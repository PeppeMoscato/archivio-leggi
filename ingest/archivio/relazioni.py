"""Dalle note di aggiornamento alle righe di `relazione_normativa` e `pronuncia_costituzionale`."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from normattiva import AmbiguityError, Normattiva, NormattivaError, NotFoundError
from normattiva.errori import InvalidUrnError

from archivio.db import RigaPronuncia, RigaRelazione
from archivio.modelli import Atto, Riferimento
from archivio.note import PRONUNCIA, classifica
from archivio.storia import chiave_urn

logger = logging.getLogger(__name__)

Chiave = tuple[str, date]
Esito = tuple[str | None, str | None]  # (urn, denominazione)


class Risolutore:
    """Risale da un riferimento in Gazzetta (codice redazionale e data) all'URN dell'atto.

    Prova in ordine: il catalogo appena estratto (gli atti del perimetro), la
    cache nel database, e solo alla fine l'API di Normattiva, una chiamata per
    riferimento distinto. Ogni risposta dell'API finisce in cache, anche quando
    l'atto non esiste, così non si chiede due volte.
    """

    def __init__(
        self,
        locali: dict[Chiave, Esito],
        cache: dict[Chiave, Esito],
        client: Normattiva | None = None,
        salva: Callable[[str, date, str | None, str | None], None] | None = None,
    ) -> None:
        self.locali = locali
        self.cache = cache
        self.client = client
        self.salva = salva
        self.chiamate = 0
        self.non_risolti = 0

    def risolvi(self, riferimento: Riferimento) -> str | None:
        if not riferimento.codice:
            return None
        chiave = (riferimento.codice, riferimento.data)
        for fonte in (self.locali, self.cache):
            if chiave in fonte:
                return fonte[chiave][0]
        if self.client is None:
            return None
        esito = self._chiedi(*chiave)
        if esito is None:
            return None
        self.cache[chiave] = esito
        if self.salva:
            self.salva(chiave[0], chiave[1], *esito)
        if esito[0] is None:
            self.non_risolti += 1
        return esito[0]

    def _chiedi(self, codice: str, giorno: date) -> Esito | None:
        """None se l'errore è passeggero: il riferimento si ritenta al prossimo giro."""
        self.chiamate += 1
        try:
            letto = self.client.dettaglio_da_gazzetta(codice, giorno)
            estremi = letto.estremi
        except AmbiguityError as errore:
            urn = {str(c.urn) for c in errore.candidati if c.estremi.ha_urn}
            if len(urn) == 1:
                return chiave_urn(urn.pop()), errore.candidati[0].estremi.denominazione
            return None, None
        except NotFoundError:
            return None, None
        except NormattivaError as errore:
            logger.warning("riferimento %s del %s non risolto: %s", codice, giorno, errore)
            return None
        try:
            return chiave_urn(str(estremi.urn)), estremi.denominazione
        except InvalidUrnError:
            return None, estremi.denominazione


def relazioni_di(atto: Atto, risolutore: Risolutore) -> tuple[list[RigaRelazione], list[RigaPronuncia]]:
    """Le relazioni in entrata e le pronunce di un atto, senza doppioni (spike, punto 10)."""
    relazioni: dict[RigaRelazione, None] = {}
    pronunce: dict[RigaPronuncia, None] = {}
    for nota in atto.note:
        for esito in classifica(nota.testo):
            if esito.tipo == PRONUNCIA:
                primo = nota.riferimenti[0] if nota.riferimenti else None
                riga = RigaPronuncia(
                    atto.urn, esito.articolo_destinazione, esito.numero_sentenza,
                    esito.anno_sentenza or (primo.data.year if primo else None),
                    primo.data if primo else None, primo.codice if primo else None, nota.testo,
                )
                pronunce[riga] = None
                continue
            for riferimento in nota.riferimenti or (None,):
                riga = RigaRelazione(
                    urn_origine=risolutore.risolvi(riferimento) if riferimento else None,
                    urn_destinazione=atto.urn,
                    tipo=esito.tipo,
                    data=riferimento.data if riferimento else None,
                    articolo_origine=esito.articolo_origine or (riferimento.articolo if riferimento else None),
                    articolo_destinazione=esito.articolo_destinazione,
                    nota=nota.testo,
                    origine_gazzetta_codice=riferimento.codice if riferimento else None,
                    origine_gazzetta_data=riferimento.data if riferimento else None,
                )
                relazioni[riga] = None
    return list(relazioni), list(pronunce)


def stato_di(atto: Atto, relazioni: list[RigaRelazione]) -> str:
    """vigente / abrogata / decaduta.

    Decaduta: Normattiva scrive "Decreto-Legge decaduto per mancata conversione"
    nel titolo dell'export. Se l'export manca, un D.L. abrogato senza legge di
    conversione si considera decaduto.
    """
    if atto.decaduto:
        return "decaduta"
    if not atto.abrogato:
        return "vigente"
    if atto.decaduto is None and atto.tipo == "decreto-legge" and not any(r.tipo == "converte" for r in relazioni):
        return "decaduta"
    return "abrogata"
