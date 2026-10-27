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

ENDPOINT = {
    "camera": "https://dati.camera.it/sparql",
    "senato": "https://dati.senato.it/sparql",
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
    "camera": {
        "atti per legislatura": """
SELECT ?leg (COUNT(?a) AS ?n) WHERE { ?a a ocd:atto ; ocd:rif_leg ?leg } GROUP BY ?leg ORDER BY ?leg""",
        "votazioni per legislatura": """
SELECT ?leg (COUNT(?v) AS ?n) WHERE { ?v a ocd:votazione ; ocd:rif_leg ?leg } GROUP BY ?leg ORDER BY ?leg""",
        "votazioni finali per legislatura": """
SELECT ?leg (COUNT(?v) AS ?n) WHERE { ?v a ocd:votazione ; ocd:rif_leg ?leg ; ocd:votazioneFinale ?f FILTER(STR(?f) IN ("1", "true")) }
GROUP BY ?leg ORDER BY ?leg""",
        "voti individuali per legislatura": """
SELECT ?leg (COUNT(?x) AS ?n) WHERE { ?x a ocd:voto ; ocd:rif_leg ?leg } GROUP BY ?leg ORDER BY ?leg""",
        "valori di ocd:iniziativa": """
SELECT ?i (COUNT(*) AS ?n) WHERE { ?a a ocd:atto ; ocd:iniziativa ?i } GROUP BY ?i ORDER BY DESC(?n) LIMIT 30""",
        "valori di dc:type nei voti": """
SELECT ?t (COUNT(*) AS ?n) WHERE { ?x a ocd:voto ; dc:type ?t } GROUP BY ?t ORDER BY DESC(?n) LIMIT 30""",
        "valori di dc:type negli atti": """
SELECT ?t (COUNT(*) AS ?n) WHERE { ?a a ocd:atto ; dc:type ?t } GROUP BY ?t ORDER BY DESC(?n) LIMIT 30""",
        "stati dell'iter": """
SELECT ?t (COUNT(*) AS ?n) WHERE { ?a a ocd:atto ; ocd:rif_statoIter ?s . ?s dc:title ?t } GROUP BY ?t ORDER BY DESC(?n) LIMIT 40""",
        "collegamenti a Normattiva": """
SELECT ?s ?p ?o WHERE { ?s ?p ?o FILTER(isIRI(?o) && CONTAINS(STR(?o), "normattiva")) } LIMIT 20""",
        "letterali con urn:nir": """
SELECT ?s ?p ?o WHERE { ?s ?p ?o FILTER(isLiteral(?o) && CONTAINS(STR(?o), "urn:nir")) } LIMIT 20""",
        "votazioni con fiducia": """
SELECT ?p (COUNT(?v) AS ?n) WHERE { ?v a ocd:votazione ; ?p ?o FILTER(CONTAINS(LCASE(STR(?p)), "fiducia")) } GROUP BY ?p""",
        "votazioni con 'fiducia' nel titolo": """
SELECT ?v ?t ?d WHERE { ?v a ocd:votazione ; dc:title ?t FILTER(CONTAINS(LCASE(STR(?t)), "fiducia")) OPTIONAL { ?v dc:date ?d } } LIMIT 10""",
        "atti della Legge Sirchia (L. 3/2003)": """
SELECT ?a ?p ?o WHERE { ?a a ocd:atto ; dc:title ?t ; ?p ?o
FILTER(CONTAINS(LCASE(STR(?t)), "disposizioni ordinamentali in materia di pubblica amministrazione")) } LIMIT 200""",
        "governi": """
SELECT ?g ?p ?o WHERE { ?g a ocd:governo ; ?p ?o } LIMIT 300""",
    },
    "senato": {
        "ddl per legislatura": """
SELECT ?leg (COUNT(?d) AS ?n) WHERE { ?d a osr:Ddl ; osr:legislatura ?leg } GROUP BY ?leg ORDER BY ?leg""",
        "votazioni per legislatura": """
SELECT ?leg (COUNT(?v) AS ?n) WHERE { ?v a osr:Votazione ; osr:legislatura ?leg } GROUP BY ?leg ORDER BY ?leg""",
        "valori di osr:natura": """
SELECT ?x (COUNT(*) AS ?n) WHERE { ?d a osr:Ddl ; osr:natura ?x } GROUP BY ?x ORDER BY DESC(?n) LIMIT 30""",
        "valori di osr:statoDdl": """
SELECT ?x (COUNT(*) AS ?n) WHERE { ?d a osr:Ddl ; osr:statoDdl ?x } GROUP BY ?x ORDER BY DESC(?n) LIMIT 40""",
        "valori di osr:esito": """
SELECT ?x (COUNT(*) AS ?n) WHERE { ?v a osr:Votazione ; osr:esito ?x } GROUP BY ?x ORDER BY DESC(?n) LIMIT 30""",
        "valori di osr:tipoVotazione": """
SELECT ?x (COUNT(*) AS ?n) WHERE { ?v a osr:Votazione ; osr:tipoVotazione ?x } GROUP BY ?x ORDER BY DESC(?n) LIMIT 30""",
        "collegamenti a Normattiva": """
SELECT ?s ?p ?o WHERE { ?s ?p ?o FILTER(isIRI(?o) && CONTAINS(STR(?o), "normattiva")) } LIMIT 20""",
        "letterali con urn:nir": """
SELECT ?s ?p ?o WHERE { ?s ?p ?o FILTER(isLiteral(?o) && CONTAINS(STR(?o), "urn:nir")) } LIMIT 20""",
        "votazioni con 'fiducia' nell'oggetto": """
SELECT ?v ?o WHERE { ?v a osr:Votazione ; osr:oggetto ?o FILTER(CONTAINS(LCASE(STR(?o)), "fiducia")) } LIMIT 10""",
        "ddl della Legge Sirchia (L. 3/2003)": """
SELECT ?d ?p ?o WHERE { ?d a osr:Ddl ; osr:titolo ?t ; ?p ?o
FILTER(CONTAINS(LCASE(STR(?t)), "disposizioni ordinamentali in materia di pubblica amministrazione")) } LIMIT 200""",
    },
}


def interroga(ramo: str, query: str, timeout: int = 120) -> list[dict[str, str]]:
    """Esegue una SELECT e restituisce le righe come dizionari {variabile: valore}."""
    testo = PREFISSI[ramo] + query
    parametri = urllib.parse.urlencode({"query": testo, "format": "application/sparql-results+json"})
    richiesta = urllib.request.Request(
        f"{ENDPOINT[ramo]}?{parametri}",
        headers={"Accept": "application/sparql-results+json", "User-Agent": "archivio-leggi/0.1 (sonda, non commerciale)"},
    )
    time.sleep(ATTESA)
    with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
        dati = json.load(risposta)
    return [{k: v["value"] for k, v in riga.items()} for riga in dati["results"]["bindings"]]


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


def sonda(ramo: str) -> tuple[dict[str, Any], str]:
    risultati: dict[str, Any] = {}
    report = f"\n## {ramo.capitalize()} — {ENDPOINT[ramo]}\n"

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
            f"""SELECT ?p (COUNT(*) AS ?n) (SAMPLE(?o) AS ?esempio) WHERE {{
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
        report += "\nDue istanze di esempio:\n\n" + tabella(esempi, 120)

    report += "\n### Query mirate\n"
    for nome, query in QUERY_MIRATE[ramo].items():
        righe = prova(risultati, ramo, nome, query)
        report += f"\n#### {nome}\n" + _esito(risultati, nome) + tabella(righe, 80)
    return risultati, report


def _esito(risultati: dict[str, Any], nome: str) -> str:
    voce = risultati.get(nome, {})
    if "errore" in voce:
        return f"**Errore**: `{breve(voce['errore'], 400)}`\n\n"
    return f"_{len(voce.get('righe', []))} righe in {voce.get('secondi', '?')} s_\n\n"


def main() -> int:
    rami = sys.argv[1:] or list(ENDPOINT)
    tutto: dict[str, Any] = {}
    report = "# Sonda Camera e Senato\n"
    for ramo in rami:
        tutto[ramo], parte = sonda(ramo)
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
