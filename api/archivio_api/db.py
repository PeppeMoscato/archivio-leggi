"""Connessioni al database (PostgreSQL su Neon) in sola lettura.

Neon sospende il compute dopo 5 minuti senza attività e il piano Free ha 100
CU-ore al mese: un pool che tiene connessioni sempre aperte lo terrebbe sveglio.
Per questo il pool parte vuoto (`min_size=0`), chiude le connessioni ferme da
più di un minuto e controlla ogni connessione prima di darla, perché dopo una
sospensione quelle vecchie possono essere cadute.
"""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
from fastapi import Request
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _configura(conn: psycopg.Connection) -> None:
    # Ogni transazione parte con BEGIN READ ONLY: funziona anche dietro il pooler di Neon
    # (PgBouncer in modalità transaction), dove un SET di sessione non resterebbe.
    conn.read_only = True
    conn.row_factory = dict_row


def crea_pool(dsn: str) -> ConnectionPool:
    return ConnectionPool(
        dsn,
        min_size=0,
        max_size=5,
        max_idle=60,
        open=False,
        configure=_configura,
        check=ConnectionPool.check_connection,
        name="archivio",
    )


def connessione(request: Request) -> Iterator[psycopg.Connection]:
    """Dipendenza FastAPI: una connessione del pool per la durata della richiesta."""
    with request.app.state.pool.connection() as conn:
        yield conn
