"""Prove del caricamento su un Postgres vero. Servono `TEST_DATABASE_URL` e un database usa e getta (fixture `conn` in conftest.py)."""

import os
from datetime import date

import pytest

from archivio.modelli import Atto, Nota, Riferimento
from archivio.pipeline import carica

DSN = os.environ.get("TEST_DATABASE_URL")
pytestmark = [pytest.mark.db, pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL non impostata")]

MERLONI = "urn:nir:stato:legge:1994-02-11;109"
CODICE_APPALTI = "urn:nir:stato:decreto.legislativo:2006-04-12;163"
DL_DECADUTO = "urn:nir:stato:decreto.legge:1995-01-02;1"


def atti():
    abrogazione = Nota(
        "Il D.Lgs. 12 aprile 2006, n. 163 ha disposto (con l'art. 256, comma 1) l'abrogazione dell'intero provvedimento.",
        (Riferimento("006G0181", date(2006, 5, 2)),),
    )
    modifica = Nota(
        "Il D.P.R. 21 dicembre 1999, n. 554 ha disposto (con l'art. 1, comma 1) la modifica dell'art. 3.",
        (Riferimento("000G0034", date(2000, 4, 28)),),
    )
    pronuncia = Nota("ha dichiarato l'illegittimita' costituzionale dell'art. 4.", (Riferimento("095C1234", date(1995, 11, 22)),))
    return [
        Atto(MERLONI, "legge", "109", date(1994, 2, 11), "Legge quadro in materia di lavori pubblici",
             gazzetta_data=date(1994, 2, 19), gazzetta_numero=41, gazzetta_codice="094G0141", abrogato=True,
             versioni=3, data_abrogazione=date(2006, 7, 1), data_entrata_vigore=date(1994, 2, 19),
             note=[abrogazione, abrogazione, modifica, pronuncia]),
        Atto(CODICE_APPALTI, "decreto legislativo", "163", date(2006, 4, 12), "Codice dei contratti pubblici",
             gazzetta_data=date(2006, 5, 2), gazzetta_codice="006G0181", abrogato=True, data_abrogazione=date(2016, 4, 19)),
        Atto(DL_DECADUTO, "decreto-legge", "1", date(1995, 1, 2), "Decreto non convertito", abrogato=True, decaduto=True,
             data_abrogazione=date(1995, 3, 4)),
    ]


class ClientFinto:
    def dettaglio_da_gazzetta(self, codice, giorno):
        from normattiva import NotFoundError

        raise NotFoundError("assente")


def test_carica_e_ricarica(conn):
    for _ in range(2):  # la seconda volta non deve creare doppioni
        rapporto = carica(conn, atti(), ClientFinto())
    with conn.cursor() as cur:
        cur.execute("SELECT urn, stato, governo_id, data_abrogazione FROM legge ORDER BY urn")
        assert cur.fetchall() == [
            (DL_DECADUTO, "decaduta", "berlusconi-1", date(1995, 3, 4)),
            (CODICE_APPALTI, "abrogata", "berlusconi-3", date(2016, 4, 19)),
            (MERLONI, "abrogata", "ciampi", date(2006, 7, 1)),
        ]
        cur.execute("SELECT urn_origine, tipo, origine_gazzetta_codice FROM relazione_normativa ORDER BY tipo")
        assert cur.fetchall() == [(CODICE_APPALTI, "abroga", "006G0181"), (None, "modifica", "000G0034")]
        cur.execute("SELECT numero_sentenza, anno, articolo, gazzetta_codice FROM pronuncia_costituzionale")
        assert cur.fetchall() == [(None, 1995, "art. 4", "095C1234")]
        cur.execute("SELECT numero_modifiche, modificata FROM legge_estesa WHERE urn = %s", (MERLONI,))
        assert cur.fetchone() == (1, True)
        cur.execute("SELECT count(*) FROM gazzetta_urn WHERE urn IS NULL")
        assert cur.fetchone() == (1,)
    assert "Atti caricati: 3" in rapporto.testo()
