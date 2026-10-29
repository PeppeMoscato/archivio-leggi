"""Sonda: dove si trova il "perché" di una legge.

Serve a progettare il contesto delle leggi (perché sono state proposte e
approvate) prima di toccare lo schema. Controlla tre fonti:
1. Normattiva: la premessa del testo originale ("Visto...", "Ritenuta la
   straordinaria necessità ed urgenza di...") di qualche atto dell'MVP;
2. dati.senato.it: le proprietà di un ddl, per trovare testi, relazioni e dossier;
3. dati.camera.it: le proprietà degli atti Camera e dei lavori preparatori.
Per gli indirizzi web trovati (schede, testi) scarica la pagina e cerca i link a
PDF, relazioni e dossier.

Uscite: il report in Markdown su stdout (e nel riepilogo del job su GitHub
Actions) e `samples/sonda_contesto.json` con le risposte grezze.
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

from sonda_parlamento import interroga

CARTELLA_SAMPLES = Path(__file__).parent / "samples"
AGENTE = "archivio-leggi/0.1 (sonda contesto, non commerciale)"

# Atti dell'MVP di tipo diverso: D.L., D.Lgs., legge di iniziativa governativa e parlamentare.
ATTI_NORMATTIVA = [
    "urn:nir:stato:decreto.legge:2018-07-12;87",
    "urn:nir:stato:decreto.legge:2017-06-07;73",
    "urn:nir:stato:decreto.legislativo:2015-03-04;23",
    "urn:nir:stato:legge:2003-01-16;3",
    "urn:nir:stato:legge:2016-05-20;76",
    "urn:nir:stato:decreto.legge:2006-07-04;223",
]

SENATO_LEG14 = "osr:legislatura 14"
QUERY = {
    "senato": {
        "proprieta_documento": """SELECT ?p (COUNT(*) AS ?n) WHERE { ?d a osr:Documento ; ?p ?o } GROUP BY ?p ORDER BY DESC(?n)""",
        "documenti_esempio": """SELECT ?d ?p ?o WHERE { { SELECT ?d WHERE { ?d a osr:Documento } LIMIT 5 } ?d ?p ?o }""",
        "documenti_ddl_15167": """SELECT ?d ?p ?o WHERE { ?d a osr:Documento ; ?q ?x . ?d ?p ?o .
  FILTER(CONTAINS(STR(?x), "15167") || CONTAINS(STR(?x), "1271")) } LIMIT 200""",
        "proprieta_intervento": """SELECT ?p (COUNT(*) AS ?n) WHERE { ?i a osr:Intervento ; ?p ?o } GROUP BY ?p ORDER BY DESC(?n)""",
        "interventi_esempio": """SELECT ?i ?p ?o WHERE { { SELECT ?i WHERE { ?i a osr:Intervento } LIMIT 3 } ?i ?p ?o }""",
        "testo_presentato_per_legislatura": """SELECT ?leg (COUNT(DISTINCT ?d) AS ?fasi) (COUNT(DISTINCT ?t) AS ?con_testo) WHERE {
  ?d a osr:Ddl ; osr:legislatura ?leg . OPTIONAL { ?d osr:testoPresentato ?t } } GROUP BY ?leg ORDER BY ?leg""",
        "ddl_esempi": """SELECT ?leg ?num ?id ?ramo ?testo WHERE { ?d a osr:Ddl ; osr:legislatura ?leg ; osr:numeroFase ?num ;
  osr:idDdl ?id ; osr:ramo ?ramo . OPTIONAL { ?d osr:testoPresentato ?testo }
  FILTER((?leg = 14 && STR(?num) = "1271") || (?leg = 18 && STR(?num) = "1018") || (?leg = 17 && STR(?num) = "2081")) }""",
    },
    "camera": {
        "proprieta_atto_xiv": """SELECT ?p (COUNT(DISTINCT ?o) AS ?n) WHERE { ?a a ocd:atto ;
  ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_14> ; ?p ?o } GROUP BY ?p ORDER BY DESC(?n)""",
        "legge_3_2003": """SELECT DISTINCT ?l ?p ?o WHERE { ?l a ocd:legge ;
  ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_14> ; ocd:lex ?lex ; ?p ?o .
  FILTER(CONTAINS(STR(?lex), "2003-01-16;3")) }""",
        "lavori_preparatori_3_2003": """SELECT DISTINCT ?lp ?p ?o WHERE { ?l a ocd:legge ;
  ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_14> ; ocd:lex ?lex ; ocd:lavoriPreparatori ?lp .
  ?lp ?p ?o . FILTER(CONTAINS(STR(?lex), "2003-01-16;3")) }""",
        "atti_3_2003": """SELECT DISTINCT ?a ?p ?o WHERE { ?l a ocd:legge ;
  ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_14> ; ocd:lex ?lex ; ocd:lavoriPreparatori ?lp .
  ?lp ocd:rif_attoCamera ?a . ?a ?p ?o . FILTER(CONTAINS(STR(?lex), "2003-01-16;3")) }""",
        "atti_3_2003_un_salto": """SELECT DISTINCT ?p ?o ?p2 ?o2 WHERE { ?l a ocd:legge ;
  ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_14> ; ocd:lex ?lex ; ocd:lavoriPreparatori ?lp .
  ?lp ocd:rif_attoCamera ?a . ?a ?p ?o . ?o ?p2 ?o2 . FILTER(CONTAINS(STR(?lex), "2003-01-16;3")) } LIMIT 300""",
        "atto_xviii_esempio": """SELECT DISTINCT ?p ?o WHERE { ?l a ocd:legge ;
  ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_18> ; ocd:lex ?lex ; ocd:lavoriPreparatori ?lp .
  ?lp ocd:rif_attoCamera ?a . ?a ?p ?o . FILTER(CONTAINS(STR(?lex), "2019-01-28;4")) }""",
        "classi_documenti": """SELECT ?c (COUNT(DISTINCT ?s) AS ?n) WHERE { ?s a ?c .
  FILTER(REGEX(STR(?c), "test|document|dossier|relaz|resocont|seduta|intervent|dibattit", "i")) } GROUP BY ?c""",
    },
}

LINK_UTILI = re.compile(r"""href=["']([^"']*(?:\.pdf|relaz|dossier|testi|stampat|Ddliter|leg\d+)[^"']*)["']""", re.IGNORECASE)
PAROLE = re.compile(r"relazione (?:illustrativa|tecnica|introduttiva)|analisi (?:tecnico-normativa|dell'impatto)|dossier|AIR", re.IGNORECASE)


def breve(valore: Any, n: int = 200) -> str:
    testo = re.sub(r"\s+", " ", str(valore)).replace("|", "\\|")
    return testo if len(testo) <= n else testo[: n - 1] + "…"


def premesse() -> tuple[list[dict[str, Any]], str]:
    from normattiva import Normattiva

    righe: list[dict[str, Any]] = []
    report = "## 1. Normattiva: premessa del testo originale\n\n"
    with Normattiva(user_agent=AGENTE, timeout=120.0) as client:
        for urn in ATTI_NORMATTIVA:
            voce: dict[str, Any] = {"urn": urn}
            try:
                atto = client.dettaglio(urn, vigenza="originale")
                voce |= {"titolo": atto.titolo, "preambolo": atto.preambolo, "html": len(atto.testo_html),
                         "testo_inizio": atto.testo[:600]}
                voce["html_inizio"] = atto.testo_html[:4000]
            except Exception as e:  # noqa: BLE001 - la sonda registra ogni errore e va avanti
                voce["errore"] = f"{type(e).__name__}: {e}"
            righe.append(voce)
            report += f"### {urn}\n\n"
            if "errore" in voce:
                report += f"Errore: `{voce['errore']}`\n\n"
                continue
            preambolo = voce["preambolo"] or ""
            report += f"- Titolo: {breve(voce['titolo'])}\n- Preambolo: {len(preambolo)} caratteri\n\n"
            report += f"- HTML: {voce['html']} caratteri\n\n"
            report += f"```\n{preambolo[:2500] or '(vuoto) ' + voce['testo_inizio']}\n```\n\n"
            report += f"```html\n{voce['html_inizio']}\n```\n\n"
            time.sleep(1)
    return righe, report


def pagina(url: str) -> dict[str, Any]:
    richiesta = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(richiesta, timeout=60) as risposta:
            corpo = risposta.read(3_000_000).decode("utf-8", "replace")
            tipo = risposta.headers.get("Content-Type", "")
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        return {"url": url, "errore": f"{type(e).__name__}: {e}"}
    link = sorted({urllib.parse.urljoin(url, l) for l in LINK_UTILI.findall(corpo)})
    return {"url": url, "tipo": tipo, "byte": len(corpo), "parole": sorted({p.lower() for p in PAROLE.findall(corpo)}),
            "link": link[:60]}


def parlamento(ramo: str) -> tuple[dict[str, Any], str]:
    risultati: dict[str, Any] = {}
    report = f"## {'2. Senato' if ramo == 'senato' else '3. Camera'}\n\n"
    indirizzi: set[str] = set()
    for nome, query in QUERY[ramo].items():
        try:
            righe = interroga(ramo, query)
            risultati[nome] = righe
        except Exception as e:  # noqa: BLE001
            risultati[nome] = {"errore": f"{type(e).__name__}: {e}"}
            report += f"### {nome}\n\nErrore: `{risultati[nome]['errore']}`\n\n"
            continue
        report += f"### {nome} ({len(righe)} righe)\n\n"
        if righe:
            colonne = list(righe[0])
            report += "| " + " | ".join(colonne) + " |\n|" + "---|" * len(colonne) + "\n"
            for r in righe[:120]:
                report += "| " + " | ".join(breve(r.get(c, "")) for c in colonne) + " |\n"
            report += "\n"
        for r in righe:
            for valore in r.values():
                if re.match(r"https?://", valore) and not re.search(r"dati\.(senato|camera)\.it|purl\.org|w3\.org|xmlns", valore):
                    indirizzi.add(valore)
    if ramo == "senato" and isinstance(risultati.get("ddl_esempi"), list):
        for r in risultati["ddl_esempi"]:
            leg, iddl = r["leg"], r["id"]
            base = f"https://www.senato.it/leg/{leg}/BGT/Schede/Ddliter"
            indirizzi |= {f"{base}/{iddl}.htm", f"{base}/testi/{iddl}_testi.htm", f"{base}/documenti/{iddl}_documenti.htm"}
            if r.get("testo"):
                indirizzi.add(f"https://www.senato.it/uri-res/N2Ls?{r['testo']}")
    report += "### Pagine web collegate\n\n"
    risultati["pagine"] = []
    for url in sorted(indirizzi)[:25]:
        esito = pagina(url)
        risultati["pagine"].append(esito)
        report += f"- {url}: " + (esito.get("errore") or f"{esito['tipo']}, {esito['byte']} byte, parole {esito['parole']}") + "\n"
        for link in esito.get("link", [])[:25]:
            report += f"  - {link}\n"
        time.sleep(1)
    return risultati, report + "\n"


def main() -> int:
    parti = sys.argv[1:] or ["normattiva", "senato", "camera"]
    tutto: dict[str, Any] = {}
    report = "# Sonda contesto delle leggi\n\n"
    for parte in parti:
        if parte == "normattiva":
            tutto[parte], testo = premesse()
        else:
            tutto[parte], testo = parlamento(parte)
        report += testo
    CARTELLA_SAMPLES.mkdir(exist_ok=True)
    (CARTELLA_SAMPLES / "sonda_contesto.json").write_text(json.dumps(tutto, ensure_ascii=False, indent=1, default=str))
    print(report)
    if riepilogo := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(riepilogo, "a", encoding="utf-8") as f:
            f.write(report[:1_000_000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
