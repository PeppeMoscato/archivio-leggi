"""Catalogo: l'elenco degli atti di un tipo e di un anno, dalla ricerca avanzata di Normattiva."""

from __future__ import annotations

import logging
import re
import time

from normattiva import AttoTrovato, ConnectionError, EsitoRicerca, EstremiAtto, Normattiva, OverloadedError, Sort

from archivio.modelli import TIPI, Atto

logger = logging.getLogger(__name__)

PER_PAGINA = 200
# La ricerca a volte aggiunge note al numero: "1 (Raccolta 2019)" (sonda del 27/10/2026).
_NUMERO = re.compile(r"^\s*(\d+(?:-?[a-z]+)?)", re.I)
# Dopo un guasto del servizio si riprova più tardi, come per le premesse. Rilancio su Neon del 31/10/2026
# (run 41180975376): "Server disconnected" sulla ricerca ha fatto fallire l'estrazione intera del 1993 e del 1999.
ATTESE_DOPO_GUASTO = (30, 90, 180)


def ricerca(client: Normattiva, attese: tuple[float, ...] = ATTESE_DOPO_GUASTO, **criteri) -> EsitoRicerca:
    """`ricerca_avanzata`, riprovata dopo ciascuna delle `attese` se il servizio non risponde o è sovraccarico."""
    for attesa in attese:
        try:
            return client.ricerca_avanzata(**criteri)
        except (ConnectionError, OverloadedError) as errore:
            logger.warning("ricerca %s: %s, nuovo tentativo fra %s s", criteri, errore, attesa)
            time.sleep(attesa)
    return client.ricerca_avanzata(**criteri)


def numero_pulito(numero: str | None) -> str:
    trovato = _NUMERO.match(numero or "")
    return trovato.group(1).lower() if trovato else (numero or "").strip()


def atto_da_ricerca(trovato: AttoTrovato) -> Atto:
    estremi, gazzetta = trovato.estremi, trovato.gazzetta
    numero = numero_pulito(estremi.numero)
    return Atto(
        urn=str(EstremiAtto(estremi.denominazione, estremi.data, numero).urn),
        tipo=TIPI[estremi.denominazione.strip().upper()],
        numero=numero,
        data=estremi.data,
        titolo=trovato.titolo,
        gazzetta_data=gazzetta.data,
        gazzetta_numero=gazzetta.numero,
        gazzetta_codice=gazzetta.codice_redazionale,
    )


def unisci_pubblicazioni(atti: list[Atto]) -> dict[str, Atto]:
    """Un atto per URN: con più pubblicazioni in Gazzetta si tiene la più vecchia (spike, punto 4)."""
    per_urn: dict[str, Atto] = {}
    for atto in atti:
        presente = per_urn.get(atto.urn)
        if presente is None or (atto.gazzetta_data or atto.data) < (presente.gazzetta_data or presente.data):
            per_urn[atto.urn] = atto
    return per_urn


def catalogo(client: Normattiva, denominazione: str, anno: int) -> dict[str, Atto]:
    """Tutti gli atti di quel tipo emanati in quell'anno, uno per URN."""
    trovati: list[Atto] = []
    pagina, totale = 1, None
    while True:
        esito = ricerca(
            client, denominazione=denominazione, anno=anno, sort=Sort.OLDEST, pagina=pagina, per_pagina=PER_PAGINA
        )
        totale = esito.totale if totale is None else totale
        for trovato in esito.atti:
            # La ricerca per denominazione potrebbe restituire tipi affini: si tiene solo quello chiesto.
            if trovato.estremi.denominazione.strip().upper() == denominazione:
                trovati.append(atto_da_ricerca(trovato))
        letti = (pagina - 1) * PER_PAGINA + len(esito.atti)
        if not esito.atti or letti >= totale:
            break
        pagina += 1
    atti = unisci_pubblicazioni(trovati)
    logger.info("catalogo %s %s: %s risultati, %s atti distinti", denominazione, anno, totale, len(atti))
    return atti
