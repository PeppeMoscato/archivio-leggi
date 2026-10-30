"""Dalle note di aggiornamento alle righe di `relazione_normativa` e `pronuncia_costituzionale`."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from datetime import date, timedelta

from normattiva import AmbiguityError, EstremiAtto, Normattiva, NormattivaError, NotFoundError
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
            tipo = esito.tipo
            if tipo == "converte" and atto.tipo != "decreto-legge":
                # Si converte solo un D.L. (art. 77 Cost.): su un altro atto la nota va letta come modifica.
                logger.warning("conversione su %s, che non è un decreto-legge: registrata come modifica", atto.urn)
                tipo = "modifica"
            for riferimento in nota.riferimenti or (None,):
                riga = RigaRelazione(
                    urn_origine=risolutore.risolvi(riferimento) if riferimento else None,
                    urn_destinazione=atto.urn,
                    tipo=tipo,
                    data=riferimento.data if riferimento else None,
                    articolo_origine=esito.articolo_origine or (riferimento.articolo if riferimento else None),
                    articolo_destinazione=esito.articolo_destinazione,
                    nota=nota.testo,
                    origine_gazzetta_codice=riferimento.codice if riferimento else None,
                    origine_gazzetta_data=riferimento.data if riferimento else None,
                )
                relazioni[riga] = None
    return list(relazioni), list(pronunce)


# Il D.L. perde efficacia se non è convertito entro 60 giorni dalla pubblicazione (art. 77 Cost.);
# due giorni di margine per le date di vigenza scritte da Normattiva.
TERMINE_CONVERSIONE = timedelta(days=62)


def scaduto_senza_conversione(atto: Atto) -> bool:
    """Il testo originale ha smesso di valere entro il termine di conversione."""
    pubblicazione = atto.gazzetta_data or atto.data
    return atto.fine_vigore_originale is not None and atto.fine_vigore_originale <= pubblicazione + TERMINE_CONVERSIONE


_MESI = {
    mese: numero
    for numero, mese in enumerate(
        ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
         "agosto", "settembre", "ottobre", "novembre", "dicembre"), start=1,
    )
}
# "Conversione in legge, con modificazioni, del decreto-legge 28 gennaio 2019, n. 4, recante ..."
_CONVERSIONE = re.compile(
    r"\bconversione\s+in\s+legge\W+(?:con\s+modificazioni\W+)?del\s+decreto[\s-]legge\s+"
    r"(?P<giorno>\d{1,2})[°º]?\s+(?P<mese>[a-z]+)\s+(?P<anno>\d{4})\W+n\.\s*(?P<numero>\d+)",
    re.I,
)


def convertito_dal_titolo(titolo: str) -> str | None:
    """L'URN del D.L. che una legge converte, letto dal suo titolo; None se non è una legge di conversione."""
    trovato = _CONVERSIONE.search(" ".join(titolo.split()))
    if trovato is None or (mese := _MESI.get(trovato.group("mese").lower())) is None:
        return None
    try:
        giorno = date(int(trovato.group("anno")), mese, int(trovato.group("giorno")))
    except ValueError:
        return None
    return str(EstremiAtto("DECRETO-LEGGE", giorno, trovato.group("numero")).urn)


def conversioni_dai_titoli(atti: Iterable[Atto]) -> dict[str, RigaRelazione]:
    """Le relazioni `converte` ricavate dai titoli delle leggi di conversione, per URN del D.L.

    Servono perché le note di aggiornamento dei D.L. citano la conversione solo
    a volte: nella prova sul 1995 (27/10/2026) 7 relazioni su 61 D.L. convertiti.
    La nota della relazione è il titolo della legge, così resta verificabile.
    """
    conversioni = {}
    for atto in atti:
        if atto.tipo != "legge" or (convertito := convertito_dal_titolo(atto.titolo)) is None:
            continue
        conversioni[convertito] = RigaRelazione(
            urn_origine=atto.urn, urn_destinazione=convertito, tipo="converte", data=atto.gazzetta_data,
            articolo_origine=None, articolo_destinazione=None, nota=" ".join(atto.titolo.split()),
            origine_gazzetta_codice=atto.gazzetta_codice, origine_gazzetta_data=atto.gazzetta_data,
        )
    return conversioni


def stato_di(atto: Atto, relazioni: list[RigaRelazione]) -> str:
    """vigente / abrogata / decaduta.

    Decaduta: Normattiva scrive "Decreto-Legge decaduto per mancata conversione"
    nel titolo. Non sempre però: nell'esecuzione completa del 27/10/2026 la
    frase mancava dai titoli dell'export, che la sonda della mattina invece
    mostrava. Per questo un D.L. abrogato senza legge di conversione si
    considera decaduto anche quando il testo originale ha smesso di valere entro
    il termine di conversione, o quando l'export manca.
    """
    if atto.decaduto:
        return "decaduta"
    if not atto.abrogato:
        return "vigente"
    if atto.tipo == "decreto-legge" and not any(r.tipo == "converte" for r in relazioni):
        if atto.decaduto is None or scaduto_senza_conversione(atto):
            return "decaduta"
    return "abrogata"


def data_decadenza(atto: Atto) -> date | None:
    """Il giorno dopo la fine di vigenza del testo originale; altrimenti la data già ricavata dall'export."""
    if atto.fine_vigore_originale is not None:
        return atto.fine_vigore_originale + timedelta(days=1)
    return atto.data_abrogazione
