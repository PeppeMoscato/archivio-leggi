"""Prove offline dell'estrazione dal Senato e delle regole di caricamento (Task 1.2)."""

import re
from datetime import date

import pytest

from archivio import senato
from archivio.parlamento import IndiceLeggi, elenchi_voti, riga_iter, risolvi_urn
from archivio.senato import DDL, SENATORE, Fase, Iniziativa, Legislatura, Votazione

# --- etichette delle votazioni (testi reali dalla sonda del 27/10/2026) ---------------


@pytest.mark.parametrize(
    ("etichetta", "numero"),
    [
        ("Disegno di legge n. 3660. Votazione finale", "3660"),
        ("DDL n. 1306-B. Votazione finale", "1306-B"),
        ("DDL n. 2542. Votazione questione di fiducia", "2542"),
        ("d.d.l. 54-bis. Em. 1.1", "54-BIS"),
        ("Seduta pomeridiana. Mozione n. 12", None),
    ],
)
def test_numero_ddl_da_etichetta(etichetta, numero):
    assert senato.numero_ddl_da_etichetta(etichetta) == numero


@pytest.mark.parametrize(
    ("etichetta", "tipo"),
    [
        ("DDL n. 2542. Votazione questione di fiducia", "fiducia"),
        ("Mozione di sfiducia al Ministro", "altro"),
        ("Disegno di legge n. 3660. Votazione finale", "finale"),
        ("DDL n. 1306. Votazione del disegno di legge nel suo complesso", "finale"),
        ("DDL n. 1306. Questione pregiudiziale", "pregiudiziale"),
        ("DDL n. 1306. Emendamento 3.100", "emendamento"),
        ("DDL n. 1306. Em. 3.100", "emendamento"),
        ("DDL n. 1306. Articolo 3", "articolo"),
        ("DDL n. 1306. Art. 3", "articolo"),
        ("Inversione dell'ordine del giorno", "altro"),
    ],
)
def test_tipo_votazione(etichetta, tipo):
    assert senato.tipo_votazione(etichetta) == tipo


def test_natura_e_iniziativa():
    assert senato.natura("di conversione di decreto-legge") == "conversione di decreto-legge"
    assert senato.natura("Costituzionale") == "costituzionale"
    assert senato.iniziativa(["Parlamentare", "Governativa"]) == "governativa"
    assert senato.iniziativa(["Parlamentare", None]) == "parlamentare"
    assert senato.iniziativa(["CNEL"]) == "CNEL"
    assert senato.iniziativa([]) is None


def fase(numero: str, ramo: str = "S", progressivo: int = 1, id_ddl: str = "100", **campi) -> Fase:
    base = dict(
        id=DDL + numero, id_ddl=id_ddl, progressivo=progressivo, ramo=ramo, numero=numero, titolo=f"Titolo {numero}",
        natura="ordinaria", data_presentazione=date(2007, 1, 10), stato=None, data_stato=None,
    )
    return Fase(**(base | campi))


def votazione(etichetta: str, oggetto: list[str] | None = None, **campi) -> Votazione:
    base = dict(
        id="http://dati.senato.it/votazione/15/1/1", descrizione=etichetta, tipo_votazione="elettronica", esito="approvato",
        presenti=300, votanti=290, favorevoli=2, contrari=1, astenuti=0, maggioranza=146, data=date(2007, 5, 3),
        fasi_oggetto=oggetto or [],
    )
    return Votazione(**(base | campi))


def test_collega_oggetto_poi_etichetta():
    fasi = {f.id: f for f in [fase("1271"), fase("1271-B", progressivo=3)]}
    per_numero = {senato.numero_senza_ramo(f.numero): f.id for f in fasi.values()}
    assert senato.numero_senza_ramo("S.1271-b") == "1271-B"
    # L'oggetto della trattazione vale sull'etichetta.
    assert senato.collega(votazione("DDL n. 1271-B. Votazione finale", [DDL + "1271"]), fasi, per_numero) == DDL + "1271"
    # Oggetto su un ddl mai diventato legge: fuori, anche se l'etichetta cita un numero noto.
    assert senato.collega(votazione("DDL n. 1271. Em. 1.1", [DDL + "9999"]), fasi, per_numero) is None
    # Senza oggetto, il numero nell'etichetta.
    assert senato.collega(votazione("DDL n. 1271-B. Votazione finale"), fasi, per_numero) == DDL + "1271-B"
    assert senato.collega(votazione("DDL n. 4000. Votazione finale"), fasi, per_numero) is None


# --- paginazione per chiave ----------------------------------------------------------


class SparqlFinto:
    """Risponde come Virtuoso: ordina per chiave, applica il filtro `>=` e tronca a LIMIT."""

    def __init__(self, righe: list[dict[str, str]], chiave: str):
        self.righe = sorted(righe, key=lambda r: r[chiave])
        self.chiave = chiave
        self.query: list[str] = []

    def select(self, query: str) -> list[dict[str, str]]:
        self.query.append(query)
        assert "%DOPO%" not in query and f"ORDER BY STR(?{self.chiave})" in query
        dopo = re.search(r'>= "([^"]*)"', query)
        limite = int(re.search(r"LIMIT (\d+)", query).group(1))
        return [r for r in self.righe if not dopo or r[self.chiave] >= dopo.group(1)][:limite]


def test_scorri_non_spezza_le_chiavi(monkeypatch):
    monkeypatch.setattr(senato, "LIMITE_RIGHE", 3)
    righe = [{"k": k, "v": str(i)} for i, k in enumerate("aabbcdde")]
    finto = SparqlFinto(righe, "k")
    letti = list(senato.scorri(finto, "SELECT ?k ?v WHERE { ?x ?k ?v %DOPO% }", "k"))
    assert sorted((r["k"], r["v"]) for r in letti) == sorted((r["k"], r["v"]) for r in righe)
    assert len(finto.query) > 1


def test_scorri_troppe_righe_per_una_chiave(monkeypatch):
    monkeypatch.setattr(senato, "LIMITE_RIGHE", 2)
    finto = SparqlFinto([{"k": "a"}] * 3, "k")
    with pytest.raises(RuntimeError):
        list(senato.scorri(finto, "SELECT ?k WHERE { %DOPO% }", "k"))


def test_estrai_voti_a_gruppi(monkeypatch):
    monkeypatch.setattr(senato, "VOTAZIONI_PER_RICHIESTA", 2)
    votazioni = [votazione("x", id=f"http://dati.senato.it/votazione/{i}") for i in range(3)]

    class Finto:
        richieste = 0

        def select(self, query):
            Finto.richieste += 1
            ids = re.findall(r"<(http://dati.senato.it/votazione/\d+)>", query)
            return [{"v": v, "p": "http://dati.senato.it/osr/favorevole", "s": SENATORE + "274"} for v in ids] + [
                {"v": ids[0], "p": "http://dati.senato.it/osr/astenuto", "s": SENATORE + "12"}
            ]

    senato.estrai_voti(Finto(), votazioni)
    assert Finto.richieste == 2
    assert votazioni[0].voti == {"favorevoli": ["274"], "astenuti": ["12"]}
    assert votazioni[1].voti == {"favorevoli": ["274"]}


# --- file intermedi ---------------------------------------------------------------------


def test_json_andata_e_ritorno(tmp_path):
    leg = Legislatura(
        15,
        [fase("1271", numeri_legge=[3], date_legge=[date(2007, 1, 16)], data_stato=date(2006, 12, 20))],
        [Iniziativa(DDL + "1271", "Sen. Rossi", "Parlamentare", True, SENATORE + "274")],
        [votazione("DDL n. 1271. Votazione finale", [DDL + "1271"], voti={"favorevoli": ["274"]})],
        votazioni_scartate=4,
    )
    senato.scrivi(tmp_path / "senato_15.json", leg)
    assert senato.leggi_legislatura(tmp_path / "senato_15.json") == leg
    persone = senato.Persone(
        [senato.Senatore(SENATORE + "274", "Mario", "Rossi")],
        [senato.Adesione(SENATORE + "274", senato.GRUPPO + "33", date(2006, 5, 1), None, "Presidente")],
        [senato.Denominazione(senato.GRUPPO + "33", date(2006, 5, 1), date(2008, 4, 28), "Lega Nord", "LNP")],
    )
    senato.scrivi(tmp_path / "senato_persone.json", persone)
    assert senato.leggi_persone(tmp_path / "senato_persone.json") == persone


def test_per_iter_ordina_le_fasi():
    fasi = [fase("2122-BIS-B", "C", 3), fase("1271", "S", 2), fase("2122-BIS", "C", 1), fase("10", id_ddl="200")]
    gruppi = senato.per_iter(fasi)
    assert [f.numero for f in gruppi["100"]] == ["2122-BIS", "1271", "2122-BIS-B"]
    assert list(gruppi) == ["100", "200"]


# --- collegamento con Normattiva -------------------------------------------------------

INDICE = IndiceLeggi.da_righe([
    ("urn:nir:stato:legge:2003-01-16;3", "legge", "3", date(2003, 1, 16)),
    ("urn:nir:stato:legge:2002-12-27;289", "legge", "289", date(2002, 12, 27)),
    ("urn:nir:stato:legge.costituzionale:2001-10-18;3", "legge costituzionale", "3", date(2001, 10, 18)),
    ("urn:nir:stato:legge:2001-03-05;3", "legge", "3", date(2001, 3, 5)),
])


def test_risolvi_urn():
    # Numero e data esatti.
    assert risolvi_urn("legge", [3], [date(2003, 1, 16)], None, INDICE) == ("urn:nir:stato:legge:2003-01-16;3", 3, date(2003, 1, 16))
    # Data della fonte sbagliata di qualche giorno: basta l'anno.
    assert risolvi_urn("legge", [3], [date(2003, 1, 20)], None, INDICE)[0] == "urn:nir:stato:legge:2003-01-16;3"
    # Più numeri nella fonte: vince quello che esiste.
    assert risolvi_urn("legge", [999, 289], [date(2002, 12, 27)], None, INDICE)[1] == 289
    # Senza data: anno dell'approvazione definitiva o il successivo.
    assert risolvi_urn("legge", [3], [], date(2002, 12, 20), INDICE)[0] == "urn:nir:stato:legge:2003-01-16;3"
    # Il tipo conta: la legge costituzionale n. 3 del 2001 non è la legge n. 3 del 2001.
    assert risolvi_urn("legge costituzionale", [3], [date(2001, 10, 18)], None, INDICE)[0].startswith("urn:nir:stato:legge.costituzionale")
    assert risolvi_urn("legge", [7], [date(2005, 1, 1)], None, INDICE) == (None, 7, date(2005, 1, 1))


def test_riga_iter():
    fasi = [
        fase("2122-BIS", "C", 1, data_presentazione=date(2001, 9, 1)),
        fase("1271", "S", 2, titolo="Titolo definitivo", numeri_legge=[3], date_legge=[date(2003, 1, 16)], data_stato=date(2002, 12, 20)),
    ]
    iniziative = [Iniziativa(fasi[0].id, "Pres. Consiglio", "Governativa", True, None)]
    riga = riga_iter(14, fasi, iniziative, INDICE)
    assert (riga.id, riga.urn, riga.titolo, riga.iniziativa) == ("senato:100", "urn:nir:stato:legge:2003-01-16;3", "Titolo definitivo", "governativa")
    assert (riga.data_presentazione, riga.data_approvazione, riga.numero_legge) == (date(2001, 9, 1), date(2002, 12, 20), 3)
    assert riga.fonte_url == "https://www.senato.it/leg/14/BGT/Schede/Ddliter/100.htm"


def test_elenchi_voti():
    v = votazione("x", voti={"favorevoli": ["274", "12"], "contrari": ["5"], "astenuti": ["404"]})
    assert elenchi_voti(v, {"senato:274": 1, "senato:12": 2, "senato:5": 3}) == ([1, 2], [3], [], 1)
