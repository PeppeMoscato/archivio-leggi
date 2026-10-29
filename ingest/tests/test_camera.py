"""Prove offline dell'estrazione dalla Camera e delle sue regole (Task 1.2, parte Camera)."""

import re
from datetime import date

import pytest

from archivio import camera
from archivio.camera import (
    ATTO, GRUPPO, LEGGE, PERSONA, VOTAZIONE, AdesioneCamera, AttoCamera, Deputato, GovernoCamera, GruppoCamera, LeggeCamera,
    LegislaturaCamera, PersoneCamera, VotazioneCamera,
)
from archivio.parlamento import confronta_governi, denominazioni_camera


def votazione(titolo: str, **campi) -> VotazioneCamera:
    base = dict(
        id=VOTAZIONE + "vs14_115_096", titolo=titolo, descrizione=None, tipo_fonte=None, data=date(2002, 3, 19), finale=False,
        fiducia=False, segreta=False, approvato=True, presenti=500, votanti=490, favorevoli=2, contrari=1, astenuti=0,
        maggioranza=246, numero="2122-BIS", fonte_url=None,
    )
    return VotazioneCamera(**(base | campi))


# --- regole pure (testi reali dalla sonda del 27/10/2026) -----------------------------


def test_numero_atto_e_persona():
    assert camera.numero_atto(ATTO + "ac14_2122-bis-b") == "2122-BIS-B"
    assert camera.numero_atto(ATTO + "ac10_1913") == "1913"
    assert camera.numero_atto("http://altro/x") is None
    assert camera.persona("http://dati.camera.it/ocd/deputato.rdf/d305578_17") == "305578"
    assert camera.persona(PERSONA + "35330") == "35330"


def test_data_e_testo():
    assert camera.data_camera("20020114") == date(2002, 1, 14)
    assert camera.data_camera("2002-01-14") == date(2002, 1, 14)
    assert camera.data_camera("") is None
    assert camera.data_camera("2002") is None
    assert camera.testo("sull&#39;&#39;articolo") == "sull''articolo"
    assert camera.testo("dell&amp;#39;articolo") == "dell'articolo"


def test_nome_gruppo_e_denominazioni():
    assert camera.nome_gruppo("ALLEANZA NAZIONALE (AN) (04.06.2001-27.04.2006)", "AN") == "ALLEANZA NAZIONALE"
    assert camera.nome_gruppo("MISTO (19.03.2013-)", None) == "MISTO"
    assert camera.fino_a("gia' ITALIA VIVA (IV) fino a 31.07.2022") == date(2022, 7, 31)
    gruppo = GruppoCamera(
        GRUPPO + "gr729", 16, "FUTURO E LIBERTA' PER IL TERZO POLO", "FLPTP", date(2010, 7, 30), date(2013, 3, 14),
        [("FUTURO E LIBERTA' PER L'ITALIA", "FLI", date(2011, 4, 25)), ("FUTURO E LIBERTA'. PER L'ITALIA", "FL", date(2010, 9, 8))],
    )
    assert denominazioni_camera(gruppo) == [
        (date(2010, 7, 30), date(2010, 9, 8), "FUTURO E LIBERTA'. PER L'ITALIA", "FL"),
        (date(2010, 9, 9), date(2011, 4, 25), "FUTURO E LIBERTA' PER L'ITALIA", "FLI"),
        (date(2011, 4, 26), date(2013, 3, 14), "FUTURO E LIBERTA' PER IL TERZO POLO", "FLPTP"),
    ]


def test_numero_votazione():
    assert camera.numero_votazione([ATTO + "ac17_2798"], "Votazione Emendamento DDL n.2798", None) == "2798"
    # Senza collegamento: dall'etichetta, poi dalla descrizione.
    assert camera.numero_votazione([], "Votazione Questione di fiducia DDL n. 2790-bis", None) == "2790-BIS"
    assert camera.numero_votazione([], "Votazione Articolo unico", "... sul quale il Governo ha posto la questione di fiducia (DDL 2547)") == "2547"
    assert camera.numero_votazione([], "Votazione Dimissioni", "DIMISSIONI DEPUTATO LUCIO MANISCO") is None


@pytest.mark.parametrize(
    ("campi", "tipo"),
    [
        (dict(tipo_fonte="Finale atto Camera", finale=True, fiducia=True), "finale"),  # la finale dopo la fiducia resta finale
        (dict(tipo_fonte="Articolo", fiducia=True), "fiducia"),
        (dict(titolo="Votazione Questione di fiducia DDL n.1334", tipo_fonte="Emendamento", fiducia=True), "fiducia"),
        (dict(tipo_fonte="Emendamento"), "emendamento"),
        (dict(tipo_fonte="Articolo"), "articolo"),
        (dict(tipo_fonte="Pregiudiziale"), "pregiudiziale"),
        (dict(tipo_fonte="Questione sospensiva"), "pregiudiziale"),
        (dict(tipo_fonte="Ordine del Giorno"), "altro"),
        (dict(titolo="Votazione finale", tipo_fonte=None), "finale"),
    ],
)
def test_tipo_votazione(campi, tipo):
    assert camera.tipo_votazione(votazione(campi.pop("titolo", "Votazione DDL n.2122-BIS"), **campi)) == tipo


def test_iniziativa_natura_urn():
    assert camera.iniziativa("Governo") == "governativa"
    assert camera.iniziativa("Mista (Governo, Parlamentare)") == "governativa"
    assert camera.iniziativa("Regioni") == "regionale"
    assert camera.iniziativa(None) is None
    legge = LeggeCamera(LEGGE + "L1995_1", None, 1, date(1995, 1, 1), "Conversione in legge del decreto-legge ...", "Ordinaria")
    assert camera.natura(legge) == "conversione di decreto-legge"
    legge.tipo = "Costituzionale"
    assert camera.natura(legge) == "costituzionale"
    assert camera.urn_da_lex("http://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1990-08-07;241") == "urn:nir:stato:legge:1990-08-07;241"
    assert camera.urn_da_lex(None) is None


def test_scegli_votazioni():
    vs = [votazione("a", numero="2122-BIS"), votazione("b", numero="999"), votazione("c", numero=None)]
    scelte, scartate = camera.scegli_votazioni(vs, {"2122-BIS"})
    assert [v.titolo for v in scelte] == ["a"] and scartate == 2


def test_confronta_governi():
    # Le date di governi.csv vengono dal Senato: la Camera dà gli stessi giuramenti.
    tutti = [GovernoCamera(g.nome, g.inizio, g.fine) for g in camera_governi_csv()]
    assert confronta_governi(tutti) == []
    assert confronta_governi(tutti[1:])[0].startswith("Andreotti VI")


def camera_governi_csv():
    from archivio import governi

    return governi.carica()


# --- estrazione con un endpoint finto ------------------------------------------------


def test_estrai_voti_salta_le_segrete_e_chi_non_vota(monkeypatch):
    monkeypatch.setattr(camera, "VOTAZIONI_PER_RICHIESTA", 2)
    votazioni = [votazione("x", id=VOTAZIONE + f"vs15_001_00{i}") for i in range(3)] + [
        votazione("segreta", id=VOTAZIONE + "vs15_001_009", segreta=True)
    ]

    class Finto:
        query: list[str] = []

        def select(self, query):
            Finto.query.append(query)
            ids = re.findall(r"<(http://dati.camera.it/ocd/votazione.rdf/[^>]+)>", query)
            deputato = "http://dati.camera.it/ocd/deputato.rdf/d305578_15"
            return [{"v": v, "d": deputato, "t": "Favorevole"} for v in ids] + [
                {"v": ids[0], "d": "http://dati.camera.it/ocd/deputato.rdf/d300001_15", "t": "Astensione"},
                {"v": ids[0], "d": deputato, "t": "Favorevole"},  # doppione da un altro grafo
            ]

    camera.estrai_voti(Finto(), votazioni)
    assert len(Finto.query) == 2
    assert all("vs15_001_009" not in q for q in Finto.query)
    assert votazioni[0].voti == {"favorevoli": ["305578"], "astenuti": ["300001"]}
    assert votazioni[3].voti == {}


@pytest.mark.parametrize(("leg", "da_dove"), [(15, "schede"), (17, "endpoint")])
def test_voti_dall_endpoint_dalla_xvii_e_dalle_schede_prima(monkeypatch, leg, da_dove):
    # Per XIII-XVI l'endpoint non ha ocd:voto: i voti vengono dalle schede HTML.
    chiamate = []
    monkeypatch.setattr(camera, "estrai_leggi", lambda *_: [])
    monkeypatch.setattr(camera, "fasi_camera_del_senato", lambda *_: ["2122-BIS"])
    monkeypatch.setattr(camera, "estrai_votazioni", lambda *_: [votazione("a")])
    monkeypatch.setattr(camera, "estrai_voti", lambda *_: chiamate.append("endpoint"))
    monkeypatch.setattr(camera, "nomi_deputati", lambda *_: camera.NomiDeputati())
    monkeypatch.setattr(camera, "estrai_voti_schede", lambda *_: chiamate.append("schede"))
    leg_camera = camera.estrai_legislatura(object(), object(), leg)
    assert len(leg_camera.votazioni) == 1
    assert chiamate == [da_dove]


# Righe vere della scheda XIII 128_59 (sonda camera-schede del 29/10/2026), più un omonimo inventato.
SCHEDA_XIII = """<h2 class="blu">Riepilogo dei voti espressi dai deputati</h2>
<table id="tabellaPartecipazioneVoto" class="display"><thead><tr><th>Nominativo</th><th>Gruppo</th><th>Voto</th></tr></thead>
<tbody>
<tr><td>ABATERUSSO ERNESTO</td><td>DS-U</td><td><span class="rosso">Contrario</span></td></tr>
<tr><td>ACIERNO ALBERTO</td><td>F-ITA</td><td><span class="verde">Favorevole</span></td></tr>
<tr><td>ACQUARONE LORENZO</td><td>PD-U</td><td><span class="nero">Non ha partecipato</span></td></tr>
<tr><td>ANDREATTA BENIAMINO</td><td>PD-U</td><td><span class="giallo">In missione</span></td></tr>
<tr><td>AGOSTINI LUCIANO</td><td>PD</td><td><span class="bianco">Astensione</span></td></tr>
<tr><td>D&#39;ALIA NICOLO&#39;</td><td>AN</td><td><span class="verde">Favorevole</span></td></tr>
<tr><td>ROSSI MARIO</td><td>AN</td><td><span class="verde">Favorevole</span></td></tr>
<tr><td>SCONOSCIUTO TIZIO</td><td>MISTO</td><td><span class="verde">Favorevole</span></td></tr>
</tbody></table>"""


def test_righe_scheda_e_url():
    righe = camera.righe_scheda(SCHEDA_XIII)
    assert righe[0] == ("ABATERUSSO ERNESTO", "DS-U", "Contrario")
    assert righe[5] == ("D'ALIA NICOLO'", "AN", "Favorevole")
    assert len(righe) == 8
    assert camera.righe_scheda("<html>niente</html>") == []
    v = votazione("x", id=VOTAZIONE + "vs13_128_059")
    assert camera.url_scheda(v).endswith("Legislatura=XIII&RifVotazione=128_59&tipo=dettaglio")
    v.fonte_url = "http://documenti.camera.it/votazioni/votazionitutte/schedavotazione.asp?Legislatura=XIII&RifVotazione=128_59&tipo=dettaglio"
    assert camera.url_scheda(v).startswith("https://documenti.camera.it/")


def test_estrai_voti_schede(monkeypatch):
    monkeypatch.setattr(camera, "PAUSA_SCHEDA", 0)
    nomi = camera.NomiDeputati()
    for chi, cognome, nome, sigla in [
        ("1", "ABATERUSSO", "Ernesto", "DS-U"), ("2", "ACIERNO", "Alberto", "F-ITA"), ("3", "AGOSTINI", "Luciano", "PD"),
        ("4", "D'ALIA", "Nicolò", "AN"), ("5", "ROSSI", "Mario", "AN"), ("6", "ROSSI", "Mario", "DS-U"),
    ]:
        nomi.aggiungi(chi, cognome, nome, sigla)
    v = votazione("x", id=VOTAZIONE + "vs13_128_059", favorevoli=4, contrari=1, astenuti=1)
    segreta = votazione("s", id=VOTAZIONE + "vs13_128_060", segreta=True)
    lette = []
    rapporto = camera.estrai_voti_schede([v, segreta], nomi, lambda url: lette.append(url) or SCHEDA_XIII)
    assert len(lette) == 1  # la segreta non si scarica
    assert v.voti == {"contrari": ["1"], "favorevoli": ["2", "4", "5"], "astenuti": ["3"]}
    assert "SCONOSCIUTO TIZIO (MISTO) ×1" in rapporto[2]
    assert "diversi dai totali della fonte: 1" in rapporto[1]


# --- file intermedi ---------------------------------------------------------------------


def legislatura_x() -> LegislaturaCamera:
    return LegislaturaCamera(
        10,
        [LeggeCamera(LEGGE + "L1990_241", "urn:nir:stato:legge:1990-08-07;241", 241, date(1990, 8, 7), "Procedimento amministrativo",
                     "Ordinaria", [ATTO + "ac10_1913"])],
        [AttoCamera(ATTO + "ac10_1913", "1913", "Norme sul procedimento", date(1987, 10, 20), "Governo", "35330", "http://scheda",
                    ["GORIA GIOVANNI, Presidente del Consiglio"], ["GAVA ANTONIO, Ministro dell'interno"])],
        [],
    )


def test_json_andata_e_ritorno(tmp_path):
    leg = legislatura_x()
    camera.scrivi(tmp_path / "camera_10.json", leg)
    assert camera.leggi_legislatura(tmp_path / "camera_10.json") == leg
    leg15 = LegislaturaCamera(15, [], [], [votazione("v", voti={"favorevoli": ["305578"]})], 7, ["2122-BIS"])
    camera.scrivi(tmp_path / "camera_15.json", leg15)
    assert camera.leggi_legislatura(tmp_path / "camera_15.json") == leg15
    persone = PersoneCamera(
        [Deputato("305578", "ALBRECHT", "PLANGGER")],
        [AdesioneCamera("305578", GRUPPO + "gr1589", date(2013, 3, 19), date(2018, 3, 22))],
        [GruppoCamera(GRUPPO + "gr1589", 17, "MISTO", None, date(2013, 3, 19), None, [("GIA'", "G", date(2014, 1, 1))])],
        [GovernoCamera("I Governo Meloni (21.10.2022)", date(2022, 10, 21), None)],
    )
    camera.scrivi(tmp_path / "camera_persone.json", persone)
    assert camera.leggi_persone(tmp_path / "camera_persone.json") == persone
