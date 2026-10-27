"""Costruisce archivi di export finti, con la stessa forma di quelli di Normattiva."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path


def metadati(urn: str, tipo: str, numero: str, data: str, abrogato: str = "no", aggiornamenti: list | None = None) -> dict:
    return {
        "urn": urn,
        "tipoDoc": tipo,
        "numDoc": numero,
        "dataDoc": data,
        "abrogato": abrogato,
        "aggiornamentiAtto": aggiornamenti or [],
    }


def articolo(numero: str, inizio: str) -> dict:
    return {"nomeNir": "articolo", "numNir": numero, "dataVigoreVersione": [{"inizioVigore": inizio, "fineVigore": "99999999"}]}


def aggiornamento(testo: str, codice: str | None, data_gu: str, articolo: str | None = None) -> dict:
    return {
        "data": "20191005",
        "testo": testo,
        "urnModifiche": [{"articoloAggiornante": {"codiceRedazionale": codice, "dataPubblicazioneGazzetta": data_gu, "idNir": articolo}}],
    }


def scrivi_export(percorso: Path, atti: list[dict]) -> Path:
    """`atti`: dizionari con `cartella`, `metadati`, `versioni` (lista di date ISO, None = originale), `articoli`."""
    with zipfile.ZipFile(percorso, "w") as archivio:
        for atto in atti:
            for indice, vigenza in enumerate(atto["versioni"], start=1):
                nome = f"{atto['cartella']}/{atto['cartella']}_{'ORIGINALE' if vigenza is None else 'VIGENZA_' + vigenza}_V{indice}.json"
                documento = {"metadati": atto["metadati"], "articolato": {"elementi": atto.get("articoli", [])}}
                archivio.writestr(nome, json.dumps(documento))
        archivio.writestr("LEGGIMI.txt", "non è un atto")
    return percorso
