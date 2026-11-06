"""Sonda: quali fonti descrivono i rapporti tra i partiti dal 1990.

Serve a progettare la parte "rapporti tra i partiti" (anagrafica, fusioni e
scissioni, coalizioni elettorali, entrate e uscite dalle maggioranze) prima di
toccare lo schema. Non usa il database. Controlla:
1. wikidata: partiti italiani, relazioni tra partiti (segue, sostituisce, si è
   separato da, confluito in, parte di) con date e riferimenti; quanti dei
   partiti di `archivio/governi_partiti.csv` si trovano per nome;
2. parlgov: il database ParlGov (SQLite), tabelle e righe dell'Italia, licenza
   dichiarata su Harvard Dataverse;
3. eligendo: l'archivio storico delle elezioni del Ministero dell'Interno
   (risponde ai programmi? dati aperti? licenza? coalizioni?);
4. camera e senato: classi e proprietà su governi, membri del governo, elezioni,
   liste e votazioni di fiducia al governo.

Uscite: il report in Markdown su stdout (e nel riepilogo del job su GitHub
Actions) e `samples/sonda_partiti_<parte>.json` con le risposte grezze.
Ogni passo che fallisce viene registrato come errore senza fermare gli altri.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from sonda_parlamento import AGENTE, interroga, tabella

CARTELLA_SAMPLES = Path(__file__).parent / "samples"
CSV_PARTITI = Path(__file__).parent / "archivio" / "governi_partiti.csv"
WIKIDATA = "https://query.wikidata.org/sparql"

# Relazioni tra partiti su Wikidata: segue, seguito da, sostituisce, sostituito da,
# separato da, confluito in, parte di, membro di.
PROPRIETA = {
    "P155": "segue",
    "P156": "seguito da",
    "P1365": "sostituisce",
    "P1366": "sostituito da",
    "P807": "separato da",
    "P7888": "confluito in",
    "P361": "parte di",
    "P463": "membro di",
}
VALORI_PROPRIETA = " ".join(f"(p:{p} ps:{p} \"{p}\")" for p in PROPRIETA)

PARTITI_ITALIANI = """?p wdt:P31/wdt:P279* wd:Q7278 ; wdt:P17 wd:Q38 .
  OPTIONAL { ?p wdt:P576 ?fine }
  FILTER(!BOUND(?fine) || ?fine >= "1990-01-01T00:00:00Z"^^xsd:dateTime)"""

QUERY_WIKIDATA = {
    "conteggi": f"""SELECT (COUNT(DISTINCT ?p) AS ?partiti) (COUNT(DISTINCT ?n) AS ?con_nascita)
  (COUNT(DISTINCT ?f) AS ?con_fine) (COUNT(DISTINCT ?r) AS ?con_relazioni) WHERE {{
  {PARTITI_ITALIANI}
  OPTIONAL {{ ?p wdt:P571 ?x . BIND(?p AS ?n) }}
  OPTIONAL {{ ?p wdt:P576 ?y . BIND(?p AS ?f) }}
  OPTIONAL {{ ?p wdt:P155|wdt:P156|wdt:P1365|wdt:P1366|wdt:P807|wdt:P7888 ?z . BIND(?p AS ?r) }}
}}""",
    "relazioni": f"""SELECT ?p ?pLabel ?prop ?altro ?altroLabel ?tipoAltroLabel ?data ?inizio ?fineq
  (COUNT(DISTINCT ?ref) AS ?riferimenti) WHERE {{
  {PARTITI_ITALIANI}
  VALUES (?pr ?ps ?prop) {{ {VALORI_PROPRIETA} }}
  ?p ?pr ?st . ?st ?ps ?altro .
  OPTIONAL {{ ?altro wdt:P31 ?tipoAltro }}
  OPTIONAL {{ ?st pq:P585 ?data }} OPTIONAL {{ ?st pq:P580 ?inizio }} OPTIONAL {{ ?st pq:P582 ?fineq }}
  OPTIONAL {{ ?st prov:wasDerivedFrom ?ref }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "it,en". }}
}} GROUP BY ?p ?pLabel ?prop ?altro ?altroLabel ?tipoAltroLabel ?data ?inizio ?fineq LIMIT 5000""",
    "riferimenti_per_proprieta": f"""SELECT ?prop (COUNT(?st) AS ?dichiarazioni) (COUNT(DISTINCT ?conref) AS ?con_riferimento)
  (COUNT(DISTINCT ?condata) AS ?con_data) WHERE {{
  {PARTITI_ITALIANI}
  VALUES (?pr ?ps ?prop) {{ {VALORI_PROPRIETA} }}
  ?p ?pr ?st .
  OPTIONAL {{ ?st prov:wasDerivedFrom ?r . BIND(?st AS ?conref) }}
  OPTIONAL {{ ?st pq:P585|pq:P580|pq:P582 ?d . BIND(?st AS ?condata) }}
}} GROUP BY ?prop""",
    "coalizioni": f"""SELECT ?c ?cLabel ?tipoLabel (COUNT(DISTINCT ?p) AS ?partiti) (SAMPLE(?pLabel) AS ?esempio)
  (MIN(?inizio) AS ?primo_inizio) WHERE {{
  {PARTITI_ITALIANI}
  ?p p:P361|p:P463 ?st . ?st ps:P361|ps:P463 ?c .
  ?c wdt:P31 ?tipo . FILTER NOT EXISTS {{ ?c wdt:P31/wdt:P279* wd:Q7278 }}
  OPTIONAL {{ ?st pq:P580 ?inizio }}
  ?p rdfs:label ?pLabel . FILTER(LANG(?pLabel) = "it")
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "it,en". }}
}} GROUP BY ?c ?cLabel ?tipoLabel ORDER BY DESC(?partiti) LIMIT 300""",
    "governo_conte_2": """SELECT ?propLabel ?valLabel ?inizio ?fine WHERE {
  ?g rdfs:label "Second Conte government"@en . ?g ?pr ?st . ?prop wikibase:claim ?pr ; wikibase:statementProperty ?ps . ?st ?ps ?val .
  OPTIONAL { ?st pq:P580 ?inizio } OPTIONAL { ?st pq:P582 ?fine }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "it,en". }
} LIMIT 300""",
}


def nomi_partiti() -> list[str]:
    with CSV_PARTITI.open(encoding="utf-8") as f:
        nomi = {r["partito"] for r in csv.DictReader(f)}
    return sorted({re.sub(r"\s*\([^)]*\)\s*$", "", n).strip() for n in nomi})


def query_corrispondenze() -> str:
    valori = " ".join(json.dumps(n, ensure_ascii=False) + "@it" for n in nomi_partiti())
    return f"""SELECT ?nome ?p ?pLabel ?nascita ?fine WHERE {{
  VALUES ?nome {{ {valori} }}
  {{ ?p rdfs:label ?nome }} UNION {{ ?p skos:altLabel ?nome }}
  ?p wdt:P31/wdt:P279* wd:Q7278 .
  OPTIONAL {{ ?p wdt:P571 ?nascita }} OPTIONAL {{ ?p wdt:P576 ?fine }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "it,en". }}
}}"""


def scarica(url: str, accetta: str = "*/*", limite: int = 80_000_000, timeout: int = 120) -> tuple[bytes, str]:
    richiesta = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": accetta})
    with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
        return risposta.read(limite), f"{risposta.status} {risposta.headers.get('Content-Type', '')} -> {risposta.geturl()}"


def wikidata(query: str) -> list[dict[str, str]]:
    url = f"{WIKIDATA}?{urllib.parse.urlencode({'query': query, 'format': 'json'})}"
    corpo, _ = scarica(url, "application/sparql-results+json", timeout=90)
    time.sleep(2)
    return [{k: v["value"] for k, v in r.items()} for r in json.loads(corpo)["results"]["bindings"]]


def semplifica(righe: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{k: v.replace("http://www.wikidata.org/entity/", "wd:") for k, v in r.items()} for r in righe]


def parte_wikidata() -> tuple[dict[str, Any], str]:
    risultati: dict[str, Any] = {}
    report = "## 1. Wikidata (CC0)\n\n"
    for nome, query in [*QUERY_WIKIDATA.items(), ("corrispondenze_governi_partiti", query_corrispondenze())]:
        try:
            righe = semplifica(wikidata(query))
        except Exception as e:  # noqa: BLE001 - la sonda registra ogni errore e va avanti
            risultati[nome] = {"errore": f"{type(e).__name__}: {e}"}
            report += f"### {nome}\n\nErrore: `{risultati[nome]['errore']}`\n\n"
            continue
        risultati[nome] = righe
        report += f"### {nome} ({len(righe)} righe)\n\n"
        if nome == "relazioni":
            per_prop: dict[str, int] = {}
            for r in righe:
                per_prop[r["prop"]] = per_prop.get(r["prop"], 0) + 1
            report += "Righe per proprietà: " + ", ".join(f"{PROPRIETA[p]} ({p}) {n}" for p, n in sorted(per_prop.items())) + "\n\n"
            esempi = [r for r in righe if r["prop"] in ("P807", "P7888", "P1365", "P155")]
            report += tabella(esempi, 80) + "\n"
        elif nome == "corrispondenze_governi_partiti":
            trovati = {r["nome"] for r in righe}
            mancanti = [n for n in nomi_partiti() if n not in trovati]
            doppi = sorted({r["nome"] for r in righe if sum(x["nome"] == r["nome"] for x in righe) > 1})
            report += (f"Partiti di governi_partiti.csv trovati per nome: {len(trovati)} su {len(nomi_partiti())}. "
                       f"Più di un elemento per lo stesso nome: {len(doppi)}.\n\n"
                       f"Non trovati: {', '.join(mancanti) or 'nessuno'}\n\nDoppi: {', '.join(doppi) or 'nessuno'}\n\n")
            report += tabella(righe, 100) + "\n"
        else:
            report += tabella(righe, 80) + "\n"
    return risultati, report


ITALIA = "(SELECT id FROM country WHERE name_short = 'ITA')"
QUERY_PARLGOV = {
    "cambi_di_partito_dal_1990": f"""SELECT c.date AS data, p.name AS da, n.name AS a, c.description, c.comment
  FROM party_change c JOIN party p ON p.id = c.party_id JOIN party n ON n.id = c.party_id_new
  WHERE p.country_id = {ITALIA} AND c.date >= '1988-01-01' ORDER BY c.date""",
    "governi_dal_1990": f"""SELECT c.start_date AS inizio, c.name AS governo, c.caretaker,
  GROUP_CONCAT(p.name_short, ', ') AS partiti FROM cabinet c
  LEFT JOIN cabinet_party cp ON cp.cabinet_id = c.id LEFT JOIN party p ON p.id = cp.party_id
  WHERE c.country_id = {ITALIA} AND c.start_date >= '1989-07-01' GROUP BY c.id ORDER BY c.start_date""",
    "date_a_meta_anno": f"""SELECT COUNT(*) AS cambi, SUM(c.date LIKE '%-07-01') AS al_primo_luglio
  FROM party_change c JOIN party p ON p.id = c.party_id WHERE p.country_id = {ITALIA}""",
}


def parte_parlgov() -> tuple[dict[str, Any], str]:
    risultati: dict[str, Any] = {}
    report = "## 2. ParlGov\n\n"
    try:
        corpo, tipo = scarica("https://parlgov.org/data/parlgov-development.db")
        risultati["db"] = {"tipo": tipo, "byte": len(corpo)}
        report += f"Database: {tipo}, {len(corpo)} byte\n\n"
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            f.write(corpo)
            f.flush()
            con = sqlite3.connect(f.name)
            tabelle = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")]
            risultati["tabelle"] = tabelle
            report += "Tabelle: " + ", ".join(tabelle) + "\n\n"
            for nome in tabelle:
                if not re.search(r"party_name_change|cabinet_support|alliance|confidence|^cabinet$", nome):
                    continue
                colonne = [r[1] for r in con.execute(f"PRAGMA table_info('{nome}')")]
                report += f"### {nome}\n\nColonne: {', '.join(colonne)}\n\n"
                righe: list[dict[str, str]] = []
                try:
                    if "country_id" in colonne:
                        cur = con.execute(f"SELECT * FROM '{nome}' WHERE country_id = (SELECT id FROM country WHERE name_short = 'ITA')")
                    elif "party_id" in colonne:
                        cur = con.execute(f"SELECT * FROM '{nome}' WHERE party_id IN (SELECT id FROM party WHERE country_id = "
                                          "(SELECT id FROM country WHERE name_short = 'ITA'))")
                    elif "cabinet_id" in colonne:
                        cur = con.execute(f"SELECT * FROM '{nome}' WHERE cabinet_id IN (SELECT id FROM cabinet WHERE country_id = "
                                          "(SELECT id FROM country WHERE name_short = 'ITA'))")
                    else:
                        cur = con.execute(f"SELECT * FROM '{nome}' LIMIT 40")
                    righe = [{c: str(v) for c, v in zip(colonne, riga)} for riga in cur.fetchall()]
                except sqlite3.Error as e:
                    report += f"Errore: `{e}`\n\n"
                risultati[nome] = righe
                report += f"Righe dell'Italia: {len(righe)}\n\n" + tabella(righe, 60) + "\n"
            for nome, query in QUERY_PARLGOV.items():
                try:
                    cur = con.execute(query)
                    colonne = [d[0] for d in cur.description]
                    righe = [{c: str(v) for c, v in zip(colonne, riga)} for riga in cur.fetchall()]
                except sqlite3.Error as e:
                    righe = []
                    report += f"### {nome}\n\nErrore: `{e}`\n\n"
                    continue
                risultati[nome] = righe
                report += f"### {nome} ({len(righe)} righe)\n\n" + tabella(righe, 150) + "\n"
    except Exception as e:  # noqa: BLE001
        risultati["errore"] = f"{type(e).__name__}: {e}"
        report += f"Errore: `{risultati['errore']}`\n\n"
    report += "### Licenza su Harvard Dataverse\n\n"
    try:
        corpo, _ = scarica("https://dataverse.harvard.edu/api/search?q=ParlGov&type=dataset&per_page=10", "application/json")
        for voce in json.loads(corpo)["data"]["items"]:
            pid = voce.get("global_id", "")
            if "parlgov" not in voce.get("name", "").lower():
                continue
            dettaglio, _ = scarica(f"https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId={pid}", "application/json")
            versione = json.loads(dettaglio)["data"]["latestVersion"]
            licenza = versione.get("license") or versione.get("termsOfUse")
            risultati.setdefault("licenze", []).append({"nome": voce.get("name"), "id": pid, "licenza": licenza})
            report += f"- {voce.get('name')} ({pid}): `{json.dumps(licenza, ensure_ascii=False)[:400]}`\n"
    except Exception as e:  # noqa: BLE001
        report += f"Errore: `{type(e).__name__}: {e}`\n"
    return risultati, report + "\n"


PAGINE_ELIGENDO = [
    "https://elezionistorico.interno.gov.it/",
    "https://elezionistorico.interno.gov.it/eligendo/opendata.php",
    "https://elezionistorico.interno.gov.it/eligendo/info_opendata.php",
    "https://elezionistorico.interno.gov.it/index.php?tpel=C&dtel=27/03/1994&tpa=I&tpe=A&lev0=0&levsut0=0&es0=S&ms=S",
    "https://elezionistorico.interno.gov.it/index.php?tpel=C&dtel=09/04/2006&tpa=I&tpe=A&lev0=0&levsut0=0&es0=S&ms=S",
    "https://dait.interno.gov.it/elezioni/open-data",
    "https://dait.interno.gov.it/elezioni/trasparenza",
]
PAROLE_ELIGENDO = re.compile(r"coalizion\w*|contrassegn\w*|licenz\w*|creative commons|cc[- ]by[- \w.]*|iodl[\w .]*|open ?data", re.IGNORECASE)
TUTTI_I_LINK = re.compile(r"""(?:href|src|data-url|value)=["']([^"'#]+\.(?:zip|csv|txt|xlsx?|json|php)[^"']*)["']""", re.IGNORECASE)
CONTESTO = re.compile(r"licenz|creative commons|iodl|condizioni d'uso|coalizion", re.IGNORECASE)
LINK_DATI = re.compile(r"""href=["']([^"']*(?:\.zip|\.csv|\.txt|\.xlsx?|opendata|open-data|download)[^"']*)["']""", re.IGNORECASE)


def parte_eligendo() -> tuple[dict[str, Any], str]:
    risultati: list[dict[str, Any]] = []
    report = "## 3. Eligendo (Ministero dell'Interno)\n\n"
    for url in PAGINE_ELIGENDO:
        try:
            corpo, tipo = scarica(url, limite=3_000_000, timeout=60)
            testo = corpo.decode("utf-8", "replace")
            voce = {"url": url, "tipo": tipo, "byte": len(corpo),
                    "parole": sorted({p.lower().strip() for p in PAROLE_ELIGENDO.findall(testo)})[:40],
                    "link": sorted({urllib.parse.urljoin(url, l) for l in LINK_DATI.findall(testo)})[:40],
                    "tutti_i_link": sorted({urllib.parse.urljoin(url, l) for l in TUTTI_I_LINK.findall(testo)})[:200],
                    "contesti": [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", testo[max(0, m.start() - 300): m.end() + 300]))
                                 for m in CONTESTO.finditer(testo)][:12],
                    "inizio": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", testo))[:1500]}
        except Exception as e:  # noqa: BLE001
            voce = {"url": url, "errore": f"{type(e).__name__}: {e}"}
        risultati.append(voce)
        report += f"### {url}\n\n" + (voce.get("errore") or f"{voce['tipo']}, {voce['byte']} byte") + "\n\n"
        if "parole" in voce:
            report += f"Parole: {voce['parole']}\n\n" + "".join(f"- {l}\n" for l in voce["link"]) + "\n"
            if "opendata" in url:
                report += "Tutti i link a file e pagine:\n\n" + "".join(f"- {l}\n" for l in voce["tutti_i_link"]) + "\n"
                report += "".join(f"> …{c}…\n\n" for c in voce["contesti"])
            report += f"> {voce['inizio'][:800]}\n\n"
        time.sleep(1)
    return {"pagine": risultati}, report


QUERY_PARLAMENTO = {
    "camera": {
        "classi_utili": """SELECT ?c (COUNT(?s) AS ?n) WHERE { ?s a ?c
  FILTER(REGEX(STR(?c), "overn|lezion|lista|partit|incaric|mandato|coalizion", "i")) } GROUP BY ?c ORDER BY DESC(?n)""",
        "proprieta_governo": """SELECT ?p (COUNT(*) AS ?n) (SAMPLE(?o) AS ?esempio) WHERE { ?g a ocd:governo ; ?p ?o } GROUP BY ?p""",
        "proprieta_membro_governo": """SELECT ?p (COUNT(*) AS ?n) (SAMPLE(?o) AS ?esempio) WHERE { ?m a ocd:membroGoverno ; ?p ?o } GROUP BY ?p""",
        "membri_governo_esempio": """SELECT ?m ?p ?o WHERE { { SELECT ?m WHERE { ?m a ocd:membroGoverno } LIMIT 4 } ?m ?p ?o }""",
        "proprieta_mandato": """SELECT ?p (COUNT(*) AS ?n) (SAMPLE(?o) AS ?esempio) WHERE { ?m a ocd:mandatoCamera ; ?p ?o } GROUP BY ?p""",
        "proprieta_elezione": """SELECT ?p (COUNT(*) AS ?n) (SAMPLE(?o) AS ?esempio) WHERE { ?e a ocd:elezione ; ?p ?o } GROUP BY ?p""",
        "elezioni_esempio": """SELECT ?e ?p ?o WHERE { { SELECT ?e WHERE { ?e a ocd:elezione } LIMIT 5 } ?e ?p ?o }""",
        "liste_per_legislatura": """SELECT ?leg (COUNT(DISTINCT ?lista) AS ?liste) (SAMPLE(?lista) AS ?esempio) WHERE {
  ?m a ocd:mandatoCamera ; ocd:rif_leg ?leg ; ocd:rif_elezione ?e . ?e ocd:lista ?lista } GROUP BY ?leg ORDER BY ?leg""",
        "fiducia_al_governo": """SELECT ?leg (COUNT(DISTINCT ?v) AS ?n) (SAMPLE(?t) AS ?esempio) WHERE {
  ?v a ocd:votazione ; ocd:rif_leg ?leg ; dc:description ?t .
  FILTER(REGEX(?t, "fiducia al governo|mozione di fiducia|fiducia al (I|II|III|IV)", "i")) } GROUP BY ?leg ORDER BY ?leg""",
    },
    "senato": {
        "classi_utili": """SELECT ?c (COUNT(?s) AS ?n) WHERE { ?s a ?c
  FILTER(REGEX(STR(?c), "overn|lezion|lista|partit|aric|mandato|coalizion", "i")) } GROUP BY ?c ORDER BY DESC(?n)""",
        "fiducia_per_legislatura": """SELECT ?leg (COUNT(DISTINCT ?v) AS ?n) (SAMPLE(?t) AS ?esempio) WHERE {
  ?v a osr:Votazione ; osr:legislatura ?leg ; rdfs:label ?t .
  FILTER(CONTAINS(LCASE(STR(?t)), "fiducia")) } GROUP BY ?leg ORDER BY ?leg""",
        "fiducia_senza_ddl": """SELECT ?leg ?t ?data WHERE {
  ?v a osr:Votazione ; osr:legislatura ?leg ; rdfs:label ?t .
  OPTIONAL { ?v osr:seduta ?s . ?s osr:dataSeduta ?data }
  FILTER(CONTAINS(LCASE(STR(?t)), "fiducia") && !CONTAINS(LCASE(STR(?t)), "ddl")) } ORDER BY ?data LIMIT 200""",
        "proprieta_mandato_senato": """SELECT ?p (COUNT(*) AS ?n) (SAMPLE(?o) AS ?esempio) WHERE { ?m a ocd:mandatoSenato ; ?p ?o } GROUP BY ?p""",
    },
}


def parte_parlamento(ramo: str) -> tuple[dict[str, Any], str]:
    risultati: dict[str, Any] = {}
    report = f"## 4. {ramo.capitalize()}\n\n"
    for nome, query in QUERY_PARLAMENTO[ramo].items():
        try:
            righe = interroga(ramo, query, timeout=180)
        except Exception as e:  # noqa: BLE001
            risultati[nome] = {"errore": f"{type(e).__name__}: {e}"}
            report += f"### {nome}\n\nErrore: `{risultati[nome]['errore']}`\n\n"
            continue
        risultati[nome] = righe
        report += f"### {nome} ({len(righe)} righe)\n\n" + tabella(righe, 80) + "\n"
    return risultati, report


def main() -> int:
    parti = sys.argv[1:] or ["wikidata", "parlgov", "eligendo", "camera", "senato"]
    report = "# Sonda rapporti tra i partiti\n\n"
    CARTELLA_SAMPLES.mkdir(exist_ok=True)
    for parte in parti:
        if parte == "wikidata":
            risultati, testo = parte_wikidata()
        elif parte == "parlgov":
            risultati, testo = parte_parlgov()
        elif parte == "eligendo":
            risultati, testo = parte_eligendo()
        else:
            risultati, testo = parte_parlamento(parte)
        (CARTELLA_SAMPLES / f"sonda_partiti_{parte}.json").write_text(json.dumps(risultati, ensure_ascii=False, indent=1, default=str))
        report += testo
    print(report)
    if riepilogo := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(riepilogo, "a", encoding="utf-8") as f:
            f.write(report[:1_000_000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
