"""Pipeline delle premesse: perché il governo ha adottato decreti-legge e decreti legislativi.

Due fasi, come la pipeline Normattiva:
- `estrai_premesse`: catalogo dell'anno (ricerca avanzata) e testo originale di ogni D.L. e
  D.Lgs.; un JSONL per anno con motivazioni, citazioni, proposta e leggi delega;
- `carica_premesse`: tabella `premessa` e relazioni `delega` (legge delega → decreto legislativo).

Le leggi ordinarie non hanno premesse utili: il loro perché sta nella relazione
illustrativa del ddl, che si raggiunge dall'iter (Senato e Camera).
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

import psycopg
from normattiva import AmbiguityError, Normattiva, NormattivaError, Urn

from archivio.catalogo import catalogo
from archivio.db import crea_schema
from archivio.modelli import Atto
from archivio.pipeline import Rapporto
from archivio.premesse import Delega, Premessa, chiave_legge, premessa_da_html

logger = logging.getLogger(__name__)

TIPI_CON_PREMESSA = ("DECRETO-LEGGE", "DECRETO LEGISLATIVO")
PAUSA = 0.5  # secondi fra una richiesta e l'altra: Normattiva non pubblica quote


def testo_originale(client: Normattiva, atto: Atto) -> str:
    """L'HTML del testo originale; se l'URN è ambiguo, quello dalla Gazzetta (testo di oggi).

    Le premesse non si modificano: il testo di oggi le riporta uguali. Succede ad atti
    ripubblicati, come il D.L. 4/2019 (sonda del 29/10/2026, spike punto 4).
    """
    try:
        return client.dettaglio(atto.urn, vigenza="originale").testo_html
    except AmbiguityError:
        if not (atto.gazzetta_codice and atto.gazzetta_data):
            raise
        return client.dettaglio_da_gazzetta(atto.gazzetta_codice, atto.gazzetta_data).testo_html


def riga_premessa(atto: Atto, premessa: Premessa) -> dict:
    return {
        "urn": atto.urn,
        "tipo": atto.tipo,
        "motivazioni": premessa.motivazioni,
        "citazioni": premessa.citazioni,
        "proposta": premessa.proposta,
        # Solo i decreti legislativi hanno una legge delega; un D.L. può citare leggi "recanti delega" per altri motivi.
        "deleghe": [d.__dict__ for d in premessa.deleghe] if atto.tipo == "decreto legislativo" else [],
        "fonte_url": Urn.parse(atto.urn).permalink,
    }


def estrai_premesse(client: Normattiva, anni: Iterable[int], uscita: Path, pausa: float = PAUSA) -> Rapporto:
    uscita.mkdir(parents=True, exist_ok=True)
    rapporto = Rapporto()
    for anno in anni:
        righe: list[dict] = []
        conti: Counter = Counter()
        for denominazione in TIPI_CON_PREMESSA:
            for atto in catalogo(client, denominazione, anno).values():
                try:
                    premessa = premessa_da_html(testo_originale(client, atto))
                except NormattivaError as errore:
                    logger.warning("%s: testo non letto (%s)", atto.urn, errore)
                    conti[f"{atto.tipo}, testo non letto"] += 1
                    continue
                finally:
                    time.sleep(pausa)
                conti[atto.tipo] += 1
                if premessa.vuota:
                    conti[f"{atto.tipo}, senza premessa"] += 1
                    continue
                conti[f"{atto.tipo}, con motivazioni"] += bool(premessa.motivazioni)
                riga = riga_premessa(atto, premessa)
                conti[f"{atto.tipo}, con legge delega"] += bool(riga["deleghe"])
                righe.append(riga)
        with (uscita / f"premesse_{anno}.jsonl").open("w", encoding="utf-8") as file:
            for riga in sorted(righe, key=lambda r: r["urn"]):
                file.write(json.dumps(riga, ensure_ascii=False) + "\n")
        rapporto.aggiungi(f"- {anno}: " + ", ".join(f"{chiave} {n}" for chiave, n in sorted(conti.items())))
    return rapporto


def leggi_premesse(cartella: Path) -> list[dict]:
    righe = []
    for file in sorted(cartella.rglob("premesse_*.jsonl")):
        with file.open(encoding="utf-8") as letto:
            righe += [json.loads(riga) for riga in letto if riga.strip()]
    return righe


def carica_premesse(conn: psycopg.Connection, righe: list[dict]) -> Rapporto:
    """Sostituisce premesse e relazioni `delega` degli atti presenti in `legge`.

    Le relazioni `delega` le scrive solo questa pipeline: il caricamento Normattiva non le tocca.
    """
    rapporto = Rapporto()
    crea_schema(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT urn FROM legge WHERE urn = ANY(%s)", ([r["urn"] for r in righe],))
        presenti = {urn for (urn,) in cur.fetchall()}
        tenute = [r for r in righe if r["urn"] in presenti]
        urn = [r["urn"] for r in tenute]
        cur.execute("DELETE FROM premessa WHERE urn = ANY(%s)", (urn,))
        cur.execute("DELETE FROM relazione_normativa WHERE tipo = 'delega' AND urn_destinazione = ANY(%s)", (urn,))
        cur.executemany(
            "INSERT INTO premessa (urn, motivazioni, citazioni, proposta, fonte_url) VALUES (%s, %s, %s, %s, %s)",
            [(r["urn"], r["motivazioni"], r["citazioni"], r["proposta"], r["fonte_url"]) for r in tenute],
        )
        deleghe = _risolvi_senza_data(cur, [(r["urn"], Delega(**d)) for r in tenute for d in r["deleghe"]])
        cur.executemany(
            """
            INSERT INTO relazione_normativa (urn_origine, urn_destinazione, tipo, data, articolo_origine, nota)
            SELECT %s, %s, 'delega', (SELECT gazzetta_data FROM legge WHERE urn = %s), %s, %s
            """,
            [(d.urn, decreto, d.urn, d.articolo, d.citazione) for decreto, d in deleghe],
        )
        cur.execute("SELECT count(*) FROM legge WHERE urn = ANY(%s)", ([d.urn for _, d in deleghe],))
        (deleghe_in_archivio,) = cur.fetchone()
    conn.commit()
    rapporto.aggiungi(f"Premesse caricate: {len(tenute)} (atti non in archivio: {len(righe) - len(tenute)})")
    rapporto.aggiungi(f"- con motivazioni: {sum(1 for r in tenute if r['motivazioni'])}")
    rapporto.aggiungi(f"Relazioni delega: {len(deleghe)}; leggi delega distinte nell'archivio: {deleghe_in_archivio}")
    return rapporto


def _risolvi_senza_data(cur: psycopg.Cursor, deleghe: list[tuple[str, Delega]]) -> list[tuple[str, Delega]]:
    """Gli URN senza giorno (`legge:2005;150`, da "la citata legge n. 150 del 2005") diventano quello
    dell'archivio con lo stesso anno e numero, se c'è; poi una sola relazione per decreto e legge."""
    risolte: dict[tuple[str, str], tuple[str, Delega]] = {}
    for decreto, delega in deleghe:
        urn = delega.urn
        if ";" in urn and "-" not in urn.rsplit(":", 1)[1] and (chiave := chiave_legge(urn)):
            cur.execute(
                "SELECT urn FROM legge WHERE tipo = 'legge' AND numero = %s AND extract(year FROM data) = %s",
                (chiave[1], int(chiave[0])),
            )
            if (trovata := cur.fetchone()):
                urn = trovata[0]
        risolte.setdefault((decreto, urn), (decreto, Delega(urn, delega.articolo, delega.citazione)))
    return list(risolte.values())

