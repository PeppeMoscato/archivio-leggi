"""Aggiornamento settimanale: estrazione con un client finto (offline) e caricamento su Postgres (con `TEST_DATABASE_URL`)."""

import json
import os
import zipfile
from datetime import date

import pytest
from normattiva import AttoTrovato, EstremiAtto, NormattivaError, NotFoundError, PubblicazioneGazzetta

from archivio import aggiornamento
from archivio.catalogo import atto_da_ricerca
from archivio.modelli import Atto, Nota, Riferimento
from archivio.pipeline import carica, leggi_atti
from fixture_export import aggiornamento as nota_export
from fixture_export import articolo, metadati, scrivi_export
from test_premesse import DL_223_2006

DAL, AL = date(2026, 10, 16), date(2026, 10, 30)
DL_100 = "urn:nir:stato:decreto.legge:2026-09-01;100"
DL_150 = "urn:nir:stato:decreto.legge:2026-10-20;150"
LEGGE_200 = "urn:nir:stato:legge:2026-10-25;200"
SIRCHIA = "urn:nir:stato:legge:2003-01-16;3"
LEGGE_2010 = "urn:nir:stato:legge:2010-02-01;7"
DL_90 = "urn:nir:stato:decreto.legge:2026-08-01;90"
LEGGE_180 = "urn:nir:stato:legge:2026-09-25;180"
CAD = "urn:nir:stato:decreto.legislativo:2005-03-07;82"
LEGGE_210 = "urn:nir:stato:legge:2026-10-28;210"


def trovato(denominazione, emanazione, numero, pubblicazione, codice, titolo="Titolo"):
    return AttoTrovato(EstremiAtto(denominazione, emanazione, numero), PubblicazioneGazzetta(pubblicazione, 1, codice), titolo)


# Il flusso degli atti aggiornati: anche tipi fuori perimetro e atti prima del 1990.
MODIFICATI = [
    trovato("LEGGE", date(2003, 1, 16), "3", date(2003, 1, 20), "003G0007", "Sirchia"),
    trovato("LEGGE", date(2010, 2, 1), "7", date(2010, 2, 3), "010G0007", "Senza export"),
    trovato("DECRETO LEGISLATIVO", date(2005, 3, 7), "82", date(2005, 5, 16), "005G0104", "CAD, ultima versione vuota"),
    trovato("DECRETO DEL PRESIDENTE DELLA REPUBBLICA", date(2001, 1, 5), "5", date(2001, 1, 9), "001G0005"),
    trovato("LEGGE", date(1985, 6, 1), "200", date(1985, 6, 5), "085G0200", "Prima del 1990"),
]
# I cataloghi del 2026: un D.L. nella finestra di conversione, uno nuovo, la legge che converte il primo, una legge vecchia.
CATALOGO_2026 = [
    trovato("DECRETO-LEGGE", date(2026, 9, 1), "100", date(2026, 9, 1), "26G00100", "Misure urgenti"),
    trovato("DECRETO-LEGGE", date(2026, 10, 20), "150", date(2026, 10, 21), "26G00150", "Altre misure urgenti"),
    trovato("LEGGE", date(2026, 10, 25), "200", date(2026, 10, 27), "26G00200",
            "Conversione in legge, con modificazioni, del decreto-legge 1 settembre 2026, n. 100, recante misure urgenti"),
    trovato("LEGGE", date(2026, 3, 1), "50", date(2026, 3, 5), "26G00050", "Fuori finestra"),
]


def storia(urn, denominazione, numero, giorno, **campi):
    return {"cartella": urn.rsplit(":", 1)[1].replace(";", "_"),
            "metadati": metadati(urn, denominazione, numero, giorno, **campi),
            "versioni": [None], "articoli": [articolo("1", giorno)]}


STORIE = {
    SIRCHIA: storia(SIRCHIA, "LEGGE", "3", "2003-01-16", aggiornamenti=[
        nota_export("La L. 25 ottobre 2026, n. 200 ha disposto (con l'art. 1, comma 1) la modifica dell'art. 51.", "26G00200", "20261027")]),
    DL_100: storia(DL_100, "DECRETO-LEGGE", "100", "2026-09-01"),
    DL_150: storia(DL_150, "DECRETO-LEGGE", "150", "2026-10-20"),
    LEGGE_200: storia(LEGGE_200, "LEGGE", "200", "2026-10-25"),
    CAD: storia(CAD, "DECRETO LEGISLATIVO", "82", "2005-03-07"),
}


class ClientFinto:
    def __init__(self):
        self.export = []
        self.giorni = []
        self.testi = []

    def atti_aggiornati(self, dal, al):
        self.giorni.append((dal, al))
        return iter(MODIFICATI if dal == DAL else [])

    def start_export(self, **criteri):
        self.export.append(criteri)
        if criteri.get("numero") == "7":
            raise NormattivaError("export in errore")
        scelte = [
            urn for urn in STORIE
            if urn.split(":")[3] == criteri["denominazione"].lower().replace("-", ".").replace(" ", ".")
            and urn.split(":")[4].startswith(str(criteri["anno"]))
            and (criteri.get("numero") is None or urn.endswith(";" + criteri["numero"]))
        ]

        class Export:
            def wait(self, timeout):
                return None

            def save(self, percorso):
                scrivi_export(percorso, [STORIE[urn] for urn in scelte])
                if CAD in scelte:  # come il D.Lgs. 82/2005 nella prova del 30/10/2026
                    with zipfile.ZipFile(percorso, "a") as archivio:
                        archivio.writestr(f"{STORIE[CAD]['cartella']}/{STORIE[CAD]['cartella']}_VIGENZA_2026-04-21_V2.json", "")
                return percorso

        return Export()

    def dettaglio(self, urn, vigenza=None):
        self.testi.append(urn)
        return type("Risposta", (), {"testo_html": DL_223_2006})()


@pytest.fixture
def cataloghi(monkeypatch):
    monkeypatch.setattr("archivio.pipeline.time.sleep", lambda secondi: None)  # pausa fra due tentativi di export
    def catalogo(client, denominazione, anno):
        trovati = [atto_da_ricerca(t) for t in CATALOGO_2026 if t.estremi.denominazione == denominazione and t.estremi.data.year == anno]
        return {a.urn: a for a in trovati}

    monkeypatch.setattr(aggiornamento, "catalogo", catalogo)


def test_estrai_aggiornamento(tmp_path, cataloghi):
    client = ClientFinto()
    rapporto = aggiornamento.estrai_aggiornamento(client, DAL, AL, tmp_path, pausa=0)
    atti = {a.urn: a for a in leggi_atti(tmp_path)}

    # Un giorno alla volta, dal 16 al 29 ottobre (il 30 è l'ultimo giorno della finestra).
    assert len(client.giorni) == 14 and client.giorni[-1] == (date(2026, 10, 29), AL)
    # Modificati nel perimetro e atti degli ultimi 90 giorni; senza export (abrogato None) la L. 7/2010; il CAD ha
    # l'ultima versione vuota e il caricamento non lo riscrive se è già nel database.
    assert set(atti) == {SIRCHIA, DL_100, DL_150, LEGGE_200, LEGGE_2010, CAD}
    assert atti[LEGGE_2010].abrogato is None
    assert atti[CAD].export_completo is False and atti[SIRCHIA].export_completo is True
    assert atti[SIRCHIA].note[0].riferimenti[0].codice == "26G00200"
    assert atti[DL_100].abrogato is False
    # Gruppi piccoli: un export per atto, con le coordinate dell'atto.
    assert {(c["denominazione"], c["anno"], c.get("numero")) for c in client.export} >= {("LEGGE", 2003, "3"), ("DECRETO-LEGGE", 2026, "100")}
    # Premesse dei D.L. e D.Lgs. degli ultimi 90 giorni, non delle leggi.
    assert client.testi == [DL_100, DL_150]
    premesse = [json.loads(r) for r in (tmp_path / aggiornamento.FILE_PREMESSE).read_text().splitlines()]
    assert [p["urn"] for p in premesse] == [DL_100, DL_150] and all(p["motivazioni"] for p in premesse)
    testo = rapporto.testo()
    assert "atti modificati nel flusso di Normattiva: 5, nel perimetro: 3" in testo
    assert "atti pubblicati negli ultimi 90 giorni: 3" in testo
    assert "2010 LEGGE: senza export completo 1 su 1" in testo
    assert "2005 DECRETO LEGISLATIVO: senza export completo 1 su 1, di cui con le versioni recenti vuote 1" in testo
    assert "Atti riesportati: 4 su 6" in testo


def test_gruppi_grandi_con_export_dell_anno(tmp_path, cataloghi, monkeypatch):
    monkeypatch.setattr(aggiornamento, "SOGLIA_ANNO", 1)
    client = ClientFinto()
    aggiornamento.estrai_aggiornamento(client, DAL, AL, tmp_path, pausa=0)
    # Il D.L. 2026 ha due atti: un export solo, per l'anno intero.
    assert {"denominazione": "DECRETO-LEGGE", "anno": 2026} in [
        {k: v for k, v in c.items() if k in ("denominazione", "anno", "numero")} for c in client.export
    ]
    assert {a.urn for a in leggi_atti(tmp_path)} >= {DL_100, DL_150}


def test_finestra():
    assert aggiornamento.finestra(14, AL) == (DAL, AL)
    with pytest.raises(ValueError):
        aggiornamento.finestra(0, AL)


# --- caricamento su Postgres --------------------------------------------------

DSN = os.environ.get("TEST_DATABASE_URL")


class ClientSenzaRisposte:
    def dettaglio_da_gazzetta(self, codice, giorno):
        raise NotFoundError("assente")


def scrivi(cartella, atti, premesse):
    cartella.mkdir()
    with (cartella / aggiornamento.FILE_ATTI).open("w", encoding="utf-8") as file:
        for atto in atti:
            file.write(json.dumps(atto.in_json()) + "\n")
    with (cartella / aggiornamento.FILE_PREMESSE).open("w", encoding="utf-8") as file:
        for riga in premesse:
            file.write(json.dumps(riga) + "\n")


@pytest.mark.db
@pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL non impostata")
def test_carica_aggiornamento(conn, tmp_path):
    def dl(urn, numero, giorno, gazzetta, codice):
        return Atto(urn, "decreto-legge", numero, giorno, "Misure urgenti", gazzetta_data=gazzetta, gazzetta_codice=codice, abrogato=False)

    conversione_90 = Atto(LEGGE_180, "legge", "180", date(2026, 9, 25),
                          "Conversione in legge del decreto-legge 1 agosto 2026, n. 90, recante misure urgenti",
                          gazzetta_data=date(2026, 9, 30), gazzetta_codice="26G00180", abrogato=False)
    sirchia = Atto(SIRCHIA, "legge", "3", date(2003, 1, 16), "Sirchia", gazzetta_data=date(2003, 1, 20), gazzetta_codice="003G0007",
                   abrogato=False)
    abrogata = Atto(LEGGE_2010, "legge", "7", date(2010, 2, 1), "Abrogata", gazzetta_data=date(2010, 2, 3), abrogato=True,
                    data_abrogazione=date(2020, 1, 1))
    # Il database dopo il caricamento completo.
    carica(conn, [dl(DL_90, "90", date(2026, 8, 1), date(2026, 8, 1), "26G00090"), conversione_90,
                  dl(DL_100, "100", date(2026, 9, 1), date(2026, 9, 1), "26G00100"), sirchia, abrogata], ClientSenzaRisposte())

    modifica = Nota("La L. 25 ottobre 2026, n. 200 ha disposto (con l'art. 1, comma 1) la modifica dell'art. 51.",
                    (Riferimento("26G00200", date(2026, 10, 27)),))
    legge_200 = Atto(LEGGE_200, "legge", "200", date(2026, 10, 25),
                     "Conversione in legge, con modificazioni, del decreto-legge 1 settembre 2026, n. 100, recante misure urgenti",
                     gazzetta_data=date(2026, 10, 27), gazzetta_codice="26G00200", abrogato=False)
    scrivi(tmp_path / "dati", [
        # Il flusso porta una ripubblicazione: in Gazzetta resta la pubblicazione originale.
        dl(DL_100, "100", date(2026, 9, 1), date(2026, 10, 28), "26G00999"),
        dl(DL_90, "90", date(2026, 8, 1), date(2026, 8, 1), "26G00090"),
        legge_200,
        Atto(SIRCHIA, "legge", "3", date(2003, 1, 16), "Sirchia", gazzetta_data=date(2003, 1, 20), gazzetta_codice="003G0007",
             abrogato=False, note=[modifica]),
        # Senza export: quella già nel database resta com'è, quella nuova entra dal catalogo.
        Atto(LEGGE_2010, "legge", "7", date(2010, 2, 1), "Abrogata", gazzetta_data=date(2010, 2, 3)),
        Atto(LEGGE_210, "legge", "210", date(2026, 10, 28), "Appena pubblicata", gazzetta_data=date(2026, 10, 29)),
    ], [{"urn": DL_100, "tipo": "decreto-legge", "motivazioni": ["Ritenuta la straordinaria necessità ed urgenza"],
         "citazioni": [], "proposta": None, "deleghe": [], "fonte_url": "https://www.normattiva.it/"}])

    rapporto = aggiornamento.carica_aggiornamento(conn, tmp_path / "dati", ClientSenzaRisposte())
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM legge")
        assert cur.fetchone() == (7,)
        cur.execute("SELECT urn, stato, data_abrogazione FROM legge WHERE urn IN (%s, %s) ORDER BY urn", (LEGGE_2010, LEGGE_210))
        assert cur.fetchall() == [(LEGGE_2010, "abrogata", date(2020, 1, 1)), (LEGGE_210, "vigente", None)]
        cur.execute("SELECT gazzetta_data, gazzetta_codice FROM legge WHERE urn = %s", (DL_100,))
        assert cur.fetchone() == (date(2026, 9, 1), "26G00100")
        cur.execute("SELECT urn_destinazione, urn_origine FROM relazione_normativa WHERE tipo = 'converte' ORDER BY 1")
        # La conversione nuova dal titolo della legge nuova; quella vecchia resta, anche se la legge non è nel giro.
        assert cur.fetchall() == [(DL_90, LEGGE_180), (DL_100, LEGGE_200)]
        cur.execute("SELECT urn_origine, tipo FROM relazione_normativa WHERE urn_destinazione = %s", (SIRCHIA,))
        assert cur.fetchall() == [(LEGGE_200, "modifica")]
        cur.execute("SELECT urn FROM premessa")
        assert cur.fetchall() == [(DL_100,)]
    testo = rapporto.testo()
    assert "Atti caricati: 5" in testo and "Premesse caricate: 1" in testo
    assert "nuovi: 2 (di cui senza export, solo dal catalogo: 1); senza export e lasciati come erano: 1" in testo
