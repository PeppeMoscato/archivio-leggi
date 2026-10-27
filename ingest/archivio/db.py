"""Scrittura nel database (PostgreSQL su Neon, o un Postgres locale per le prove).

Ogni scrittura è idempotente: gli atti si aggiornano per URN, le relazioni e
le pronunce di un atto si cancellano e si riscrivono insieme all'atto. Così la
pipeline si può rilanciare su un anno o su tutto il perimetro senza doppioni.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import psycopg

from archivio.governi import FONTE_URL, Governo

SCHEMA = Path(__file__).with_name("schema.sql")


@dataclass(frozen=True)
class RigaLegge:
    urn: str
    tipo: str
    numero: str
    data: date
    titolo: str
    link_normattiva: str
    stato: str
    data_abrogazione: date | None
    data_entrata_vigore: date | None
    gazzetta_data: date | None
    gazzetta_numero: int | None
    gazzetta_codice: str | None
    governo_id: str | None


@dataclass(frozen=True)
class RigaRelazione:
    urn_origine: str | None
    urn_destinazione: str
    tipo: str
    data: date | None
    articolo_origine: str | None
    articolo_destinazione: str | None
    nota: str
    origine_gazzetta_codice: str | None
    origine_gazzetta_data: date | None


@dataclass(frozen=True)
class RigaPronuncia:
    urn_legge: str
    articolo: str | None
    numero_sentenza: str | None
    anno: int | None
    data_gazzetta: date | None
    gazzetta_codice: str | None
    nota: str


def connetti(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn, autocommit=False)


def crea_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()


def salva_governi(conn: psycopg.Connection, governi: Iterable[Governo]) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO governo (id, nome, presidente, inizio, fine, fonte_url)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET nome = EXCLUDED.nome, presidente = EXCLUDED.presidente,
                inizio = EXCLUDED.inizio, fine = EXCLUDED.fine, fonte_url = EXCLUDED.fonte_url
            """,
            [(g.id, g.nome, g.presidente, g.inizio, g.fine, FONTE_URL) for g in governi],
        )
    conn.commit()


def salva_leggi(conn: psycopg.Connection, righe: Iterable[RigaLegge]) -> int:
    righe = list(righe)
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO legge (urn, tipo, numero, data, titolo, link_normattiva, stato, data_abrogazione,
                data_entrata_vigore, gazzetta_data, gazzetta_numero, gazzetta_codice, governo_id, aggiornato_il)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (urn) DO UPDATE SET tipo = EXCLUDED.tipo, numero = EXCLUDED.numero, data = EXCLUDED.data,
                titolo = EXCLUDED.titolo, link_normattiva = EXCLUDED.link_normattiva, stato = EXCLUDED.stato,
                data_abrogazione = EXCLUDED.data_abrogazione, data_entrata_vigore = EXCLUDED.data_entrata_vigore,
                gazzetta_data = EXCLUDED.gazzetta_data, gazzetta_numero = EXCLUDED.gazzetta_numero,
                gazzetta_codice = EXCLUDED.gazzetta_codice, governo_id = EXCLUDED.governo_id, aggiornato_il = now()
            """,
            [
                (
                    r.urn, r.tipo, r.numero, r.data, r.titolo, r.link_normattiva, r.stato, r.data_abrogazione,
                    r.data_entrata_vigore, r.gazzetta_data, r.gazzetta_numero, r.gazzetta_codice, r.governo_id,
                )
                for r in righe
            ],
        )
    conn.commit()
    return len(righe)


def sostituisci_relazioni(
    conn: psycopg.Connection,
    urn_atti: Iterable[str],
    relazioni: Iterable[RigaRelazione],
    pronunce: Iterable[RigaPronuncia],
) -> None:
    """Cancella relazioni in entrata e pronunce degli atti indicati e scrive quelle nuove."""
    urn_atti = list(urn_atti)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM relazione_normativa WHERE urn_destinazione = ANY(%s)", (urn_atti,))
        cur.execute("DELETE FROM pronuncia_costituzionale WHERE urn_legge = ANY(%s)", (urn_atti,))
        cur.executemany(
            """
            INSERT INTO relazione_normativa (urn_origine, urn_destinazione, tipo, data, articolo_origine,
                articolo_destinazione, nota, origine_gazzetta_codice, origine_gazzetta_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    r.urn_origine, r.urn_destinazione, r.tipo, r.data, r.articolo_origine, r.articolo_destinazione,
                    r.nota, r.origine_gazzetta_codice, r.origine_gazzetta_data,
                )
                for r in relazioni
            ],
        )
        cur.executemany(
            """
            INSERT INTO pronuncia_costituzionale (urn_legge, articolo, numero_sentenza, anno, data_gazzetta,
                gazzetta_codice, nota)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [(p.urn_legge, p.articolo, p.numero_sentenza, p.anno, p.data_gazzetta, p.gazzetta_codice, p.nota) for p in pronunce],
        )
    conn.commit()


def leggi_cache_gazzetta(conn: psycopg.Connection) -> dict[tuple[str, date], tuple[str | None, str | None]]:
    with conn.cursor() as cur:
        cur.execute("SELECT codice_redazionale, data_gazzetta, urn, tipo FROM gazzetta_urn")
        return {(codice, giorno): (urn, tipo) for codice, giorno, urn, tipo in cur.fetchall()}


def salva_cache_gazzetta(conn: psycopg.Connection, codice: str, giorno: date, urn: str | None, tipo: str | None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO gazzetta_urn (codice_redazionale, data_gazzetta, urn, tipo) VALUES (%s, %s, %s, %s)
            ON CONFLICT (codice_redazionale, data_gazzetta) DO UPDATE SET urn = EXCLUDED.urn, tipo = EXCLUDED.tipo,
                risolto_il = now()
            """,
            (codice, giorno, urn, tipo),
        )
    conn.commit()
