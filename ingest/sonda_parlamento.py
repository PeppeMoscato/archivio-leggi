"""Sonda: cosa offrono davvero gli endpoint SPARQL di Camera e Senato.

Serve a progettare lo schema v1.2 (iter, votazioni, gruppi, governi) prima di
scrivere la pipeline. Non usa il database e non ha dipendenze esterne.

Per ogni endpoint:
1. elenca le classi con il numero di istanze;
2. per le classi utili (atti, votazioni, voti, gruppi, governi, ...) mostra le
   proprietà usate e alcune istanze di esempio con tutte le loro triple;
3. esegue le query mirate di QUERY_MIRATE (conteggi per legislatura, legame
   con le leggi pubblicate, fiducia, ...).

Uscite: il report in Markdown su stdout (e nel riepilogo del job su GitHub
Actions) e `samples/sonda_parlamento.json` con le risposte grezze.
Ogni query che fallisce viene registrata come errore senza fermare le altre.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CARTELLA_SAMPLES = Path(__file__).parent / "samples"
ATTESA = 1.0  # secondi fra una query e l'altra: gli endpoint non pubblicano quote

# Il primo indirizzo che risponde vince: alla prima esecuzione l'HTTPS della Camera
# rispondeva 502 a ogni query.
ENDPOINT = {
    "camera": ["https://dati.camera.it/sparql", "http://dati.camera.it/sparql"],
    "senato": ["https://dati.senato.it/sparql", "http://dati.senato.it/sparql"],
}

PREFISSI = {
    "camera": """
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
""",
    "senato": """
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
""",
}

# Parole che rendono una classe interessante per iter, voti e governi.
CLASSI_UTILI = re.compile(
    r"atto|ddl|legge|votazion|voto|gruppo|afferenz|adesion|governo|incaric|iniziativ|iter|fase|stato|"
    r"deputato|senatore|firmat|seduta|legislatura|mandato|partito|fiducia|relatore|lista",
    re.IGNORECASE,
)

# Query mirate. I nomi delle proprietà vengono dalla documentazione delle ontologie
# (OCD per la Camera, OSR per il Senato) e vanno confermati: per questo le query
# generiche qui sopra girano prima.
QUERY_MIRATE: dict[str, dict[str, str]] = {
    # Seconda tornata (Task 1.2, parte Camera): la prima esplorazione è in docs/sonda_parlamento.md.
    "camera": {
        "leggi per legislatura": """
SELECT ?leg (COUNT(?l) AS ?n) WHERE { ?l a ocd:legge ; ocd:rif_leg ?leg } GROUP BY ?leg ORDER BY ?leg""",
        "tipi di legge": """
SELECT ?t (COUNT(*) AS ?n) WHERE { ?l a ocd:legge ; dc:type ?t } GROUP BY ?t ORDER BY DESC(?n)""",
        "proprietà dei lavori preparatori": """
SELECT ?p (COUNT(*) AS ?n) WHERE { { SELECT ?lp WHERE { ?l a ocd:legge ; ocd:lavoriPreparatori ?lp } LIMIT 2000 } ?lp ?p ?o } GROUP BY ?p ORDER BY DESC(?n)""",
        "Legge Sirchia (L. 3/2003) con i lavori preparatori": """
SELECT ?l ?p ?o ?p2 ?o2 WHERE { ?l a ocd:legge ; ocd:lex <http://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2003-01-16;3> ; ?p ?o
OPTIONAL { ?o ?p2 ?o2 FILTER(isBlank(?o)) } }""",
        "L. 241/1990 con i lavori preparatori": """
SELECT ?l ?p ?o ?p2 ?o2 WHERE { ?l a ocd:legge ; ocd:lex <http://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1990-08-07;241> ; ?p ?o
OPTIONAL { ?o ?p2 ?o2 FILTER(isBlank(?o)) } }""",
        "D.L. 4/2019 (reddito di cittadinanza) e legge di conversione": """
SELECT ?l ?p ?o ?p2 ?o2 WHERE { ?l a ocd:legge ; ocd:lex ?x ; ?p ?o FILTER(CONTAINS(STR(?x), "2019-03-28;26"))
OPTIONAL { ?o ?p2 ?o2 FILTER(isBlank(?o)) } }""",
        "atto ac14_2122-bis (tutte le triple)": """
SELECT ?p ?o WHERE { <http://dati.camera.it/ocd/attocamera.rdf/ac14_2122-bis> ?p ?o }""",
        "stati dell'iter di ac14_2122-bis": """
SELECT ?s ?t ?d WHERE { <http://dati.camera.it/ocd/attocamera.rdf/ac14_2122-bis> ocd:rif_statoIter ?s . ?s dc:title ?t OPTIONAL { ?s dc:date ?d } }""",
        "atti con uno stato 'Legge' per legislatura": """
SELECT ?leg (COUNT(DISTINCT ?a) AS ?n) WHERE { ?a a ocd:atto ; ocd:rif_leg ?leg ; ocd:rif_statoIter ?s . ?s dc:title ?t
FILTER(CONTAINS(STR(?t), "Legge") || CONTAINS(STR(?t), "legge")) } GROUP BY ?leg ORDER BY ?leg""",
        "valori di ocd:rif_natura": """
SELECT ?n (COUNT(*) AS ?c) WHERE { ?a a ocd:atto ; ocd:rif_natura ?x . ?x dc:title ?n } GROUP BY ?n ORDER BY DESC(?c)""",
        "votazioni per tipo (dc:type)": """
SELECT ?t (COUNT(*) AS ?n) WHERE { ?v a ocd:votazione ; dc:type ?t } GROUP BY ?t ORDER BY DESC(?n) LIMIT 60""",
        "votazioni con richiestaFiducia = 1 per legislatura": """
SELECT ?leg (COUNT(?v) AS ?n) WHERE { ?v a ocd:votazione ; ocd:rif_leg ?leg ; ocd:richiestaFiducia ?f FILTER(STR(?f) = "1") } GROUP BY ?leg ORDER BY ?leg""",
        "votazioni con richiestaFiducia = 1 (campione)": """
SELECT ?v ?t ?d ?tipo WHERE { ?v a ocd:votazione ; ocd:richiestaFiducia ?f ; dc:title ?t ; dc:description ?d ; dc:type ?tipo FILTER(STR(?f) = "1") } LIMIT 30""",
        "votazioni 'fiducia' nel titolo per legislatura": """
SELECT ?leg (COUNT(?v) AS ?n) WHERE { ?v a ocd:votazione ; ocd:rif_leg ?leg ; dc:title ?t FILTER(CONTAINS(LCASE(STR(?t)), "fiducia")) } GROUP BY ?leg ORDER BY ?leg""",
        "votazioni con rif_attoCamera per legislatura": """
SELECT ?leg (COUNT(?v) AS ?n) WHERE { ?v a ocd:votazione ; ocd:rif_leg ?leg ; ocd:rif_attoCamera ?a } GROUP BY ?leg ORDER BY ?leg""",
        "votazioni della XIII senza rif_attoCamera (campione)": """
SELECT ?t ?d ?tipo WHERE { ?v a ocd:votazione ; ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_13> ; dc:title ?t ; dc:description ?d ; dc:type ?tipo
OPTIONAL { ?v ocd:rif_attoCamera ?a } FILTER(!BOUND(?a)) } LIMIT 40""",
        "votazioni su ac14_2122-bis e ac14_2122-bis-b": """
SELECT ?v ?t ?d ?tipo ?fin WHERE { ?v ocd:rif_attoCamera ?a ; dc:title ?t ; dc:description ?d ; dc:type ?tipo ; ocd:votazioneFinale ?fin
FILTER(?a IN (<http://dati.camera.it/ocd/attocamera.rdf/ac14_2122-bis>, <http://dati.camera.it/ocd/attocamera.rdf/ac14_2122-bis-b>)) }""",
        "voti di una votazione per tipo (vs17_487_077)": """
SELECT ?t (COUNT(*) AS ?n) WHERE { ?x ocd:rif_votazione <http://dati.camera.it/ocd/votazione.rdf/vs17_487_077> ; dc:type ?t } GROUP BY ?t""",
        "voti di due votazioni con FILTER IN": """
SELECT ?v ?t (COUNT(*) AS ?n) WHERE { ?x ocd:rif_votazione ?v ; dc:type ?t
FILTER(?v IN (<http://dati.camera.it/ocd/votazione.rdf/vs17_487_077>, <http://dati.camera.it/ocd/votazione.rdf/vs19_376_012>)) } GROUP BY ?v ?t""",
        "voti di due votazioni con VALUES": """
SELECT ?v ?t (COUNT(*) AS ?n) WHERE { VALUES ?v { <http://dati.camera.it/ocd/votazione.rdf/vs17_487_077> <http://dati.camera.it/ocd/votazione.rdf/vs19_376_012> }
?x ocd:rif_votazione ?v ; dc:type ?t } GROUP BY ?v ?t""",
        "voti di 15 votazioni della XV con FILTER IN (righe)": """
SELECT ?v ?d ?t WHERE { ?x ocd:rif_votazione ?v ; ocd:rif_deputato ?d ; dc:type ?t
FILTER(?v IN (<http://dati.camera.it/ocd/votazione.rdf/vs15_010_001>, <http://dati.camera.it/ocd/votazione.rdf/vs15_010_002>,
<http://dati.camera.it/ocd/votazione.rdf/vs15_010_003>, <http://dati.camera.it/ocd/votazione.rdf/vs15_010_004>, <http://dati.camera.it/ocd/votazione.rdf/vs15_010_005>,
<http://dati.camera.it/ocd/votazione.rdf/vs15_010_006>, <http://dati.camera.it/ocd/votazione.rdf/vs15_010_007>, <http://dati.camera.it/ocd/votazione.rdf/vs15_010_008>,
<http://dati.camera.it/ocd/votazione.rdf/vs15_010_009>, <http://dati.camera.it/ocd/votazione.rdf/vs15_010_010>, <http://dati.camera.it/ocd/votazione.rdf/vs15_020_001>,
<http://dati.camera.it/ocd/votazione.rdf/vs15_020_002>, <http://dati.camera.it/ocd/votazione.rdf/vs15_020_003>, <http://dati.camera.it/ocd/votazione.rdf/vs15_020_004>,
<http://dati.camera.it/ocd/votazione.rdf/vs15_020_005>)) FILTER(STR(?t) != "Non ha votato") } LIMIT 20000""",
        "voti per legislatura e tipo (dall'IRI del voto)": """
SELECT ?leg ?t (COUNT(*) AS ?n) WHERE { ?x a ocd:voto ; dc:type ?t BIND(SUBSTR(STR(?x), 38, 2) AS ?leg) } GROUP BY ?leg ?t ORDER BY ?leg ?t""",
        "limite di righe per risposta (60.000 voti chiesti)": """
SELECT ?x WHERE { ?x a ocd:voto } LIMIT 60000""",
        "paginazione: OFFSET 50000 con ORDER BY": """
SELECT ?x WHERE { ?x a ocd:voto } ORDER BY ?x OFFSET 50000 LIMIT 5""",
        "deputato d305578_17 (tutte le triple)": """
SELECT ?p ?o WHERE { <http://dati.camera.it/ocd/deputato.rdf/d305578_17> ?p ?o }""",
        "adesioni ai gruppi: proprietà": """
SELECT ?p (COUNT(*) AS ?n) WHERE { { SELECT ?a WHERE { ?d a ocd:deputato ; ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_17> ; ocd:aderisce ?a } LIMIT 2000 } ?a ?p ?o }
GROUP BY ?p ORDER BY DESC(?n)""",
        "adesioni di d305578_17": """
SELECT ?a ?p ?o WHERE { <http://dati.camera.it/ocd/deputato.rdf/d305578_17> ocd:aderisce ?a . ?a ?p ?o }""",
        "gruppi per legislatura": """
SELECT ?leg (COUNT(?g) AS ?n) WHERE { ?g a ocd:gruppoParlamentare ; ocd:rif_leg ?leg } GROUP BY ?leg ORDER BY ?leg""",
        "denominazioni dei gruppi: proprietà": """
SELECT ?p (COUNT(*) AS ?n) WHERE { ?g a ocd:gruppoParlamentare ; ocd:denominazione ?d . ?d ?p ?o } GROUP BY ?p ORDER BY DESC(?n)""",
        "denominazioni dei gruppi (campione)": """
SELECT ?g ?d ?p ?o WHERE { ?g a ocd:gruppoParlamentare ; ocd:denominazione ?d . ?d ?p ?o } LIMIT 30""",
        "gruppi che diventano altri gruppi": """
SELECT ?g ?t ?nuovo WHERE { ?g a ocd:gruppoParlamentare ; dc:title ?t ; ocd:diventa ?nuovo } LIMIT 20""",
        "governi dal 1987": """
SELECT ?g ?t ?inizio ?fine WHERE { ?g a ocd:governo ; dc:title ?t ; ocd:startDate ?inizio OPTIONAL { ?g ocd:endDate ?fine } FILTER(STR(?inizio) >= "1987") }
ORDER BY ?inizio""",
    },
    "senato": {
        "limite di righe per risposta (60.000 voti chiesti)": """
SELECT ?v ?s WHERE { ?v a osr:Votazione ; osr:legislatura 18 ; osr:contrario ?s } LIMIT 60000""",
        "paginazione: OFFSET 50000 con ORDER BY": """
SELECT ?v ?s WHERE { ?v a osr:Votazione ; osr:legislatura 18 ; osr:contrario ?s } ORDER BY ?v ?s OFFSET 50000 LIMIT 5""",
        "voti di due votazioni con FILTER IN": """
SELECT ?v ?p (COUNT(*) AS ?n) WHERE { ?v ?p ?s FILTER(?v IN (<http://dati.senato.it/votazione/18-105-16>, <http://dati.senato.it/votazione/18-104-2>)) FILTER(?p IN (osr:favorevole, osr:contrario, osr:astenuto)) } GROUP BY ?v ?p""",
        "voti di due votazioni con VALUES": """
SELECT ?v ?p (COUNT(*) AS ?n) WHERE { VALUES ?v { <http://dati.senato.it/votazione/18-105-16> <http://dati.senato.it/votazione/18-104-2> } ?v ?p ?s FILTER(?p = osr:favorevole || ?p = osr:contrario || ?p = osr:astenuto) } GROUP BY ?v ?p""",
        "voti di due votazioni con OR": """
SELECT ?v ?p (COUNT(*) AS ?n) WHERE { ?v ?p ?s FILTER(?v = <http://dati.senato.it/votazione/18-105-16> || ?v = <http://dati.senato.it/votazione/18-104-2>) FILTER(?p = osr:favorevole || ?p = osr:contrario || ?p = osr:astenuto) } GROUP BY ?v ?p""",
        "voti di due votazioni con UNION": """
SELECT ?v ?p (COUNT(*) AS ?n) WHERE { { ?v ?p ?s FILTER(?v = <http://dati.senato.it/votazione/18-105-16>) } UNION { ?v ?p ?s FILTER(?v = <http://dati.senato.it/votazione/18-104-2>) }
FILTER(?p = osr:favorevole || ?p = osr:contrario || ?p = osr:astenuto) } GROUP BY ?v ?p""",
        "fasi con lo stesso idDdl della Legge Sirchia": """
SELECT ?fase ?ramo ?numero ?progr ?compatto WHERE { ?fase a osr:Ddl ; osr:idDdl 15167 ; osr:ramo ?ramo ; osr:numeroFase ?numero ;
osr:progressivoIter ?progr ; osr:numeroFaseCompatto ?compatto }""",
        "iter con fasi in più legislature": """
SELECT (COUNT(*) AS ?n) WHERE { { SELECT ?id (COUNT(DISTINCT ?leg) AS ?l) WHERE { ?f a osr:Ddl ; osr:idDdl ?id ; osr:legislatura ?leg } GROUP BY ?id } FILTER(?l > 1) }""",
        "votazioni per tipo nella XIII": """
SELECT ?t (COUNT(*) AS ?n) WHERE { ?v a osr:Votazione ; osr:legislatura 13 ; osr:tipoVotazione ?t } GROUP BY ?t""",
        "etichette di votazioni della XIII senza oggetto (campione)": """
SELECT ?l WHERE { ?v a osr:Votazione ; osr:legislatura 13 ; rdfs:label ?l OPTIONAL { ?v osr:oggetto ?o } FILTER(!BOUND(?o)) } LIMIT 40""",
        "collegamento iniziativa → senatore (proprietà)": """
SELECT ?p (COUNT(*) AS ?n) WHERE { ?i a osr:Iniziativa ; ?p ?x FILTER(STRSTARTS(STR(?x), "http://dati.senato.it/senatore/")) } GROUP BY ?p""",
    },
}


def interroga(ramo: str, query: str, timeout: int = 120) -> list[dict[str, str]]:
    """Esegue una SELECT e restituisce le righe come dizionari {variabile: valore}.

    Prova gli indirizzi dell'endpoint in ordine; un errore 5xx o di rete passa al successivo.
    """
    testo = PREFISSI[ramo] + query
    parametri = urllib.parse.urlencode({"query": testo, "format": "application/sparql-results+json"})
    errore: Exception | None = None
    for indirizzo in ENDPOINT[ramo]:
        richiesta = urllib.request.Request(
            f"{indirizzo}?{parametri}",
            headers={"Accept": "application/sparql-results+json", "User-Agent": "archivio-leggi/0.1 (sonda, non commerciale)"},
        )
        time.sleep(ATTESA)
        try:
            with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
                dati = json.load(risposta)
            return [{k: v["value"] for k, v in riga.items()} for riga in dati["results"]["bindings"]]
        except urllib.error.HTTPError as e:
            if e.code < 500:
                raise
            errore = e
        except (urllib.error.URLError, TimeoutError) as e:
            errore = e
    assert errore is not None
    raise errore


def prova(risultati: dict[str, Any], ramo: str, nome: str, query: str) -> list[dict[str, str]]:
    inizio = time.monotonic()
    try:
        righe = interroga(ramo, query)
        risultati[nome] = {"righe": righe, "secondi": round(time.monotonic() - inizio, 1)}
        return righe
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as errore:
        dettaglio = errore.read().decode(errors="replace")[:500] if isinstance(errore, urllib.error.HTTPError) else ""
        risultati[nome] = {"errore": f"{type(errore).__name__}: {errore} {dettaglio}".strip()}
        return []


def breve(valore: str, n: int = 160) -> str:
    valore = " ".join(valore.split())
    return valore if len(valore) <= n else valore[: n - 1] + "…"


def compatta(righe: list[dict[str, str]], massimo: int = 3) -> list[dict[str, str]]:
    """Per ogni coppia (soggetto, proprietà) tiene i primi valori e conta gli altri."""
    gruppi: dict[tuple[str, str], list[str]] = {}
    for riga in righe:
        gruppi.setdefault((riga.get("s", ""), riga.get("p", "")), []).append(riga.get("o", ""))
    uscita = []
    for (soggetto, proprieta), valori in gruppi.items():
        testo = " ; ".join(valori[:massimo]) + (f" (+{len(valori) - massimo})" if len(valori) > massimo else "")
        uscita.append({"s": soggetto, "p": proprieta, "o": testo})
    return uscita


def tabella(righe: list[dict[str, str]], massimo: int = 60) -> str:
    if not righe:
        return "_nessuna riga_\n"
    colonne = list(dict.fromkeys(k for riga in righe for k in riga))
    testo = "| " + " | ".join(colonne) + " |\n|" + "---|" * len(colonne) + "\n"
    for riga in righe[:massimo]:
        testo += "| " + " | ".join(breve(riga.get(c, "")).replace("|", "\\|") for c in colonne) + " |\n"
    if len(righe) > massimo:
        testo += f"\n_… altre {len(righe) - massimo} righe nel JSON_\n"
    return testo


def _legislatura(n: int) -> str:
    return f"<http://dati.camera.it/ocd/legislatura.rdf/repubblica_{n:02d}>"


# Terza tornata (28/10/2026): la pipeline non trova voti individuali per le votazioni della XV
# (0 righe con ocd:rif_votazione), mentre per XVII e XIX ci sono. Per ogni legislatura: come sono
# fatte le votazioni, che cosa punta a loro e a quali votazioni puntano i voti dei deputati.
QUERY_VOTI: dict[str, str] = {
    "un voto della XVII (tutte le triple)": """
SELECT ?x ?p ?o WHERE { { SELECT ?x WHERE { ?x ocd:rif_votazione <http://dati.camera.it/ocd/votazione.rdf/vs17_487_077> } LIMIT 1 } ?x ?p ?o }""",
}
for _n in range(13, 20):
    QUERY_VOTI |= {
        f"leg. {_n}: una votazione (tutte le triple)": f"""
SELECT ?v ?p ?o WHERE {{ {{ SELECT ?v WHERE {{ ?v a ocd:votazione ; ocd:rif_leg {_legislatura(_n)} }} OFFSET 500 LIMIT 1 }} ?v ?p ?o }}""",
        f"leg. {_n}: che cosa punta a tre votazioni": f"""
SELECT ?v ?p (COUNT(*) AS ?n) WHERE {{ {{ SELECT ?v WHERE {{ ?v a ocd:votazione ; ocd:rif_leg {_legislatura(_n)} }} OFFSET 500 LIMIT 3 }} ?s ?p ?v }}
GROUP BY ?v ?p""",
        f"leg. {_n}: voti di un deputato": f"""
SELECT ?x ?v ?t WHERE {{ {{ SELECT ?d WHERE {{ ?d a ocd:deputato ; ocd:rif_leg {_legislatura(_n)} }} OFFSET 100 LIMIT 1 }}
?x ocd:rif_deputato ?d ; ocd:rif_votazione ?v ; dc:type ?t }} LIMIT 5""",
    }


def sonda(ramo: str, esplora: bool = True, query: dict[str, str] | None = None) -> tuple[dict[str, Any], str]:
    risultati: dict[str, Any] = {}
    report = f"\n## {ramo.capitalize()} — {ENDPOINT[ramo][0]}\n"
    if not esplora:
        return _mirate(risultati, ramo, report, query or QUERY_MIRATE[ramo])

    classi = prova(risultati, ramo, "classi", "SELECT ?c (COUNT(?s) AS ?n) WHERE { ?s a ?c } GROUP BY ?c ORDER BY DESC(?n) LIMIT 300")
    if not classi:
        # Su endpoint grandi il conteggio può andare in timeout: basta l'elenco.
        classi = prova(risultati, ramo, "classi (senza conteggio)", "SELECT DISTINCT ?c WHERE { ?s a ?c } LIMIT 300")
    report += "\n### Classi\n" + _esito(risultati, "classi") + tabella(classi, 300)

    for riga in classi:
        classe = riga["c"]
        if not CLASSI_UTILI.search(classe.rsplit("/", 1)[-1].rsplit("#", 1)[-1]):
            continue
        nome = f"proprietà di {classe}"
        proprieta = prova(
            risultati, ramo, nome,
            f"""SELECT ?p (COUNT(*) AS ?n) WHERE {{
  {{ SELECT ?s WHERE {{ ?s a <{classe}> }} LIMIT 2000 }} ?s ?p ?o }} GROUP BY ?p ORDER BY DESC(?n)""",
        )
        report += f"\n### {classe}\n" + _esito(risultati, nome) + "Proprietà sulle prime 2.000 istanze:\n\n" + tabella(proprieta)
        nome_esempi = f"esempi di {classe}"
        esempi = prova(
            risultati, ramo, nome_esempi,
            f"SELECT ?s ?p ?o WHERE {{ {{ SELECT ?s WHERE {{ ?s a <{classe}> }} OFFSET 1000 LIMIT 2 }} ?s ?p ?o }}",
        )
        if not esempi:
            esempi = prova(risultati, ramo, nome_esempi, f"SELECT ?s ?p ?o WHERE {{ {{ SELECT ?s WHERE {{ ?s a <{classe}> }} LIMIT 2 }} ?s ?p ?o }}")
        report += "\nDue istanze di esempio:\n\n" + tabella(compatta(esempi), 120)

    return _mirate(risultati, ramo, report, QUERY_MIRATE[ramo])


def _mirate(risultati: dict[str, Any], ramo: str, report: str, mirate: dict[str, str]) -> tuple[dict[str, Any], str]:
    report += "\n### Query mirate\n"
    for nome, query in mirate.items():
        righe = prova(risultati, ramo, nome, query)
        report += f"\n#### {nome}\n" + _esito(risultati, nome) + tabella(righe, 80)
    return risultati, report


def _esito(risultati: dict[str, Any], nome: str) -> str:
    voce = risultati.get(nome, {})
    if "errore" in voce:
        return f"**Errore**: `{breve(voce['errore'], 400)}`\n\n"
    return f"_{len(voce.get('righe', []))} righe in {voce.get('secondi', '?')} s_\n\n"


# Le pagine HTML delle votazioni (dc:relation): per XIII-XVI l'endpoint non ha i voti dei deputati,
# forse le schede sì. Una votazione per legislatura, la XVII come confronto.
SCHEDE = {
    13: "http://documenti.camera.it/votazioni/votazionitutte/schedavotazione.asp?Legislatura=XIII&RifVotazione=128_59&tipo=dettaglio",
    14: "http://documenti.camera.it/votazioni/votazionitutte/schedavotazione.asp?Legislatura=XIV&RifVotazione=29_26&tipo=dettaglio",
    15: "http://documenti.camera.it/votazioni/votazionitutte/schedavotazione.asp?Legislatura=XV&RifVotazione=33_13&tipo=dettaglio",
    16: "http://documenti.camera.it/votazioni/votazionitutte/schedavotazione.asp?Legislatura=XVI&RifVotazione=36_26&tipo=dettaglio",
    17: "http://documenti.camera.it/votazioni/votazionitutte/schedavotazione.asp?Legislatura=XVII&RifVotazione=374_51&tipo=dettaglio",
}


def schede() -> tuple[dict[str, Any], str]:
    risultati: dict[str, Any] = {}
    report = "\n## Schede HTML delle votazioni della Camera\n"
    for leg, url in SCHEDE.items():
        report += f"\n### Legislatura {leg}\n{url}\n\n"
        try:
            richiesta = urllib.request.Request(url, headers={"User-Agent": "archivio-leggi (sonda; progetto non commerciale)"})
            with urllib.request.urlopen(richiesta, timeout=60) as risposta:
                grezzo = risposta.read()
                stato, finale = risposta.status, risposta.geturl()
        except (urllib.error.URLError, TimeoutError) as errore:
            risultati[str(leg)] = {"errore": str(errore)}
            report += f"**Errore**: `{errore}`\n"
            continue
        html = grezzo.decode("utf-8", errors="replace") if b"utf-8" in grezzo[:2000].lower() else grezzo.decode("latin-1")
        testo = " ".join(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", html)).split())
        conteggi = {parola: len(re.findall(parola, testo, re.I)) for parola in ("favorevole", "contrario", "astenuto", "non ha votato", "missione")}
        risultati[str(leg)] = {"stato": stato, "url_finale": finale, "byte": len(grezzo), "conteggi": conteggi, "testo": testo[:20000]}
        report += f"HTTP {stato}, {len(grezzo)} byte, url finale {finale}\n\nParole: {conteggi}\n\n"
        dove = max(0, testo.lower().find("favorevol") - 300)
        report += "```\n" + testo[:600] + "\n...\n" + testo[dove:dove + 1500] + "\n```\n"
        # Com'è fatta la tabella dei voti (per collegare i nomi ai deputati) e dove portano i link.
        collegamenti: dict[str, int] = {}
        for href in re.findall(r'(?i)href\s*=\s*["\']?([^"\'\s>]+)', html):
            chiave = re.sub(r"=[^&]*", "=…", href)
            collegamenti[chiave] = collegamenti.get(chiave, 0) + 1
        report += "Link (parametri tolti): " + json.dumps(sorted(collegamenti.items(), key=lambda c: -c[1])[:20], ensure_ascii=False) + "\n\n"
        if leg in (13, 16):
            inizio = html.find("Nominativo")
            report += "HTML attorno alla tabella:\n```html\n" + html[max(0, inizio - 300):inizio + 3500] + "\n```\n"
            tabellare = re.search(r'(?is)href\s*=\s*["\']?([^"\'\s>]+)["\']?[^>]*>[^<]*tabellare', html)
            if tabellare:
                indirizzo = urllib.parse.urljoin(finale, tabellare.group(1).replace("&amp;", "&"))
                report += f"Formato tabellare: {indirizzo}\n"
                try:
                    with urllib.request.urlopen(urllib.request.Request(indirizzo, headers={"User-Agent": "archivio-leggi (sonda)"}), timeout=60) as r:
                        corpo = r.read()
                    report += f"{len(corpo)} byte, tipo {r.headers.get('Content-Type')}\n```\n" + corpo[:2500].decode("latin-1") + "\n```\n"
                except (urllib.error.URLError, TimeoutError) as errore:
                    report += f"**Errore**: `{errore}`\n"
        time.sleep(ATTESA * 3)
    return risultati, report


def main() -> int:
    # "senato-mirate": solo le query mirate, senza esplorare tutte le classi; "camera-voti": solo QUERY_VOTI;
    # "camera-schede": le pagine HTML di alcune votazioni.
    rami = sys.argv[1:] or list(ENDPOINT)
    tutto: dict[str, Any] = {}
    report = "# Sonda Camera e Senato\n"
    for argomento in rami:
        if argomento == "camera-schede":
            tutto["schede"], parte = schede()
            report += parte
            print(parte, flush=True)
            continue
        ramo, _, modo = argomento.partition("-")
        tutto[ramo], parte = sonda(ramo, esplora=modo not in ("mirate", "voti"), query=QUERY_VOTI if modo == "voti" else None)
        report += parte
        print(parte, flush=True)
    CARTELLA_SAMPLES.mkdir(exist_ok=True)
    (CARTELLA_SAMPLES / "sonda_parlamento.json").write_text(json.dumps(tutto, ensure_ascii=False, indent=1), encoding="utf-8")
    if riepilogo := os.environ.get("GITHUB_STEP_SUMMARY"):
        # Il riepilogo di GitHub accetta al massimo 1 MB.
        Path(riepilogo).write_text(report[:1_000_000], encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
