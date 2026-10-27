"""Spike: cosa restituisce davvero l'API open data di Normattiva.

Interroga Normattiva tramite `normattiva-sdk` per cinque leggi dell'MVP e per i
conteggi degli atti dal 1990, poi confronta le risposte con i campi dello
schema v1 (`docs/01_schema_dati.md`). Non usa il database.

Uscite:
- `samples/risultati.json`: le risposte grezze, già tradotte in dizionari;
- il report in Markdown su stdout (e nel riepilogo del job, su GitHub Actions).

Ogni passo che fallisce viene registrato come errore, senza fermare gli altri:
lo scopo è sapere cosa funziona e cosa no.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from normattiva import ClasseProvvedimento, Format, Normattiva, NormattivaError, Urn
from normattiva.modelli import ExportMode

CARTELLA_SAMPLES = Path(__file__).parent / "samples"
INIZIO_PERIMETRO = date(1990, 1, 1)

# Perimetro iniziale (docs/00_visione.md) e tipi da archiviare più avanti.
PERIMETRO = ("LEGGE", "LEGGE COSTITUZIONALE", "DECRETO-LEGGE", "DECRETO LEGISLATIVO")
FUTURI = (
    "DECRETO DEL PRESIDENTE DELLA REPUBBLICA",
    "DECRETO DEL PRESIDENTE DEL CONSIGLIO DEI MINISTRI",
    "DECRETO MINISTERIALE",
)


@dataclass(frozen=True)
class AttoDiProva:
    nome: str
    denominazione: str
    data: date
    numero: int
    articolo: str | None = None
    atteso: str = ""

    @property
    def urn(self) -> Urn:
        costruttori = {
            "LEGGE": Urn.legge,
            "DECRETO-LEGGE": Urn.decreto_legge,
            "DECRETO LEGISLATIVO": Urn.decreto_legislativo,
        }
        return costruttori[self.denominazione](self.data.year, self.numero, data=self.data)


# Cinque leggi MVP di tipo e stato diversi (docs/06_leggi_mvp.md).
ATTI_DI_PROVA = (
    AttoDiProva("Legge Sirchia", "LEGGE", date(2003, 1, 16), 3, "51", "vigente"),
    AttoDiProva("Patente a punti", "DECRETO LEGISLATIVO", date(2002, 1, 15), 9, None, "vigente"),
    AttoDiProva("Reddito di cittadinanza", "DECRETO-LEGGE", date(2019, 1, 28), 4, None, "RdC abrogato"),
    AttoDiProva("Legge Merloni", "LEGGE", date(1994, 2, 11), 109, None, "abrogata"),
    AttoDiProva("Sicurezza sul lavoro", "DECRETO LEGISLATIVO", date(1994, 9, 19), 626, None, "abrogato"),
)


def in_dizionario(oggetto: Any) -> Any:
    """Converte i modelli dell'SDK in strutture serializzabili in JSON."""
    if dataclasses.is_dataclass(oggetto) and not isinstance(oggetto, type):
        return {campo.name: in_dizionario(getattr(oggetto, campo.name)) for campo in dataclasses.fields(oggetto)}
    if isinstance(oggetto, (list, tuple)):
        return [in_dizionario(elemento) for elemento in oggetto]
    if isinstance(oggetto, dict):
        return {str(chiave): in_dizionario(valore) for chiave, valore in oggetto.items()}
    if isinstance(oggetto, (date, Urn)):
        return str(oggetto)
    return oggetto


def prova(passo: str, funzione, *argomenti, **opzioni) -> dict[str, Any]:
    """Esegue un passo e registra il risultato o l'errore."""
    try:
        return {"passo": passo, "ok": True, "dati": funzione(*argomenti, **opzioni)}
    except (NormattivaError, ValueError, KeyError, AttributeError) as errore:
        return {"passo": passo, "ok": False, "errore": f"{type(errore).__name__}: {errore}"}


def conta(client: Normattiva, denominazione: str, classe: ClasseProvvedimento | None = None) -> int:
    esito = client.ricerca_avanzata(
        denominazione=denominazione,
        emanazione=(INIZIO_PERIMETRO, None),
        classe=classe,
        per_pagina=1,
    )
    return esito.totale


def conteggi(client: Normattiva) -> list[dict[str, Any]]:
    righe = []
    for denominazione in PERIMETRO + FUTURI:
        righe.append(
            {
                "denominazione": denominazione,
                "perimetro": denominazione in PERIMETRO,
                "totale": prova("totale", conta, client, denominazione),
                "abrogati": prova("abrogati", conta, client, denominazione, ClasseProvvedimento.ABROGATO),
                "aggiornati": prova("aggiornati", conta, client, denominazione, ClasseProvvedimento.AGGIORNATO),
            }
        )
    return righe


def classe_di(client: Normattiva, atto: AttoDiProva) -> str:
    """Ricava lo stato redazionale filtrando la ricerca per classe."""
    for classe in ClasseProvvedimento:
        esito = client.ricerca_avanzata(
            denominazione=atto.denominazione,
            anno=atto.data.year,
            numero=atto.numero,
            classe=classe,
            per_pagina=1,
        )
        if esito.totale:
            return classe.name
    return "nessuna"


def ricerca(client: Normattiva, atto: AttoDiProva) -> list[Any]:
    esito = client.ricerca_avanzata(
        denominazione=atto.denominazione,
        anno=atto.data.year,
        numero=atto.numero,
        per_pagina=5,
    )
    return [in_dizionario(trovato) for trovato in esito.atti]


def dettaglio(client: Normattiva, atto: AttoDiProva) -> dict[str, Any]:
    letto = client.dettaglio(atto.urn)
    note = letto.note_aggiornamento or ""
    return {
        "estremi": in_dizionario(letto.estremi),
        "gazzetta": in_dizionario(letto.gazzetta),
        "titolo": letto.titolo,
        "finestra": in_dizionario(letto.finestra),
        "permalink": letto.permalink,
        "possibile_troncamento": letto.possibile_troncamento,
        "lunghezza_testo": len(letto.testo),
        "note_aggiornamento_inizio": note[:1500],
    }


def esportazione(client: Normattiva, atto: AttoDiProva) -> dict[str, Any]:
    """Export multivigente in JSON: l'unico punto in cui compaiono abrogazione e modifiche."""
    export = client.start_export(
        format=Format.JSON,
        mode=ExportMode.MULTIVIGENTE,
        massimo_atti=5,
        denominazione=atto.denominazione,
        anno=atto.data.year,
        numero=atto.numero,
    )
    export.wait(timeout=900)
    corpus = export.download()
    risultato = []
    for storico in corpus.atti:
        risultato.append(
            {
                "urn": str(storico.urn),
                "eli": storico.eli,
                "abrogato": storico.abrogato,
                "versioni": [str(versione.vigente_dal) for versione in storico.versioni],
                "aggiornamenti": [
                    {
                        "data": str(aggiornamento.data),
                        "testo": aggiornamento.testo[:300],
                        "riferimenti": in_dizionario(aggiornamento.riferimenti),
                    }
                    for aggiornamento in storico.aggiornamenti
                ],
            }
        )
    return {"atti": risultato}


def risolvi_modificante(client: Normattiva, codice_redazionale: str, giorno: date) -> dict[str, Any]:
    """Dal riferimento di Gazzetta di una modifica risale all'atto che l'ha introdotta."""
    letto = client.dettaglio_da_gazzetta(codice_redazionale, giorno)
    return {"estremi": in_dizionario(letto.estremi), "urn": str(letto.urn), "titolo": letto.titolo}


def primo_riferimento(export: dict[str, Any]) -> tuple[str, date] | None:
    for storico in export.get("atti", []):
        for aggiornamento in storico["aggiornamenti"]:
            for riferimento in aggiornamento["riferimenti"]:
                gazzetta = riferimento.get("gazzetta") or {}
                if gazzetta.get("codice_redazionale") and gazzetta.get("data"):
                    return gazzetta["codice_redazionale"], date.fromisoformat(gazzetta["data"])
    return None


def esegui(client: Normattiva) -> dict[str, Any]:
    risultati: dict[str, Any] = {"eseguito_il": date.today().isoformat(), "atti": [], "conteggi": []}
    for atto in ATTI_DI_PROVA:
        voce: dict[str, Any] = {"nome": atto.nome, "urn": str(atto.urn), "stato_atteso": atto.atteso}
        voce["ricerca"] = prova("ricerca", ricerca, client, atto)
        voce["classe"] = prova("classe", classe_di, client, atto)
        voce["dettaglio"] = prova("dettaglio", dettaglio, client, atto)
        voce["export"] = prova("export", esportazione, client, atto)
        if voce["export"]["ok"] and (riferimento := primo_riferimento(voce["export"]["dati"])):
            voce["modificante"] = prova("modificante", risolvi_modificante, client, *riferimento)
        risultati["atti"].append(voce)
    risultati["conteggi"] = conteggi(client)
    return risultati


def esito_breve(passo: dict[str, Any]) -> str:
    return "ok" if passo["ok"] else f"errore ({passo['errore'][:80]})"


def report(risultati: dict[str, Any]) -> str:
    righe = [
        "# Spike Normattiva — risultati",
        "",
        f"Eseguito il {risultati['eseguito_il']}.",
        "",
        "## Atti di prova",
        "",
        "| Atto | URN | Classe | Stato atteso | Ricerca | Dettaglio | Export | Abrogato (export) | Versioni | Modifiche | Modificante risolto |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for voce in risultati["atti"]:
        classe = voce["classe"]["dati"] if voce["classe"]["ok"] else esito_breve(voce["classe"])
        abrogato = versioni = modifiche = "—"
        if voce["export"]["ok"] and voce["export"]["dati"]["atti"]:
            storico = voce["export"]["dati"]["atti"][0]
            abrogato = str(storico["abrogato"])
            versioni = str(len(storico["versioni"]))
            modifiche = str(len(storico["aggiornamenti"]))
        modificante = "—"
        if "modificante" in voce:
            passo = voce["modificante"]
            modificante = passo["dati"]["urn"] if passo["ok"] else esito_breve(passo)
        righe.append(
            f"| {voce['nome']} | `{voce['urn']}` | {classe} | {voce['stato_atteso']} | "
            f"{esito_breve(voce['ricerca'])} | {esito_breve(voce['dettaglio'])} | {esito_breve(voce['export'])} | "
            f"{abrogato} | {versioni} | {modifiche} | {modificante} |"
        )
    righe += [
        "",
        f"## Atti emanati dal {INIZIO_PERIMETRO.isoformat()}",
        "",
        "| Tipo | Nel perimetro | Totale | Abrogati | Aggiornati |",
        "|---|---|---|---|---|",
    ]
    for riga in risultati["conteggi"]:
        valori = [str(riga[chiave]["dati"]) if riga[chiave]["ok"] else "errore" for chiave in ("totale", "abrogati", "aggiornati")]
        righe.append(f"| {riga['denominazione']} | {'sì' if riga['perimetro'] else 'no'} | " + " | ".join(valori) + " |")
    return "\n".join(righe) + "\n"


def main() -> int:
    user_agent = "archivio-leggi spike (+https://github.com/PeppeMoscato/archivio-leggi)"
    with Normattiva(user_agent=user_agent, timeout=120.0) as client:
        risultati = esegui(client)
    CARTELLA_SAMPLES.mkdir(exist_ok=True)
    (CARTELLA_SAMPLES / "risultati.json").write_text(json.dumps(risultati, ensure_ascii=False, indent=2) + "\n")
    testo = report(risultati)
    print(testo)
    if riepilogo := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(riepilogo, "a", encoding="utf-8") as file:
            file.write(testo)
    passi = [voce[chiave] for voce in risultati["atti"] for chiave in ("ricerca", "dettaglio")]
    return 0 if any(passo["ok"] for passo in passi) else 1


if __name__ == "__main__":
    sys.exit(main())
