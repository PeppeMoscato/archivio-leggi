"""Aggiornamento settimanale incrementale da Normattiva (Fase 1).

Invece di riesportare tutto il perimetro (circa 1 h 35 min e 144 export), si
riesportano solo:
- gli atti che Normattiva ha modificato nella finestra (`atti_aggiornati`);
- gli atti pubblicati in Gazzetta negli ultimi 90 giorni (catalogo dell'anno):
  i D.L. decadono o si convertono senza che Normattiva li modifichi per forza,
  la legge di conversione (nuova) va unita al suo D.L. nello stesso caricamento,
  e per gli atti appena pubblicati export e testo arrivano dopo qualche giorno
  (prova del 30/10/2026: nessun export per le leggi e i D.Lgs. di ottobre).

Come la pipeline completa, due fasi: `estrai_aggiornamento` scrive
`atti_aggiornati.jsonl` (e le premesse dei D.L. e D.Lgs. nuovi in
`premesse_aggiornate.jsonl`); `carica_aggiornamento` li scrive nel database con
`pipeline.carica`, usando il catalogo già nel database per i riferimenti in
Gazzetta e le conversioni dai titoli. Un atto senza export completo (versioni
recenti vuote o illeggibili) non si riscrive: se è già nel database resta com'è,
se è nuovo entra con i dati del catalogo. Ogni scrittura è idempotente: una
finestra più lunga della settimana (14 giorni di default) recupera un giro
fallito senza doppioni.
"""

from __future__ import annotations

import json
import logging
import tempfile
from collections import Counter
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

import psycopg
from normattiva import Normattiva

from archivio import contesto, db
from archivio.catalogo import atto_da_ricerca, catalogo, unisci_pubblicazioni
from archivio.modelli import TIPI, Atto
from archivio.pipeline import (
    ATTESA_ATTO, PERIMETRO, ExportNonRiuscito, Rapporto, carica, esporta, leggi_atti, storie_dell_anno, unisci,
)
from archivio.storia import chiave_urn

logger = logging.getLogger(__name__)

GIORNI = 14  # una settimana più una di margine: se un giro fallisce, il successivo lo recupera
FINESTRA_RECENTI = timedelta(days=90)  # 60 giorni per la conversione dei D.L. (art. 77 Cost.) più il margine
# Fra emanazione e pubblicazione in Gazzetta passano di solito giorni, a volte settimane: per gli atti
# nuovi si guarda anche il catalogo dell'anno prima, se la finestra comincia a inizio anno.
RITARDO_GAZZETTA = timedelta(days=60)
# Con più atti di così nello stesso anno e tipo, un export dell'anno intero (1-2 minuti) costa meno
# di un export per atto.
SOGLIA_ANNO = 6
INIZIO_PERIMETRO = 1990
FILE_ATTI = "atti_aggiornati.jsonl"
FILE_PREMESSE = "premesse_aggiornate.jsonl"
DENOMINAZIONI = {tipo: denominazione for denominazione, tipo in TIPI.items()}


def modificati(client: Normattiva, dal: date, al: date) -> tuple[dict[str, Atto], Counter]:
    """Gli atti del perimetro che Normattiva ha modificato fra `dal` e `al`, uno per URN.

    Si chiede un giorno alla volta: risposte piccole, e nel log si vede se un giorno
    torna vuoto. Il flusso contiene tutti i tipi di atto (anche D.P.R., decreti
    ministeriali...): si tengono solo quelli del perimetro dal 1990.
    """
    trovati: list[Atto] = []
    conti: Counter = Counter()
    giorno = dal
    while giorno < al:
        nel_giorno = 0
        for trovato in client.atti_aggiornati(giorno, giorno + timedelta(days=1)):
            nel_giorno += 1
            denominazione = trovato.estremi.denominazione.strip().upper()
            if denominazione not in TIPI or not trovato.ha_urn or trovato.estremi.data.year < INIZIO_PERIMETRO:
                conti["fuori_perimetro"] += 1
                continue
            trovati.append(atto_da_ricerca(trovato))
        logger.info("atti aggiornati il %s: %s", giorno, nel_giorno)
        conti["nel_flusso"] += nel_giorno
        giorno += timedelta(days=1)
    return unisci_pubblicazioni(trovati), conti


def nuovi(client: Normattiva, dal: date, al: date) -> dict[str, Atto]:
    """Gli atti del perimetro pubblicati in Gazzetta da `dal`, e comunque negli ultimi 90 giorni."""
    atti: dict[str, Atto] = {}
    da = min(dal, al - FINESTRA_RECENTI)
    for denominazione in PERIMETRO:
        for anno in range((da - RITARDO_GAZZETTA).year, al.year + 1):
            for urn, atto in catalogo(client, denominazione, anno).items():
                if (atto.gazzetta_data or atto.data) >= da:
                    atti[urn] = atto
    return atti


def per_gruppo(atti: Iterable[Atto]) -> dict[tuple[str, int], dict[str, Atto]]:
    """Gli atti divisi per tipo e anno di emanazione: le coordinate dell'export."""
    gruppi: dict[tuple[str, int], dict[str, Atto]] = {}
    for atto in atti:
        gruppi.setdefault((DENOMINAZIONI[atto.tipo], atto.data.year), {})[atto.urn] = atto
    return dict(sorted(gruppi.items()))


def storie_del_gruppo(client: Normattiva, cartella: Path, denominazione: str, anno: int, atti: dict[str, Atto]):
    """Export dell'anno intero per i gruppi grandi, altrimenti un export per atto."""
    if len(atti) > SOGLIA_ANNO:
        return storie_dell_anno(client, cartella, denominazione, anno, atti)
    storie, mancanti = [], []
    for atto in atti.values():
        try:
            storie += esporta(
                client, cartella, f"{denominazione.replace(' ', '_')}_{anno}_{atto.numero}", ATTESA_ATTO,
                denominazione=denominazione, anno=anno, mese=atto.data.month, giorno=atto.data.day, numero=atto.numero,
            )
        except ExportNonRiuscito as errore:
            logger.warning("%s; l'atto resta com'è nel database", errore)
            mancanti.append(atto.urn)
    return storie, mancanti


def estrai_aggiornamento(
    client: Normattiva, dal: date, al: date, uscita: Path, pausa: float = contesto.PAUSA
) -> Rapporto:
    uscita.mkdir(parents=True, exist_ok=True)
    rapporto = Rapporto()
    cambiati, conti = modificati(client, dal, al)
    recenti = nuovi(client, dal, al)
    atti = unisci_pubblicazioni([*cambiati.values(), *recenti.values()])
    rapporto.aggiungi(f"Finestra: dal {dal:%d/%m/%Y} al {al:%d/%m/%Y}")
    rapporto.aggiungi(
        f"- atti modificati nel flusso di Normattiva: {conti['nel_flusso']}, nel perimetro: {len(cambiati)} "
        f"({', '.join(f'{t} {n}' for t, n in Counter(a.tipo for a in cambiati.values()).most_common()) or 'nessuno'})"
    )
    rapporto.aggiungi(
        f"- atti pubblicati negli ultimi {(al - min(dal, al - FINESTRA_RECENTI)).days} giorni: {len(recenti)} "
        f"({', '.join(f'{t} {n}' for t, n in Counter(a.tipo for a in recenti.values()).most_common()) or 'nessuno'})"
    )

    righe: list[Atto] = []
    esportati_totale = 0
    gruppi = per_gruppo(atti.values())
    with tempfile.TemporaryDirectory() as temporanea:
        for (denominazione, anno), gruppo in gruppi.items():
            storie, mancanti = storie_del_gruppo(client, Path(temporanea), denominazione, anno, gruppo)
            # Con le versioni recenti illeggibili note e stato sarebbero vecchi: l'atto conta come senza export.
            complete = [s for s in storie if s.completa]
            uniti, discrepanze = unisci(gruppo, complete, None)
            # Gli atti senza export restano nel file con `abrogato` None: il caricamento decide (vedi sopra).
            righe += uniti
            esportati = sum(1 for a in uniti if a.abrogato is not None)
            nel_gruppo = {chiave_urn(urn) for urn in gruppo}
            illeggibili = sum(1 for s in storie if not s.completa and s.urn in nel_gruppo)
            if esportati < len(gruppo):
                rapporto.aggiungi(
                    f"- {anno} {denominazione}: senza export {len(gruppo) - esportati} su {len(gruppo)}"
                    + (f", di cui con l'ultima versione illeggibile {illeggibili}" if illeggibili else "")
                    + (f" ({', '.join(mancanti)})" if mancanti else "")
                )
            esportati_totale += esportati
            logger.info("%s %s: %s atti, export %s, discrepanze %s", anno, denominazione, len(gruppo), len(storie), dict(discrepanze))
    with (uscita / FILE_ATTI).open("w", encoding="utf-8") as scritto:
        for atto in sorted(righe, key=lambda a: (a.data, a.tipo, a.numero)):
            scritto.write(json.dumps(atto.in_json(), ensure_ascii=False) + "\n")
    rapporto.aggiungi(f"Atti riesportati: {esportati_totale} su {len(atti)}, in {len(gruppi)} gruppi per tipo e anno")

    # Le premesse non cambiano con le modifiche: servono solo per i D.L. e D.Lgs. recenti. Si rileggono per
    # tutti i 90 giorni perché il testo degli atti appena pubblicati a volte non si legge ancora (errore 500).
    conti_premesse: Counter = Counter()
    con_premessa = [a for a in recenti.values() if DENOMINAZIONI[a.tipo] in contesto.TIPI_CON_PREMESSA]
    premesse = contesto.premesse_di(client, con_premessa, conti_premesse, pausa)
    contesto.scrivi_premesse(uscita / FILE_PREMESSE, premesse)
    rapporto.aggiungi(
        f"Premesse dei D.L. e D.Lgs. recenti: {len(premesse)}"
        + (f" ({', '.join(f'{chiave} {n}' for chiave, n in sorted(conti_premesse.items()))})" if conti_premesse else "")
    )
    return rapporto


def atto_dal_catalogo(riga: tuple) -> Atto:
    urn, tipo, numero, giorno, titolo, gazzetta_data, gazzetta_numero, gazzetta_codice = riga
    return Atto(urn, tipo, numero, giorno, titolo, gazzetta_data, gazzetta_numero, gazzetta_codice)


def carica_aggiornamento(conn: psycopg.Connection, cartella: Path, client: Normattiva | None = None) -> Rapporto:
    """Atti aggiornati e premesse dei nuovi nel database, dopo il caricamento completo di Normattiva."""
    db.crea_schema(conn)
    letti = leggi_atti(cartella)
    nel_database = {riga[0]: atto_dal_catalogo(riga) for riga in db.leggi_catalogo(conn)}
    # Senza export (`abrogato` None) un atto già nel database resta com'è; uno nuovo entra con i dati del catalogo.
    atti = [a for a in letti if a.abrogato is not None or a.urn not in nel_database]
    for atto in atti:
        # Con più pubblicazioni in Gazzetta si tiene la più vecchia (come `unisci_pubblicazioni`):
        # il flusso degli aggiornati può portare la ripubblicazione.
        presente = nel_database.get(atto.urn)
        if presente and presente.gazzetta_data and (atto.gazzetta_data is None or presente.gazzetta_data < atto.gazzetta_data):
            atto.gazzetta_data, atto.gazzetta_numero, atto.gazzetta_codice = (
                presente.gazzetta_data, presente.gazzetta_numero, presente.gazzetta_codice,
            )
    noti = list((nel_database | {a.urn: a for a in atti}).values())
    rapporto = carica(conn, atti, client, noti=noti)
    rapporto.aggiungi(
        f"- già nel database: {sum(1 for a in atti if a.urn in nel_database)}; "
        f"nuovi: {sum(1 for a in atti if a.urn not in nel_database)} "
        f"(di cui senza export, solo dal catalogo: {sum(1 for a in atti if a.abrogato is None)}); "
        f"senza export e lasciati come erano: {len(letti) - len(atti)}; atti nel database prima: {len(nel_database)}"
    )
    rapporto.righe += contesto.carica_premesse(conn, contesto.leggi_premesse(cartella)).righe
    return rapporto


def finestra(giorni: int, al: date | None = None) -> tuple[date, date]:
    al = al or date.today()
    if giorni < 1:
        raise ValueError("la finestra deve essere di almeno un giorno")
    return al - timedelta(days=giorni), al

