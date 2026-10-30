"""Prove dell'API su un Postgres vero con i dati di tests/dati.sql (serve TEST_DATABASE_URL)."""

import psycopg
import pytest

pytestmark = pytest.mark.db

L241 = "urn:nir:stato:legge:1990-08-07;241"
L3 = "urn:nir:stato:legge:2003-01-16;3"
DLGS81 = "urn:nir:stato:decreto.legislativo:2008-04-09;81"
DL1 = "urn:nir:stato:decreto.legge:2003-01-02;1"


def urn_trovati(client, **parametri):
    risposta = client.get("/leggi", params=parametri)
    assert risposta.status_code == 200, risposta.text
    return [legge["urn"] for legge in risposta.json()["risultati"]]


def test_salute(client):
    assert client.get("/salute").json() == {"stato": "ok", "atti": 4}


def test_ricerca_senza_filtri_per_data(client):
    corpo = client.get("/leggi").json()
    assert corpo["totale"] == 4
    assert [legge["urn"] for legge in corpo["risultati"]] == [DLGS81, L3, DL1, L241]
    assert urn_trovati(client, ordine="data_asc") == [L241, DL1, L3, DLGS81]


def test_ricerca_nel_titolo_con_stemming(client):
    # "amministrativi" e "amministrazione" hanno la stessa radice: trova la 241 e la L. 3/2003, la 241 prima (due parole).
    assert urn_trovati(client, q="procedimento amministrativo") == [L241]
    assert set(urn_trovati(client, q="amministrazione")) == {L241, L3}
    assert urn_trovati(client, q="sicurezza luoghi di lavoro") == [DLGS81]
    assert urn_trovati(client, q="amministrazione -procedimento") == [L3]


def test_ricerca_per_citazione_e_urn(client):
    assert urn_trovati(client, q="L. 3/2003") == [L3]
    assert urn_trovati(client, q="d.lgs. 81/2008") == [DLGS81]
    assert urn_trovati(client, q="1/2003") == [DL1]
    assert urn_trovati(client, q="d.lgs. 3/2003") == []
    assert urn_trovati(client, q=L241) == [L241]


def test_filtri(client):
    assert urn_trovati(client, tipo="decreto-legge") == [DL1]
    assert urn_trovati(client, stato="decaduta") == [DL1]
    assert urn_trovati(client, governo="berlusconi-2") == [L3, DL1]
    assert urn_trovati(client, anno=1990) == [L241]
    assert urn_trovati(client, numero="81") == [DLGS81]
    assert urn_trovati(client, dal="2003-01-10", al="2003-12-31") == [L3]
    assert urn_trovati(client, modificata="true") == [DLGS81, L241]
    assert urn_trovati(client, q="amministrazione", governo="berlusconi-2") == [L3]


def test_paginazione(client):
    corpo = client.get("/leggi", params={"per_pagina": 3, "pagina": 2}).json()
    assert (corpo["totale"], corpo["pagina"], corpo["per_pagina"]) == (4, 2, 3)
    assert [legge["urn"] for legge in corpo["risultati"]] == [L241]
    assert client.get("/leggi", params={"pagina": 9}).json()["totale"] == 4
    assert client.get("/leggi", params={"per_pagina": 101}).status_code == 422
    assert client.get("/leggi", params={"tipo": "dpr"}).status_code == 422


def test_dettaglio(client):
    corpo = client.get(f"/leggi/{L241}").json()
    assert corpo["titolo"].startswith("Nuove norme in materia di procedimento amministrativo")
    assert (corpo["stato"], corpo["numero_modifiche"], corpo["modificata"]) == ("vigente", 2, True)
    assert corpo["governo"]["nome"] == "Andreotti VI"
    assert [(p["partito"], p["ruolo"]) for p in corpo["governo"]["partiti"]] == [
        ("Democrazia Cristiana (DC)", "governo"),
        ("Partito Repubblicano Italiano (PRI)", "appoggio esterno"),
    ]
    assert corpo["gazzetta_codice"] == "090G0294"
    assert corpo["conteggi"] == {"ricevute": {"modifica": 2}, "disposte": {}, "pronunce": 1, "iter": 0}
    assert client.get(f"/leggi/{L3}").json()["conteggi"] == {
        "ricevute": {},
        "disposte": {"modifica": 1, "abroga_parziale": 1},
        "pronunce": 0,
        "iter": 1,
    }


def test_premessa(client):
    premessa = client.get(f"/leggi/{DL1}").json()["premessa"]
    assert premessa["motivazioni"] == ["Ritenuta la straordinaria necessità ed urgenza di adottare misure di prova;"]
    assert premessa["citazioni"][0] == "Visti gli articoli 77 e 87 della Costituzione;"
    assert premessa["proposta"].startswith("Sulla proposta")
    assert client.get(f"/leggi/{L241}").json()["premessa"] is None


def test_premessa_senza_schema_v14(client):
    # Su un database con lo schema v1.3 (tabella e colonna assenti) il dettaglio e l'iter rispondono lo stesso.
    from archivio_api import query

    with client.app.state.pool.connection() as conn:
        conn.execute("SAVEPOINT prima")
        conn.execute("SET LOCAL search_path TO pg_catalog")  # premessa, legge, ... non si vedono più
        assert query.premessa(conn, DL1) is None
        conn.execute("ROLLBACK TO SAVEPOINT prima")


def test_urn_con_punto_e_virgola_codificato(client):
    # Un client può codificare ";" e ":" nel percorso: l'URN arriva uguale.
    assert client.get("/leggi/urn%3Anir%3Astato%3Alegge%3A1990-08-07%3B241").json()["urn"] == L241


def test_legge_assente(client):
    for percorso in ("", "/relazioni", "/pronunce", "/iter", "/votazioni"):
        risposta = client.get(f"/leggi/urn:nir:stato:legge:1990-01-01;999{percorso}")
        assert risposta.status_code == 404
        assert "Legge non trovata" in risposta.json()["detail"]


def test_relazioni(client):
    ricevute = client.get(f"/leggi/{L241}/relazioni").json()
    assert ricevute["totale"] == 2
    prima, seconda = ricevute["risultati"]
    # In ordine di data: prima quella del 1999, con l'atto di origine fuori dall'archivio.
    assert (prima["urn_origine"], prima["origine_gazzetta_codice"], prima["atto_collegato"]) == (None, "099G0001", None)
    assert seconda["atto_collegato"] == {
        "urn": L3,
        "tipo": "legge",
        "numero": "3",
        "data": "2003-01-16",
        "titolo": "Disposizioni ordinamentali in materia di pubblica amministrazione.",
    }
    disposte = client.get(f"/leggi/{L3}/relazioni", params={"verso": "disposte", "tipo": "abroga_parziale"}).json()
    assert [r["atto_collegato"]["urn"] for r in disposte["risultati"]] == [DLGS81]


def test_pronunce(client):
    (pronuncia,) = client.get(f"/leggi/{L241}/pronunce").json()
    assert (pronuncia["articolo"], pronuncia["anno"], pronuncia["numero_sentenza"]) == ("art. 4", 1995, None)
    assert client.get(f"/leggi/{L3}/pronunce").json() == []


def test_iter(client):
    (iter_,) = client.get(f"/leggi/{L3}/iter").json()
    assert (iter_["legislatura"], iter_["iniziativa"]) == (14, "governativa")
    assert [(f["ramo"], f["numero"], f["numero_votazioni"]) for f in iter_["fasi"]] == [("senato", "S.795", 2), ("camera", "C.2122", 0)]
    assert iter_["fasi"][0]["firmatari"][0]["primo_firmatario"] is True
    assert iter_["fasi"][0]["testo_presentato"] == "urn:nir:senato.repubblica:disegno.legge:14.legislatura;795"
    assert iter_["fasi"][1]["testo_presentato"] is None
    assert client.get(f"/leggi/{L241}/iter").json() == []


def test_votazioni(client):
    corpo = client.get(f"/leggi/{L3}/votazioni").json()
    assert [(v["tipo"], v["nominale"]) for v in corpo["risultati"]] == [("emendamento", False), ("finale", True)]
    assert "voti_favorevoli" not in corpo["risultati"][0]
    finale = client.get(f"/leggi/{L3}/votazioni", params={"tipo": "finale"}).json()
    assert (finale["totale"], finale["risultati"][0]["favorevoli"]) == (1, 2)
    assert client.get(f"/leggi/{L3}/votazioni", params={"tipo": "segreta"}).status_code == 422
    assert corpo["risultati"][0]["gruppi"] is None


# Votazione finale della L. 3/2003 in tests/dati.sql: il gruppo 1 ha ancora il vecchio nome, la senatrice 2 vota
# nel gruppo 2 (vi è entrata quel giorno), il senatore 3 non ha gruppo e va in fondo.
GRUPPI_FINALE = [
    {"gruppo_id": "senato:g1", "nome": "Vecchio nome del gruppo", "sigla": "VNG", "favorevoli": 2, "contrari": 0, "astenuti": 0},
    {"gruppo_id": "senato:g2", "nome": "Gruppo misto", "sigla": "MISTO", "favorevoli": 0, "contrari": 1, "astenuti": 0},
    {"gruppo_id": None, "nome": None, "sigla": None, "favorevoli": 0, "contrari": 0, "astenuti": 1},
]


def test_votazioni_con_voto_per_gruppo(client):
    corpo = client.get(f"/leggi/{L3}/votazioni", params={"gruppi": "true"}).json()
    emendamento, finale = corpo["risultati"]
    assert emendamento["gruppi"] == []  # voto non nominale
    assert finale["gruppi"] == GRUPPI_FINALE


def test_dettaglio_votazione(client):
    # L'id contiene "/": arriva intero anche codificato.
    for percorso in ("/votazioni/senato:14/1", "/votazioni/senato%3A14%2F1"):
        corpo = client.get(percorso).json()
        assert (corpo["id"], corpo["urn"], corpo["fase_numero"], corpo["tipo"]) == ("senato:14/1", L3, "S.795", "finale")
        assert corpo["gruppi"] == GRUPPI_FINALE
    assert client.get("/votazioni/senato:v2").json()["gruppi"] == []
    risposta = client.get("/votazioni/senato:14/999")
    assert risposta.status_code == 404
    assert "Votazione non trovata" in risposta.json()["detail"]


def test_governi(client):
    governi = client.get("/governi").json()
    assert [(g["id"], g["numero_atti"]) for g in governi] == [("andreotti-6", 1), ("berlusconi-2", 2), ("prodi-2", 1)]
    assert governi[1]["partiti"] == [{"partito": "Forza Italia", "ruolo": "governo", "fonte_url": "https://example.org/fonte"}]


def test_connessioni_in_sola_lettura(client):
    with client.app.state.pool.connection() as conn:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("DELETE FROM legge")


def test_ricerca_usa_indice_titolo(database):
    # La query di /leggi?q= deve poter usare l'indice legge_titolo_fts: stessa espressione di schema.sql.
    from psycopg import sql

    from archivio_api.query import QUERY_TESTO, VETTORE_TITOLO

    with psycopg.connect(database) as conn:
        conn.execute("SET enable_seqscan = off")
        piano = conn.execute(
            sql.SQL("EXPLAIN SELECT 1 FROM legge l WHERE {} @@ {}").format(VETTORE_TITOLO, QUERY_TESTO.format("lavoro"))
        ).fetchall()
    assert any("legge_titolo_fts" in riga[0] for riga in piano)
