"""I governi della Repubblica dal 1989, per assegnare ogni atto al governo in carica.

Fonte: elenco storico dei governi del Senato (FONTE_URL). Date controllate il
27/10/2026 anche sull'elenco di Wikipedia ("List of Italian governments").
Come `fine` di ogni governo si usa il giuramento del successivo: così ogni
giorno ha un solo governo, compresi i mesi di "affari correnti" dopo le
dimissioni (es. Andreotti VII fino al 28/6/1992).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

FONTE_URL = "https://www.senato.it/legislature/repubblica/governi-della-repubblica"
FILE = Path(__file__).with_name("governi.csv")
# Partiti di ogni governo: nessuna fonte strutturata, si compila a mano con la fonte di ogni riga.
FILE_PARTITI = Path(__file__).with_name("governi_partiti.csv")


@dataclass(frozen=True)
class Governo:
    id: str
    nome: str
    presidente: str
    inizio: date
    fine: date | None


def carica(percorso: Path = FILE) -> list[Governo]:
    with percorso.open(encoding="utf-8") as file:
        righe = sorted(csv.DictReader(file), key=lambda riga: riga["inizio"])
    governi = []
    for indice, riga in enumerate(righe):
        fine = date.fromisoformat(righe[indice + 1]["inizio"]) if indice + 1 < len(righe) else None
        governi.append(Governo(riga["id"], riga["nome"], riga["presidente"], date.fromisoformat(riga["inizio"]), fine))
    return governi


def governo_alla_data(governi: list[Governo], giorno: date) -> str | None:
    """Il governo in carica in quel giorno; il giorno del giuramento conta per il nuovo governo."""
    for governo in governi:
        if governo.inizio <= giorno and (governo.fine is None or giorno < governo.fine):
            return governo.id
    return None


@dataclass(frozen=True)
class PartitoGoverno:
    governo_id: str
    partito: str
    ruolo: str  # governo / appoggio esterno
    fonte_url: str


def carica_partiti(percorso: Path = FILE_PARTITI) -> list[PartitoGoverno]:
    with percorso.open(encoding="utf-8") as file:
        return [PartitoGoverno(r["governo_id"], r["partito"], r["ruolo"], r["fonte_url"]) for r in csv.DictReader(file)]
