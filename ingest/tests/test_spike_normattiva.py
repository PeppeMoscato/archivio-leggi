from datetime import date

import pytest

from spike_normattiva import ATTI_DI_PROVA, in_dizionario, primo_riferimento, report


def test_urn_degli_atti_di_prova():
    urn = {atto.nome: str(atto.urn) for atto in ATTI_DI_PROVA}
    assert urn["Legge Sirchia"] == "urn:nir:stato:legge:2003-01-16;3"
    assert urn["Patente a punti"] == "urn:nir:stato:decreto.legislativo:2002-01-15;9"
    assert urn["Reddito di cittadinanza"] == "urn:nir:stato:decreto.legge:2019-01-28;4"
    assert urn["Legge Merloni"] == "urn:nir:stato:legge:1994-02-11;109"
    assert urn["Sicurezza sul lavoro"] == "urn:nir:stato:decreto.legislativo:1994-09-19;626"


def test_in_dizionario_converte_date_e_tuple():
    assert in_dizionario({"giorno": date(2005, 1, 10), "elenco": (1, 2)}) == {"giorno": "2005-01-10", "elenco": [1, 2]}


def test_primo_riferimento():
    export = {
        "atti": [
            {
                "aggiornamenti": [
                    {"riferimenti": [{"gazzetta": {"codice_redazionale": "08G0104", "data": "2008-04-30"}}]}
                ]
            }
        ]
    }
    assert primo_riferimento(export) == ("08G0104", date(2008, 4, 30))
    assert primo_riferimento({"atti": []}) is None


def test_report_con_errori():
    errore = {"passo": "x", "ok": False, "errore": "ConnectionError: servizio non raggiungibile"}
    risultati = {
        "eseguito_il": "2026-10-27",
        "atti": [
            {
                "nome": "Legge Sirchia",
                "urn": "urn:nir:stato:legge:2003-01-16;3",
                "stato_atteso": "vigente",
                "ricerca": errore,
                "classe": errore,
                "dettaglio": errore,
                "export": errore,
            }
        ],
        "conteggi": [
            {"denominazione": "LEGGE", "perimetro": True, "totale": {"ok": True, "dati": 10}, "abrogati": errore, "aggiornati": errore}
        ],
    }
    testo = report(risultati)
    assert "Legge Sirchia" in testo
    assert "| LEGGE | sì | 10 | errore | errore |" in testo


@pytest.mark.rete
def test_dettaglio_legge_sirchia():
    from normattiva import Normattiva

    with Normattiva() as client:
        atto = client.dettaglio(ATTI_DI_PROVA[0].urn)
    assert atto.estremi.numero == "3"
    assert atto.estremi.data == date(2003, 1, 16)


def test_report_con_urn_ambiguo():
    ok = {"ok": True, "dati": "AGGIORNATO"}
    risultati = {
        "eseguito_il": "2026-10-27",
        "atti": [
            {
                "nome": "Reddito di cittadinanza",
                "urn": "urn:nir:stato:decreto.legge:2019-01-28;4",
                "stato_atteso": "RdC abrogato",
                "ricerca": {"ok": True, "dati": []},
                "classe": ok,
                "dettaglio": {
                    "ok": True,
                    "dati": {
                        "ambiguo": True,
                        "candidati": [
                            {"estremi": {}, "gazzetta": {"data": "2019-01-28", "numero": 23, "codice_redazionale": "19G00008"}, "titolo": "Disposizioni urgenti"}
                        ],
                    },
                },
                "export": {"ok": True, "dati": {"atti": [{"abrogato": False, "versioni": ["None"], "aggiornamenti": [{"data": "2019-03-29", "testo": "Modifica", "riferimenti": []}]}]}},
            }
        ],
        "conteggi": [],
    }
    testo = report(risultati)
    assert "URN ambiguo (vedi dettagli)" in testo
    assert "codice 19G00008" in testo
    assert "Primi aggiornamenti — 2019-03-29: Modifica" in testo
