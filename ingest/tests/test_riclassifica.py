"""Riclassificazione delle `converte` già salvate (1/11/2026): note vere viste nei caricamenti del 27 e 30/10."""

import os
from datetime import date

import pytest

from archivio import db
from archivio.riclassifica import Correzione, correzione, riclassifica

RDC = "urn:nir:stato:decreto.legge:2019-01-28;4"
DLGS_504 = "urn:nir:stato:decreto.legislativo:1995-10-26;504"
L_241 = "urn:nir:stato:legge:1990-08-07;241"
DL_1995 = "urn:nir:stato:decreto.legge:1995-01-07;1"

ALTRO_DL = ("ha disposto (con l'art. 1, comma 1) la conversione con modificazioni del D.L. 21 ottobre 2021, n. 146 "
            "(in G.U. 21/10/2021, n. 252).")
STESSO_DL = ("La L. 28 marzo 2019, n. 26 ha disposto (con l'art. 1, comma 1) la conversione con modificazioni "
             "del D.L. 28 gennaio 2019, n. 4.")
TITOLO = ("Conversione in legge, con modificazioni, del decreto-legge 28 gennaio 2019, n. 4, recante disposizioni urgenti "
          "in materia di reddito di cittadinanza e di pensioni.")
CITAZIONE = ("Il D.L. 7 marzo 1995, n. 66 ha disposto (con l'art. 1, comma 2) che \"restano validi gli atti adottati sulla "
             "base del D.L. 7 gennaio 1995, n. 1, fino alla data di entrata in vigore della legge di conversione del presente "
             "decreto\".")
DUE_CLAUSOLE = ("Il D.L. 21 ottobre 2021, n. 146, convertito con modificazioni dalla L. 17 dicembre 2021, n. 215, ha disposto "
                "(con l'art. 5, comma 1) la modifica dell'art. 3; (con l'art. 1, comma 1) la conversione con modificazioni "
                "del D.L. 21 ottobre 2021, n. 146.")


def test_restano_converte():
    assert correzione(TITOLO, None, RDC, "decreto-legge") is None
    assert correzione(STESSO_DL, "art. 1, comma 1", RDC, "decreto-legge") is None
    assert correzione("ha disposto la conversione in legge del presente decreto.", None, RDC, "decreto-legge") is None


def test_diventano_modifica():
    # Su un atto che non è un D.L. e su un D.L. diverso da quello convertito.
    assert correzione(ALTRO_DL, "art. 1, comma 1", DLGS_504, "decreto legislativo") == Correzione("modifica", None)
    assert correzione(ALTRO_DL, "art. 1, comma 1", RDC, "decreto-legge").tipo == "modifica"
    # Citazione della legge di conversione (il caso della L. 241/1990).
    assert correzione(CITAZIONE, "art. 1, comma 2", DL_1995, "decreto-legge").tipo == "modifica"
    # Un titolo di legge di conversione su un atto che non è quel D.L.
    assert correzione(TITOLO, None, L_241, "legge").tipo == "modifica"


def test_sceglie_la_clausola_della_conversione():
    # La clausola "la modifica dell'art. 3" non è mai stata una converte: si guarda quella con la conversione.
    assert correzione(DUE_CLAUSOLE, "art. 1, comma 1", DLGS_504, "decreto legislativo") == Correzione("modifica", None)


DSN = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.db
@pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL non impostata")
def test_riclassifica_nel_database(conn):
    db.crea_schema(conn)
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO legge (urn, tipo, numero, data, titolo, link_normattiva, stato) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                (RDC, "decreto-legge", "4", date(2019, 1, 28), "Reddito di cittadinanza", "https://www.normattiva.it/", "vigente"),
                (DLGS_504, "decreto legislativo", "504", date(1995, 10, 26), "Testo unico accise", "https://www.normattiva.it/", "vigente"),
                (DL_1995, "decreto-legge", "1", date(1995, 1, 7), "Decreto", "https://www.normattiva.it/", "abrogata"),
            ],
        )
        cur.executemany(
            "INSERT INTO relazione_normativa (urn_destinazione, tipo, nota, articolo_origine) VALUES (%s, %s, %s, %s)",
            [
                (RDC, "converte", TITOLO, None),
                (RDC, "converte", STESSO_DL, "art. 1, comma 1"),
                (RDC, "converte", ALTRO_DL, "art. 1, comma 1"),
                (DLGS_504, "converte", ALTRO_DL, "art. 1, comma 1"),
                (DL_1995, "converte", CITAZIONE, "art. 1, comma 2"),
                (DLGS_504, "modifica", ALTRO_DL, "art. 1, comma 1"),
            ],
        )
    conn.commit()

    prova = riclassifica(conn)
    assert prova.controllate == 5
    assert prova.corrette == {"modifica": 3}
    assert prova.per_destinazione == {"decreto-legge": 2, "decreto legislativo": 1}
    assert prova.decreti_senza_conversione == [DL_1995]
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM relazione_normativa WHERE tipo = 'converte'")
        assert cur.fetchone()[0] == 5  # sola lettura

    riclassifica(conn, scrivi=True)
    with conn.cursor() as cur:
        cur.execute("SELECT urn_destinazione, nota FROM relazione_normativa WHERE tipo = 'converte' ORDER BY id")
        assert cur.fetchall() == [(RDC, TITOLO), (RDC, STESSO_DL)]
    conn.commit()
    assert riclassifica(conn).corrette == {}
