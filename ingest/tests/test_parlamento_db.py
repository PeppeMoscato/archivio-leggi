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


# --- Camera ---------------------------------------------------------------------------


def scrivi_file_camera(cartella):
    from archivio import camera
    from archivio.camera import ATTO, GRUPPO, VOTAZIONE, AdesioneCamera, Deputato, GruppoCamera, LegislaturaCamera, PersoneCamera
    from test_camera import legislatura_x, votazione

    persone = PersoneCamera(
        [Deputato("1", "MARIO", "ROSSI"), Deputato("2", "LUCIA", "BIANCHI"), Deputato("35330", "GIOVANNI", "GORIA")],
        [AdesioneCamera("1", GRUPPO + "gr139", date(2001, 6, 4), None), AdesioneCamera("2", GRUPPO + "gr140", date(2001, 6, 4), None)],
        [GruppoCamera(GRUPPO + "gr139", 14, "ALLEANZA NAZIONALE", "AN", date(2001, 6, 4), date(2006, 4, 27))],
        [],
    )
    leg14 = LegislaturaCamera(
        14,
        [],
        [],
        [
            votazione("Votazione finale DDL n.2122-BIS", id=VOTAZIONE + "vs14_120_001", tipo_fonte="Finale atto Camera", finale=True,
                      favorevoli=1, contrari=1, astenuti=0, voti={"favorevoli": ["1"], "contrari": ["2", "77"]}),
            votazione("Votazione Emendamento 2.2 DDL n.2122-BIS", id=VOTAZIONE + "vs14_115_098", tipo_fonte="Emendamento",
                      segreta=True, approvato=False),
            votazione("Votazione finale DDL n.9999", id=VOTAZIONE + "vs14_200_001", numero="9999"),
        ],
        votazioni_scartate=5,
        fasi_senato=["2122-BIS"],
    )
    leg14.leggi.append(camera.LeggeCamera(camera.LEGGE + "L2003_3", SIRCHIA, 3, date(2003, 1, 16), "Sirchia", "Ordinaria",
                                          [ATTO + "ac14_2122-quater"]))
    camera.scrivi(cartella / "camera_persone.json", persone)
    camera.scrivi(cartella / "camera_14.json", leg14)
    camera.scrivi(cartella / "camera_10.json", legislatura_x())


def test_carica_camera_dopo_il_senato(conn, tmp_path):
    from archivio.parlamento import carica_camera

    scrivi_file(tmp_path)
    scrivi_file_camera(tmp_path)
    db.crea_schema(conn)
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO legge (urn, tipo, numero, data, titolo, link_normattiva, stato) VALUES (%s, 'legge', %s, %s, 't', '', 'vigente')",
            [(SIRCHIA, "3", date(2003, 1, 16)), ("urn:nir:stato:legge:1990-08-07;241", "241", date(1990, 8, 7))],
        )
    conn.commit()
    carica_senato(conn, tmp_path)
    for _ in range(2):  # la seconda volta non deve creare doppioni
        rapporto = carica_camera(conn, tmp_path)
    carica_senato(conn, tmp_path)  # ricaricare il Senato non cancella le votazioni della Camera

    with conn.cursor() as cur:
        cur.execute("SELECT id, fase_id, tipo, esito, voti_favorevoli, cardinality(voti_contrari) FROM votazione WHERE ramo = 'camera'")
        righe = sorted(cur.fetchall())
        cur.execute("SELECT id FROM parlamentare WHERE codice = 'camera:1'")
        (rossi,) = cur.fetchone()
        assert righe == [
            ("camera:vs14_115_098", "senato:2122-BIS", "emendamento", "respinto", [], 0),
            ("camera:vs14_120_001", "senato:2122-BIS", "finale", "approvato", [rossi], 1),
        ]
        cur.execute("SELECT count(*) FROM votazione WHERE ramo = 'senato'")
        assert cur.fetchone() == (2,)
        # Legislatura X: iter dai lavori preparatori della Camera, collegato a Normattiva.
        cur.execute("SELECT id, urn, iniziativa, natura FROM iter WHERE id LIKE 'camera:%'")
        assert cur.fetchall() == [("camera:L1990_241", "urn:nir:stato:legge:1990-08-07;241", "governativa", "ordinaria")]
        cur.execute(
            "SELECT f.numero, fi.nome, fi.primo_firmatario, p.cognome FROM firmatario fi JOIN fase_iter f ON f.id = fi.fase_id "
            "LEFT JOIN parlamentare p ON p.id = fi.parlamentare_id WHERE f.id LIKE 'camera:%' ORDER BY fi.primo_firmatario DESC"
        )
        assert cur.fetchall() == [
            ("C.1913", "GORIA GIOVANNI, Presidente del Consiglio", True, "GORIA"),
            ("C.1913", "GAVA ANTONIO, Ministro dell'interno", False, None),
        ]
        cur.execute("SELECT nome, sigla FROM gruppo WHERE id = 'camera:gr139'")
        assert cur.fetchone() == ("ALLEANZA NAZIONALE", "AN")
        cur.execute("SELECT gruppo_id, favorevoli, contrari FROM voto_gruppo WHERE votazione_id = 'camera:vs14_120_001' ORDER BY 1")
        assert cur.fetchall() == [("camera:gr139", 1, 0), ("camera:gr140", 0, 1)]
    testo = rapporto.testo()
    assert "votazioni su fasi che non sono nel database (Senato non caricato o fase diversa): 1 (es. 9999)" in testo
    assert "deputati non trovati: 1" in testo
    assert "non sono fasi Camera negli iter del Senato: 1 su 1" in testo
    assert "con una data di giuramento diversa: nessuno" not in testo  # nessun governo della Camera nei file di prova
