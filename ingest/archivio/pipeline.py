"""Pipeline Normattiva → Postgres (Task 1.1), in due fasi.

1. `estrai`: per ogni tipo di atto e anno, catalogo (ricerca avanzata) più
   storia (export multivigente). Scrive un file JSONL per anno. Su GitHub
   Actions gira un job per anno, in parallelo.
2. `carica`: legge tutti i JSONL, risolve gli atti modificanti, classifica le
   note, ricava stato e governo e scrive nel database.

Le due fasi sono separate perché la seconda ha bisogno del catalogo completo
per risolvere i riferimenti in Gazzetta senza chiamare l'API.
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from normattiva import ClasseProvvedimento, Format, Normattiva, NormattivaError, Sort, Urn
from normattiva.modelli import ExportMode

from archivio import db, governi
from archivio.catalogo import PER_PAGINA, atto_da_ricerca, catalogo
from archivio.modelli import TIPI, Atto
from archivio.relazioni import Risolutore, conversioni_dai_titoli, data_decadenza, relazioni_di, stato_di
from archivio.storia import Storia, chiave_urn, decaduto, leggi_storie

logger = logging.getLogger(__name__)

PERIMETRO = tuple(TIPI)
# Un export annuale dura di solito 1-2 minuti (sonda del 27/10/2026), ma alcuni restano
# in lavorazione per ore (D.L. 2008 nella prima esecuzione completa): meglio arrendersi
# presto e dividere la richiesta.
ATTESA_ANNO = 900.0
ATTESA_MESE = 600.0
ATTESA_ATTO = 300.0


# --- Fase 1: estrazione -------------------------------------------------------


def abrogati_per_classe(client: Normattiva, denominazione: str, anno: int) -> set[str]:
    """Gli URN che la ricerca classifica come ABROGATO: controllo incrociato col flag dell'export."""
    urn: set[str] = set()
    pagina = 1
    while True:
        esito = client.ricerca_avanzata(
            denominazione=denominazione, anno=anno, classe=ClasseProvvedimento.ABROGATO,
            sort=Sort.OLDEST, pagina=pagina, per_pagina=PER_PAGINA,
        )
        urn.update(atto_da_ricerca(a).urn for a in esito.atti if a.estremi.denominazione.strip().upper() == denominazione)
        if not esito.atti or (pagina - 1) * PER_PAGINA + len(esito.atti) >= esito.totale:
            return urn
        pagina += 1


class ExportNonRiuscito(Exception):
    pass


def esporta(client: Normattiva, cartella: Path, nome: str, attesa: float, tentativi: int = 2, **criteri) -> list[Storia]:
    """Export multivigente in JSON; l'archivio si legge e poi si cancella."""
    ultimo_errore: Exception | None = None
    for tentativo in range(1, tentativi + 1):
        inizio = time.monotonic()
        try:
            export = client.start_export(format=Format.JSON, mode=ExportMode.MULTIVIGENTE, massimo_atti=None, **criteri)
            export.wait(timeout=attesa)
            percorso = export.save(cartella / f"{nome}.zip")
        except NormattivaError as errore:
            ultimo_errore = errore
            logger.warning("export %s, tentativo %s fallito: %s", nome, tentativo, errore)
            if tentativo < tentativi:
                time.sleep(30 * tentativo)
            continue
        dimensione = percorso.stat().st_size
        storie = list(leggi_storie(percorso))
        percorso.unlink()
        logger.info("export %s: %s atti, %.1f MB, %.0f s", nome, len(storie), dimensione / 1e6, time.monotonic() - inizio)
        return storie
    raise ExportNonRiuscito(f"export {nome} non riuscito: {ultimo_errore}")


def storie_dell_anno(
    client: Normattiva, cartella: Path, denominazione: str, anno: int, atti: dict[str, Atto]
) -> tuple[list[Storia], list[str]]:
    """Le storie degli atti di un anno, e gli URN rimasti senza export.

    Prima un export per l'anno intero; se non si conclude, uno per mese; se un
    mese non si conclude, uno per atto. Un atto che non si esporta nemmeno da
    solo resta senza storia: lo stato si prende dalla classe della ricerca.
    """
    nome = f"{denominazione.replace(' ', '_')}_{anno}"
    try:
        return esporta(client, cartella, nome, ATTESA_ANNO, tentativi=1, denominazione=denominazione, anno=anno), []
    except ExportNonRiuscito as errore:
        logger.warning("%s; divido per mese", errore)
    storie: list[Storia] = []
    mancanti: list[str] = []
    for mese in range(1, 13):
        del_mese = [a for a in atti.values() if a.data.month == mese]
        if not del_mese:
            continue
        try:
            storie += esporta(
                client, cartella, f"{nome}_{mese:02d}", ATTESA_MESE, denominazione=denominazione, anno=anno, mese=mese
            )
            continue
        except ExportNonRiuscito as errore:
            logger.warning("%s; divido per atto", errore)
        for atto in del_mese:
            try:
                storie += esporta(
                    client, cartella, f"{nome}_{atto.numero}", ATTESA_ATTO, tentativi=1,
                    denominazione=denominazione, anno=anno, mese=mese, giorno=atto.data.day, numero=atto.numero,
                )
            except ExportNonRiuscito as errore:
                logger.warning("%s; l'atto resta senza storia", errore)
                mancanti.append(atto.urn)
    return storie, mancanti


@dataclass
class Rapporto:
    righe: list[str] = field(default_factory=list)

    def aggiungi(self, riga: str) -> None:
        logger.info(riga)
        self.righe.append(riga)

    def testo(self) -> str:
        return "\n".join(self.righe) + "\n"


def unisci(atti: dict[str, Atto], storie: Iterable[Storia], abrogati: set[str]) -> tuple[list[Atto], Counter]:
    """Aggiunge la storia a ogni atto del catalogo; conta le discrepanze."""
    conti: Counter = Counter()
    per_urn = {chiave_urn(urn): atto for urn, atto in atti.items()}
    for storia in storie:
        atto = per_urn.get(storia.urn)
        if atto is None:
            conti["export_fuori_catalogo"] += 1
            continue
        if atto.abrogato is not None:
            conti["export_doppi"] += 1
        atto.abrogato = storia.abrogato
        # La frase sulla decadenza può stare nel titolo dell'export o in quello della ricerca.
        atto.decaduto = storia.decaduto or decaduto(atto.titolo)
        atto.versioni = storia.versioni
        atto.data_abrogazione = storia.data_abrogazione
        atto.data_entrata_vigore = storia.data_entrata_vigore
        atto.fine_vigore_originale = storia.fine_vigore_originale
        atto.note = storia.note
    for atto in per_urn.values():
        per_classe = atto.urn in abrogati
        if atto.abrogato is None:
            conti["senza_export"] += 1
            atto.abrogato = per_classe
        elif atto.abrogato != per_classe:
            conti["abrogato_discorde"] += 1
    return list(per_urn.values()), conti


def estrai(client: Normattiva, anni: Iterable[int], uscita: Path, denominazioni: Iterable[str] = PERIMETRO) -> Rapporto:
    uscita.mkdir(parents=True, exist_ok=True)
    rapporto = Rapporto()
    with tempfile.TemporaryDirectory() as temporanea:
        for anno in anni:
            righe: list[Atto] = []
            for denominazione in denominazioni:
                atti = catalogo(client, denominazione, anno)
                if not atti:
                    continue
                storie, mancanti = storie_dell_anno(client, Path(temporanea), denominazione, anno, atti)
                uniti, conti = unisci(atti, storie, abrogati_per_classe(client, denominazione, anno))
                if mancanti:
                    rapporto.aggiungi(f"- {anno} {denominazione}: export non riuscito per {', '.join(mancanti)}")
                righe += uniti
                rapporto.aggiungi(
                    f"- {anno} {denominazione}: {len(atti)} atti, export {len(storie)}, "
                    f"abrogati {sum(1 for a in uniti if a.abrogato)}, decaduti {sum(1 for a in uniti if a.decaduto)}, note {sum(len(a.note) for a in uniti)}"
                    + (f", discrepanze {dict(conti)}" if conti else "")
                )
            file = uscita / f"atti_{anno}.jsonl"
            with file.open("w", encoding="utf-8") as scritto:
                for atto in sorted(righe, key=lambda a: (a.data, a.tipo, a.numero)):
                    scritto.write(json.dumps(atto.in_json(), ensure_ascii=False) + "\n")
    return rapporto


# --- Fase 2: caricamento ------------------------------------------------------


def leggi_atti(cartella: Path) -> list[Atto]:
    atti = []
    for file in sorted(cartella.rglob("atti_*.jsonl")):
        with file.open(encoding="utf-8") as letto:
            atti += [Atto.da_json(json.loads(riga)) for riga in letto if riga.strip()]
    return atti


def riga_legge(atto: Atto, stato: str, elenco_governi: list[governi.Governo]) -> db.RigaLegge:
    return db.RigaLegge(
        urn=atto.urn,
        tipo=atto.tipo,
        numero=atto.numero,
        data=atto.data,
        titolo=atto.titolo,
        link_normattiva=Urn.parse(atto.urn).permalink,
        stato=stato,
        data_abrogazione=None if stato == "vigente" else data_decadenza(atto) if stato == "decaduta" else atto.data_abrogazione,
        data_entrata_vigore=atto.data_entrata_vigore,
        gazzetta_data=atto.gazzetta_data,
        gazzetta_numero=atto.gazzetta_numero,
        gazzetta_codice=atto.gazzetta_codice,
        governo_id=governi.governo_alla_data(elenco_governi, atto.data),
    )


def carica(conn, atti: list[Atto], client: Normattiva | None = None, blocco: int = 500) -> Rapporto:
    rapporto = Rapporto()
    db.crea_schema(conn)
    elenco_governi = governi.carica()
    db.salva_governi(conn, elenco_governi)

    locali = {
        (a.gazzetta_codice, a.gazzetta_data): (a.urn, a.tipo) for a in atti if a.gazzetta_codice and a.gazzetta_data
    }
    risolutore = Risolutore(
        locali, db.leggi_cache_gazzetta(conn), client, lambda *riga: db.salva_cache_gazzetta(conn, *riga)
    )
    stati: Counter = Counter()
    tipi: Counter = Counter()
    pronunce_totali = senza_origine = dai_titoli = 0
    conversioni = conversioni_dai_titoli(atti)
    # Prima tutte le leggi (le relazioni hanno la FK su urn_destinazione), poi le relazioni a blocchi.
    calcolate = []
    for atto in atti:
        relazioni, pronunce = relazioni_di(atto, risolutore)
        conversione = conversioni.get(atto.urn)
        if conversione and not any(r.tipo == "converte" and r.urn_origine == conversione.urn_origine for r in relazioni):
            relazioni.append(conversione)
            dai_titoli += 1
        stato = stato_di(atto, relazioni)
        calcolate.append((atto, relazioni, pronunce))
        stati[(atto.tipo, stato)] += 1
        tipi.update(r.tipo for r in relazioni)
        pronunce_totali += len(pronunce)
        senza_origine += sum(1 for r in relazioni if r.urn_origine is None)
    db.salva_leggi(conn, [riga_legge(atto, stato_di(atto, relazioni), elenco_governi) for atto, relazioni, _ in calcolate])
    for inizio in range(0, len(calcolate), blocco):
        parte = calcolate[inizio : inizio + blocco]
        db.sostituisci_relazioni(
            conn,
            [atto.urn for atto, _, _ in parte],
            [r for _, relazioni, _ in parte for r in relazioni],
            [p for _, _, pronunce in parte for p in pronunce],
        )

    rapporto.aggiungi(f"Atti caricati: {len(atti)}")
    for (tipo, stato), quanti in sorted(stati.items()):
        rapporto.aggiungi(f"- {tipo}, {stato}: {quanti}")
    rapporto.aggiungi(f"Relazioni: {sum(tipi.values())} ({', '.join(f'{t} {n}' for t, n in tipi.most_common())})")
    rapporto.aggiungi(f"- converte ricavate dal titolo della legge di conversione: {dai_titoli}")
    rapporto.aggiungi(f"- senza atto di origine risolto: {senza_origine}")
    rapporto.aggiungi(f"Pronunce della Corte costituzionale: {pronunce_totali}")
    rapporto.aggiungi(f"Chiamate API per risolvere riferimenti: {risolutore.chiamate} (non risolti: {risolutore.non_risolti})")
    return rapporto
