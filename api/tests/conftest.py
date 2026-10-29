import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

DSN = os.environ.get("TEST_DATABASE_URL")
# La DDL è quella della pipeline: l'API legge lo stesso database.
SCHEMA = Path(__file__).parents[2] / "ingest" / "archivio" / "schema.sql"
DATI = Path(__file__).with_name("dati.sql")
OGGETTI = (
    "DROP VIEW IF EXISTS legge_estesa, voto_gruppo; "
    "DROP TABLE IF EXISTS votazione, firmatario, fase_iter, iter, adesione_gruppo, denominazione_gruppo, gruppo, "
    "parlamentare, governo_partito, relazione_normativa, pronuncia_costituzionale, gazzetta_urn, legge, governo CASCADE"
)


@pytest.fixture(scope="session")
def database():
    """Un database con lo schema della pipeline e qualche atto vero (tests/dati.sql)."""
    if not DSN:
        pytest.skip("TEST_DATABASE_URL non impostata")
    with psycopg.connect(DSN) as conn:
        conn.execute(OGGETTI)
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
        conn.execute(DATI.read_text(encoding="utf-8"))
    return DSN


@pytest.fixture(scope="session")
def client(database):
    os.environ["DATABASE_URL"] = database
    from archivio_api.app import app

    with TestClient(app) as client:
        yield client
