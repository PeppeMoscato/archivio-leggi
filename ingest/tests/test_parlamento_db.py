"""Caricamento del Senato su un Postgres vero (serve `TEST_DATABASE_URL`)."""

import os
from datetime import date

import pytest

from archivio import db, senato
from archivio.parlamento import carica_senato
from archivio.senato import DDL, GRUPPO, SENATORE, Adesione, Denominazione, Iniziativa, Legislatura, Persone, Senatore
from test_senato import fase, votazione

pytestmark = [pytest.mark.db, pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL non impostata")]

SIRCHIA = "urn:nir:stato:legge:2003-01-16;3"


def scrivi_file(cartella):
    fasi = [
        fase("2122-BIS", "C", 1),
        fase("1271", "S", 2, numeri_legge=[3], date_legge=[date(2003, 1, 16)], data_stato=date(2002, 12, 20)),
    ]
    voti = {"favorevoli": ["1", "2"], "contrari": ["3"], "astenuti": ["99"]}  # il 99 non ha scheda
    leg = Legislatura(
        14,
        fasi,
        [Iniziativa(fasi[0].id, "Pres. Consiglio Silvio Berlusconi (Gov. Berlusconi-II)", "Governativa", True, None),
         Iniziativa(fasi[1].id, "Sen. Bianchi", "Parlamentare", False, SENATORE + "2")],
        [votazione("DDL n. 1271. Votazione finale", [fasi[1].id], id="http://dati.senato.it/votazione/14/1", data=date(2002, 12, 20),
                   favorevoli=2, contrari=1, astenuti=1, voti=voti),
         votazione("DDL n. 1271. Em. 1.1", [fasi[1].id], id="http://dati.senato.it/votazione/14/2", tipo_votazione="segreta",
                   data=date(2002, 12, 19))],
        votazioni_scartate=7,
    )
    persone = Persone(
        [Senatore(SENATORE + "1", "Anna", "Rossi"), Senatore(SENATORE + "2", "Luca", "Bianchi"), Senatore(SENATORE + "3", "Ugo", "Verdi")],
        [
            Adesione(SENATORE + "1", GRUPPO + "33", date(2001, 5, 30), None, None),
            # Il senatore 2 cambia gruppo il giorno prima del voto.
            Adesione(SENATORE + "2", GRUPPO + "33", date(2001, 5, 30), date(2002, 12, 19), None),
            Adesione(SENATORE + "2", GRUPPO + "40", date(2002, 12, 19), None, "Presidente"),
            Adesione(SENATORE + "3", GRUPPO + "40", date(2001, 5, 30), None, None),
        ],
        [
            Denominazione(GRUPPO + "33", date(1996, 5, 9), date(2001, 5, 29), "Lega Nord per la Padania indipendente", "LNPI"),
            Denominazione(GRUPPO + "33", date(2001, 5, 30), None, "Lega Padana", "LP"),
        ],
    )
    senato.scrivi(cartella / "senato_14.json", leg)
    senato.scrivi(cartella / "senato_persone.json", persone)


def test_carica_senato(conn, tmp_path):
    scrivi_file(tmp_path)
    db.crea_schema(conn)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO legge (urn, tipo, numero, data, titolo, link_normattiva, stato) VALUES (%s, 'legge', '3', %s, 'Sirchia', '', 'vigente')",
            (SIRCHIA, date(2003, 1, 16)),
        )
    conn.commit()
    for _ in range(2):  # la seconda volta non deve creare doppioni
        rapporto = carica_senato(conn, tmp_path)

    with conn.cursor() as cur:
        cur.execute("SELECT id, urn, iniziativa, numero_legge FROM iter")
        assert cur.fetchall() == [("senato:100", SIRCHIA, "governativa", 3)]
        cur.execute("SELECT id, ramo, progressivo FROM fase_iter ORDER BY progressivo")
        assert cur.fetchall() == [("senato:2122-BIS", "camera", 1), ("senato:1271", "senato", 2)]
        cur.execute("SELECT f.nome, f.tipo, p.cognome FROM firmatario f LEFT JOIN parlamentare p ON p.id = f.parlamentare_id ORDER BY f.nome")
        assert cur.fetchall() == [
            ("Pres. Consiglio Silvio Berlusconi (Gov. Berlusconi-II)", "governativa", None),
            ("Sen. Bianchi", "parlamentare", "Bianchi"),
        ]
        cur.execute("SELECT id, tipo, cardinality(voti_favorevoli), cardinality(voti_astenuti) FROM votazione ORDER BY id")
        assert cur.fetchall() == [("senato:14/1", "finale", 2, 1), ("senato:14/2", "emendamento", 0, 0)]
        cur.execute("SELECT count(*), count(*) FILTER (WHERE nome IS NULL) FROM parlamentare")
        assert cur.fetchone() == (4, 1)
        cur.execute("SELECT nome, sigla FROM gruppo WHERE id = 'senato:33'")
        assert cur.fetchone() == ("Lega Padana", "LP")
        cur.execute(
            "SELECT gruppo_id, favorevoli, contrari, astenuti FROM voto_gruppo WHERE votazione_id = 'senato:14/1' "
            "ORDER BY gruppo_id NULLS LAST"
        )
        # Il senatore 2 conta nel gruppo 40, quello in cui era il giorno del voto; il 99 non ha gruppo.
        assert cur.fetchall() == [("senato:33", 1, 0, 0), ("senato:40", 1, 1, 0), (None, 0, 0, 1)]
    testo = rapporto.testo()
    assert "collegati a una legge di Normattiva: 1 (non trovati: 0)" in testo
    assert "non caricate): 7" in testo
    assert "Spazio: database" in testo
