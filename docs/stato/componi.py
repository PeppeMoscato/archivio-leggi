"""Compone lo stato del progetto dai file di `docs/stato/` in un solo documento.

Ogni voce (decisione, questione aperta, voce di roadmap, voce del log) è un file a sé,
così due thread che lavorano in parallelo aggiungono file diversi e non vanno in
conflitto. Questo script li rimette insieme nel formato del vecchio
`05_stato_e_decisioni.md`, per leggerli in un colpo solo o per caricarli nel Progetto Claude.

    python docs/stato/componi.py                 # stampa il documento
    python docs/stato/componi.py --uscita F.md   # lo scrive in F.md
    python docs/stato/componi.py --controlla     # controlla solo i file (CI)

Solo libreria standard: gira con qualunque Python 3.10+.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent

# Campi ammessi per ogni tipo di voce: (obbligatori, facoltativi).
CAMPI = {
    "decisioni": (("Data", "Decisione", "Motivo"), ()),
    "aperte": (("Questione",), ()),
    "roadmap": (("Fase", "Voce", "Fatto"), ("Nota", "Situazione")),
    "log": (("Data", "Testo"), ()),
}

NOME_DATATO = re.compile(r"^(\d{4}-\d{2}-\d{2})_\d{2}_[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
NOME_NUMERATO = re.compile(r"^\d{2}_[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
DATA = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass
class Voce:
    percorso: Path
    campi: dict[str, str] = field(default_factory=dict)

    def __getitem__(self, chiave: str) -> str:
        return self.campi.get(chiave, "")


def leggi_voce(percorso: Path, ammessi: tuple[str, ...]) -> tuple[Voce, list[str]]:
    """Legge un file `Campo: valore`. Le righe senza un campo ammesso continuano il campo prima."""
    voce = Voce(percorso)
    errori: list[str] = []
    attuale: str | None = None
    righe: dict[str, list[str]] = {}
    schema = re.compile(r"^(" + "|".join(re.escape(c) for c in ammessi) + r"): ?(.*)$")
    for numero, riga in enumerate(percorso.read_text(encoding="utf-8").splitlines(), 1):
        trovato = schema.match(riga)
        if trovato:
            attuale = trovato.group(1)
            if attuale in righe:
                errori.append(f"{percorso}: riga {numero}, campo {attuale} ripetuto")
            righe[attuale] = [trovato.group(2)]
        elif attuale is None:
            if riga.strip():
                errori.append(f"{percorso}: riga {numero}, testo prima del primo campo")
        else:
            righe[attuale].append(riga)
    for chiave, valore in righe.items():
        voce.campi[chiave] = "\n".join(valore).strip()
    return voce, errori


def leggi_tutto(cartella: Path = CARTELLA) -> tuple[dict[str, list[Voce]], str, list[str]]:
    voci: dict[str, list[Voce]] = {}
    errori: list[str] = []
    for tipo, (obbligatori, facoltativi) in CAMPI.items():
        voci[tipo] = []
        sotto = cartella / tipo
        if not sotto.is_dir():
            errori.append(f"{sotto}: cartella mancante")
            continue
        for percorso in sorted(sotto.iterdir()):
            if percorso.name.startswith(".") or percorso.is_dir():
                continue
            nome_ok = NOME_DATATO if tipo in ("decisioni", "log") else NOME_NUMERATO
            if not nome_ok.match(percorso.name):
                atteso = (
                    "AAAA-MM-GG_NN_parole-chiave.md"
                    if tipo in ("decisioni", "log")
                    else "NN_parole-chiave.md"
                )
                errori.append(f"{percorso}: nome non valido, atteso {atteso}")
                continue
            voce, sbagli = leggi_voce(percorso, obbligatori + facoltativi)
            errori += sbagli
            for chiave in obbligatori:
                if not voce[chiave]:
                    errori.append(f"{percorso}: manca il campo {chiave}")
            if tipo in ("decisioni", "log") and voce["Data"]:
                if not DATA.match(voce["Data"]):
                    errori.append(f"{percorso}: Data deve cominciare con AAAA-MM-GG")
                elif voce["Data"][:10] != percorso.name[:10]:
                    errori.append(f"{percorso}: la Data non coincide con la data nel nome del file")
            if tipo == "roadmap" and voce["Fatto"] not in ("sì", "no"):
                errori.append(f"{percorso}: Fatto deve essere 'sì' o 'no'")
            if tipo == "decisioni" and "\n" in voce["Decisione"] + voce["Motivo"]:
                errori.append(f"{percorso}: Decisione e Motivo vanno su una riga (finiscono in una tabella)")
            voci[tipo].append(voce)
    fase = cartella / "fase.md"
    testo_fase = fase.read_text(encoding="utf-8").strip() if fase.is_file() else ""
    if not testo_fase:
        errori.append(f"{fase}: file mancante o vuoto")
    return voci, testo_fase, errori


def cella(testo: str) -> str:
    return testo.replace("|", "\\|")


def rientra(testo: str) -> str:
    """Rientra le righe successive alla prima, così un testo su più righe resta nel suo punto elenco."""
    return testo.replace("\n", "\n  ")


def componi(voci: dict[str, list[Voce]], testo_fase: str) -> str:
    righe = [
        "# Stato del progetto e decisioni",
        "",
        "Documento composto da `docs/stato/` con `python docs/stato/componi.py`: non modificarlo a mano.",
        "Le regole per aggiornarlo sono in `docs/05_stato_e_decisioni.md`.",
        "",
        "## Fase attuale",
        testo_fase,
        "",
    ]
    for voce in voci["roadmap"]:
        if voce["Situazione"]:
            righe.append(f"- **{voce['Voce']}**: {rientra(voce['Situazione'])}")
    righe += ["", "## Decisioni prese", "| Data | Decisione | Motivo |", "|---|---|---|"]
    for voce in voci["decisioni"]:
        righe.append(f"| {voce['Data']} | {cella(voce['Decisione'])} | {cella(voce['Motivo'])} |")
    righe += ["", "## Ancora da decidere"]
    righe += [f"- {rientra(voce['Questione'])}" for voce in voci["aperte"]]
    righe += ["", "## Roadmap"]
    fasi: dict[str, list[Voce]] = {}
    for voce in voci["roadmap"]:
        fasi.setdefault(voce["Fase"], []).append(voce)
    for nome, elenco in fasi.items():
        righe += [f"### {nome}"]
        for voce in elenco:
            segno = "x" if voce["Fatto"] == "sì" else " "
            nota = f" — {voce['Nota']}" if voce["Nota"] else ""
            righe.append(f"- [{segno}] {voce['Voce']}{nota}")
        righe.append("")
    righe += ["## Log sessioni"]
    righe += [f"- {voce['Data']}: {rientra(voce['Testo'])}" for voce in voci["log"]]
    return "\n".join(righe) + "\n"


def main(argomenti: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--uscita", type=Path, help="scrive il documento in questo file")
    parser.add_argument("--controlla", action="store_true", help="controlla i file senza stampare")
    opzioni = parser.parse_args(argomenti)
    voci, testo_fase, errori = leggi_tutto()
    if errori:
        print("\n".join(errori), file=sys.stderr)
        return 1
    if opzioni.controlla:
        conteggi = ", ".join(f"{tipo} {len(elenco)}" for tipo, elenco in voci.items())
        print(f"docs/stato in ordine: {conteggi}")
        return 0
    documento = componi(voci, testo_fase)
    if opzioni.uscita:
        opzioni.uscita.write_text(documento, encoding="utf-8")
    else:
        sys.stdout.write(documento)
    return 0


if __name__ == "__main__":
    sys.exit(main())
