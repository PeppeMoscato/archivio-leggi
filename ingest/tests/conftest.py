import os

import pytest

from archivio import db

# Tutto ciò che crea schema.sql, viste prima delle tabelle.
OGGETTI = (
    "DROP VIEW IF EXISTS legge_estesa, voto_gruppo; "
    "DROP TABLE IF EXISTS votazione, firmatario, fase_iter, iter, adesione_gruppo, denominazione_gruppo, gruppo, "
    "parlamentare, governo_partito, premessa, relazione_normativa, pronuncia_costituzionale, gazzetta_urn, legge, governo CASCADE"
)


@pytest.fixture
def conn():
    """Un database vuoto: si cancellano le tabelle dell'archivio prima di ogni prova."""
    with db.connetti(os.environ["TEST_DATABASE_URL"]) as connessione:
        with connessione.cursor() as cur:
            cur.execute(OGGETTI)
        connessione.commit()
        yield connessione
