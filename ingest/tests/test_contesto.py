"""Premesse: estrazione con un client finto (offline) e caricamento su Postgres (con `TEST_DATABASE_URL`)."""

import json
import os
from datetime import date

import pytest
from normattiva import AmbiguityError, ConnectionError, NotFoundError

from archivio import contesto
from archivio.modelli import Atto
from archivio.pipeline import carica
from test_premesse import DL_223_2006, DLGS, L_76_2016

DL = Atto("urn:nir:stato:decreto.legge:2006-07-04;223", "decreto-legge", "223", date(2006, 7, 4), "Bersani",
          gazzetta_data=date(2006, 7, 4), gazzetta_codice="006G0241")
DLGS_ATTO = Atto("urn:nir:stato:decreto.legislativo:2015-03-04;23", "decreto legislativo", "23", date(2015, 3, 4),
                 "Tutele crescenti", gazzetta_data=date(2015, 3, 6), gazzetta_codice="15G00037")
RIPUBBLICATO = Atto("urn:nir:stato:decreto.legge:2006-08-01;9", "decreto-legge", "9", date(2006, 8, 1), "Ripubblicato",
                    gazzetta_data=date(2006, 8, 1), gazzetta_codice="006G0999")
MANCANTE = Atto("urn:nir:stato:decreto.legge:2006-09-01;10", "decreto-legge", "10", date(2006, 9, 1), "Assente")
LEGGE_DELEGA = Atto("urn:nir:stato:legge:2014-12-10;183", "legge", "183", date(2014, 12, 10), "Jobs Act",
                    gazzetta_data=date(2014, 12, 15), gazzetta_codice="14G00196")


class RispostaFinta:
    def __init__(self, testo_html):
        self.testo_html = testo_html


class ClientFinto:
    def __init__(self, guasti=0):
        self.chiamate = []
        self.guasti = guasti  # le prime chiamate a dettaglio falliscono come un servizio che non risponde

    def dettaglio(self, urn, vigenza=None):
        self.chiamate.append((urn, vigenza))
        if self.guasti:
            self.guasti -= 1
            raise ConnectionError("il servizio non risponde: Server disconnected without sending a response.")
        if urn == RIPUBBLICATO.urn:
            raise AmbiguityError("due atti")
        if urn == MANCANTE.urn:
            raise NotFoundError("assente")
        return RispostaFinta({DL.urn: DL_223_2006, DLGS_ATTO.urn: DLGS}[urn])

    def dettaglio_da_gazzetta(self, codice, giorno):
        self.chiamate.append((codice, giorno))
        return RispostaFinta(L_76_2016)


def test_estrai_premesse(tmp_path, monkeypatch):
    cataloghi = {"DECRETO-LEGGE": [DL, RIPUBBLICATO, MANCANTE], "DECRETO LEGISLATIVO": [DLGS_ATTO]}
    monkeypatch.setattr(contesto, "catalogo", lambda client, denominazione, anno: {a.urn: a for a in cataloghi[denominazione]})
    client = ClientFinto(guasti=2)  # il primo atto riesce al terzo tentativo
    rapporto = contesto.estrai_premesse(client, [2006], tmp_path, pausa=0, attese=(0, 0))
    righe = [json.loads(r) for r in (tmp_path / "premesse_2006.jsonl").read_text().splitlines()]
    assert [r["urn"] for r in righe] == [DL.urn, DLGS_ATTO.urn]
    assert righe[0]["motivazioni"][0].startswith("Ritenuta la straordinaria necessità ed urgenza di rafforzare")
    assert righe[0]["deleghe"] == []
    assert righe[0]["fonte_url"].startswith("https://www.normattiva.it/")
    assert righe[1]["deleghe"][0]["urn"] == LEGGE_DELEGA.urn
    # URN ambiguo: si passa dalla Gazzetta; atto assente: si conta e si va avanti.
    assert ("006G0999", date(2006, 8, 1)) in client.chiamate
    assert "testo non letto 1" in rapporto.testo() and "senza premessa 1" in rapporto.testo()


def test_servizio_che_non_risponde_si_arrende():
    client = ClientFinto(guasti=3)
    with pytest.raises(ConnectionError):
        contesto.testo_originale(client, DL, attese=(0, 0))
    assert len(client.chiamate) == 3


DSN = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.db
@pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL non impostata")
def test_carica_premesse_e_ricarica_normattiva(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(contesto, "catalogo", lambda client, denominazione, anno: {
        a.urn: a for a in {"DECRETO-LEGGE": [DL], "DECRETO LEGISLATIVO": [DLGS_ATTO]}[denominazione]
    })
    contesto.estrai_premesse(ClientFinto(), [2006], tmp_path, pausa=0, attese=())
    righe = contesto.leggi_premesse(tmp_path)
    righe.append({**righe[0], "urn": "urn:nir:stato:decreto.legge:1999-01-01;1"})  # non nell'archivio: si scarta
    carica(conn, [DL, DLGS_ATTO, LEGGE_DELEGA])
    for _ in range(2):  # la seconda volta non deve creare doppioni
        rapporto = contesto.carica_premesse(conn, righe)
    # Ricaricare l'archivio Normattiva non cancella le relazioni delega.
    carica(conn, [DL, DLGS_ATTO, LEGGE_DELEGA])
    with conn.cursor() as cur:
        cur.execute("SELECT urn, array_length(motivazioni, 1), proposta IS NOT NULL FROM premessa ORDER BY urn")
        assert cur.fetchall() == [(DL.urn, 2, True), (DLGS_ATTO.urn, None, True)]
        cur.execute("SELECT urn_origine, urn_destinazione, data, nota FROM relazione_normativa WHERE tipo = 'delega'")
        ((origine, destinazione, giorno, nota),) = cur.fetchall()
    assert (origine, destinazione, giorno) == (LEGGE_DELEGA.urn, DLGS_ATTO.urn, date(2014, 12, 15))
    assert nota.startswith("Vista la legge 10 dicembre 2014, n. 183")
    assert "Premesse caricate: 2 (atti non in archivio: 1)" in rapporto.testo()


@pytest.mark.db
@pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL non impostata")
def test_carica_premesse_urn_senza_data(conn):
    carica(conn, [DLGS_ATTO, LEGGE_DELEGA])
    riga = {"urn": DLGS_ATTO.urn, "tipo": "decreto legislativo", "motivazioni": [], "citazioni": [], "proposta": None,
            "fonte_url": "https://www.normattiva.it/", "deleghe": [
                {"urn": "urn:nir:stato:legge:2014;183", "articolo": "1", "citazione": "della citata legge n. 183 del 2014"},
                {"urn": LEGGE_DELEGA.urn, "articolo": None, "citazione": "Vista la legge 10 dicembre 2014, n. 183"},
            ]}
    contesto.carica_premesse(conn, [riga])
    with conn.cursor() as cur:
        cur.execute("SELECT urn_origine, articolo_origine FROM relazione_normativa WHERE tipo = 'delega'")
        assert cur.fetchall() == [(LEGGE_DELEGA.urn, "1")]
