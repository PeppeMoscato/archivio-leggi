"""I governi della Repubblica dal 1989, per assegnare ogni atto al governo in carica.

Fonte: elenco storico dei governi del Senato (FONTE_URL). Date controllate il
27/10/2026 anche sull'elenco di Wikipedia ("List of Italian governments").
Come `fine` di ogni governo si usa il giuramento del successivo: così ogni
giorno ha un solo governo, compresi i mesi di "affari correnti" dopo le
dimissioni (es. Andreotti VII fino al 28/6/1992). Il giorno delle dimissioni
(schema v1.6) sta nella colonna `dimissioni`, con la sua fonte.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

FONTE_URL = "https://www.senato.it/legislature/repubblica/governi-della-repubblica"
FILE = Path(__file__).with_name("governi.csv")
# Partiti di ogni governo: nessuna fonte strutturata, si compila a mano con la fonte di ogni riga.
# Regola (30/10/2026): "governo" sono i partiti che la fonte elenca come membri al giuramento (in pratica,
# con almeno un ministro); "appoggio esterno" quelli che la fonte indica come sostegno senza ministri.
# Dal 08/11/2026 (schema v1.6) le righe hanno le date: `inizio` vuoto = dal giuramento, `fine` vuota = fino alla fine
# del governo; `fine` è il primo giorno fuori dalla maggioranza (il giorno delle dimissioni dei ministri del partito
# secondo dati.camera.it, se ci sono, altrimenti quello dell'uscita secondo la fonte). Un partito che entra dopo il
# giuramento (scissione, fusione, ingresso) ha la sua riga con `inizio`; `fonte_date_url` è la fonte delle date,
# quando non è quella della riga. La `nota` si carica.
FILE_PARTITI = Path(__file__).with_name("governi_partiti.csv")


@dataclass(frozen=True)
class Governo:
    id: str
    nome: str
    presidente: str
    inizio: date
    fine: date | None
    dimissioni: date | None = None
    dimissioni_fonte_url: str | None = None


def _data(testo: str | None) -> date | None:
    return date.fromisoformat(testo) if testo else None


def carica(percorso: Path = FILE) -> list[Governo]:
    with percorso.open(encoding="utf-8") as file:
        righe = sorted(csv.DictReader(file), key=lambda riga: riga["inizio"])
    governi = []
    for indice, riga in enumerate(righe):
        fine = date.fromisoformat(righe[indice + 1]["inizio"]) if indice + 1 < len(righe) else None
        governi.append(
            Governo(riga["id"], riga["nome"], riga["presidente"], date.fromisoformat(riga["inizio"]), fine,
                    _data(riga.get("dimissioni")), riga.get("dimissioni_fonte_url") or None)
        )
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
    inizio: date | None = None  # vuoto nel CSV = dal giuramento (lo riempie `con_date`)
    fine: date | None = None  # primo giorno fuori dalla maggioranza; vuota = fino alla fine del governo
    fonte_date_url: str | None = None
    nota: str | None = None


def carica_partiti(percorso: Path = FILE_PARTITI) -> list[PartitoGoverno]:
    with percorso.open(encoding="utf-8") as file:
        return [
            PartitoGoverno(r["governo_id"], r["partito"], r["ruolo"], r["fonte_url"], _data(r.get("inizio")),
                           _data(r.get("fine")), r.get("fonte_date_url") or None, r.get("nota") or None)
            for r in csv.DictReader(file)
        ]


def con_date(partiti: list[PartitoGoverno], governi: list[Governo]) -> list[PartitoGoverno]:
    """Riempie `inizio` con il giuramento e controlla che le date stiano dentro la vita del governo."""
    per_id = {g.id: g for g in governi}
    uscita = []
    for p in partiti:
        governo = per_id[p.governo_id]
        inizio = p.inizio or governo.inizio
        if inizio < governo.inizio or (governo.fine and inizio >= governo.fine):
            raise ValueError(f"{p.governo_id}, {p.partito}: inizio {inizio} fuori dal governo")
        if p.fine and (p.fine <= inizio or (governo.fine and p.fine > governo.fine)):
            raise ValueError(f"{p.governo_id}, {p.partito}: fine {p.fine} fuori dal governo o prima dell'inizio")
        uscita.append(replace(p, inizio=inizio))
    return uscita


def maggioranza_alla_data(partiti: list[PartitoGoverno], governo_id: str, giorno: date) -> list[PartitoGoverno]:
    """I partiti del governo che ne facevano parte (o lo sostenevano da fuori) quel giorno; servono le date piene."""
    return [
        p for p in partiti
        if p.governo_id == governo_id and p.inizio is not None and p.inizio <= giorno and (p.fine is None or giorno < p.fine)
    ]
