"""I dati intermedi della pipeline: quello che si estrae da Normattiva prima del database.

Sono serializzabili in JSON perché l'estrazione (un job per anno su GitHub
Actions) e il caricamento (un job unico) girano in processi diversi e si
passano i file JSONL come artifact.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

# Denominazione Normattiva → valore di `legge.tipo`.
TIPI = {
    "LEGGE": "legge",
    "LEGGE COSTITUZIONALE": "legge costituzionale",
    "DECRETO-LEGGE": "decreto-legge",
    "DECRETO LEGISLATIVO": "decreto legislativo",
}


@dataclass(frozen=True)
class Riferimento:
    """Dove è stato pubblicato l'atto che ha disposto una modifica."""

    codice: str | None
    data: date
    articolo: str | None = None


@dataclass(frozen=True)
class Nota:
    """Una nota di aggiornamento di Normattiva, con i riferimenti in Gazzetta che porta."""

    testo: str
    riferimenti: tuple[Riferimento, ...] = ()


@dataclass
class Atto:
    """Un atto del perimetro, unendo catalogo (ricerca) e storia (export)."""

    urn: str
    tipo: str
    numero: str
    data: date
    titolo: str
    gazzetta_data: date | None = None
    gazzetta_numero: int | None = None
    gazzetta_codice: str | None = None
    # Dalla storia (export multivigente); None se l'export non conteneva l'atto.
    abrogato: bool | None = None
    decaduto: bool | None = None
    versioni: int | None = None
    data_abrogazione: date | None = None
    data_entrata_vigore: date | None = None
    # Ultimo giorno di vigenza del testo originale (per i D.L. decaduti: 60 giorni dalla pubblicazione).
    fine_vigore_originale: date | None = None
    note: list[Nota] = field(default_factory=list)

    def in_json(self) -> dict[str, Any]:
        return _in_json(asdict(self))

    @classmethod
    def da_json(cls, dati: dict[str, Any]) -> Atto:
        giorno = _giorno
        return cls(
            urn=dati["urn"],
            tipo=dati["tipo"],
            numero=dati["numero"],
            data=giorno(dati["data"]),
            titolo=dati["titolo"],
            gazzetta_data=giorno(dati.get("gazzetta_data")),
            gazzetta_numero=dati.get("gazzetta_numero"),
            gazzetta_codice=dati.get("gazzetta_codice"),
            abrogato=dati.get("abrogato"),
            decaduto=dati.get("decaduto"),
            versioni=dati.get("versioni"),
            data_abrogazione=giorno(dati.get("data_abrogazione")),
            data_entrata_vigore=giorno(dati.get("data_entrata_vigore")),
            fine_vigore_originale=giorno(dati.get("fine_vigore_originale")),
            note=[
                Nota(
                    testo=nota["testo"],
                    riferimenti=tuple(
                        Riferimento(r.get("codice"), giorno(r["data"]), r.get("articolo")) for r in nota.get("riferimenti", ())
                    ),
                )
                for nota in dati.get("note", ())
            ],
        )


def _giorno(valore: str | None) -> date | None:
    return date.fromisoformat(valore) if valore else None


def _in_json(valore: Any) -> Any:
    if isinstance(valore, dict):
        return {chiave: _in_json(v) for chiave, v in valore.items()}
    if isinstance(valore, (list, tuple)):
        return [_in_json(v) for v in valore]
    if isinstance(valore, date):
        return valore.isoformat()
    return valore
