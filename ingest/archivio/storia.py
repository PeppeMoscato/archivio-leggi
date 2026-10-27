"""Storia degli atti: l'export multivigente di Normattiva, letto senza caricare i testi.

L'export di un anno contiene, per ogni atto, un file JSON per versione
(`..._ORIGINALE_V1.json`, `..._VIGENZA_2005-01-10_V2.json`, ...). Dai nomi dei
file si ricavano le versioni; dai metadati dell'ultima versione il flag di
abrogazione e le note di aggiornamento; dal testo originale l'entrata in
vigore. Il resto del testo (che pesa quasi tutto l'archivio) non si conserva:
nel database vanno solo i metadati (decisione del 27/10/2026).

Il lettore è scritto qui invece di usare `Corpus` dell'SDK perché `Corpus`
costruisce in memoria l'albero di ogni versione di ogni atto, e un anno di
leggi in multivigenza è troppo grande per farlo con comodo.
"""

from __future__ import annotations

import json
import logging
import re
import zipfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from normattiva import Urn
from normattiva._wire import leggi_data  # privato ma stabile: l'SDK è fissato a 0.1.0

from archivio.modelli import Nota, Riferimento

logger = logging.getLogger(__name__)

_VERSIONE = re.compile(r"_(?:VIGENZA_(\d{4}-\d{2}-\d{2})|ORIGINALE)_V(\d+)\.json$", re.I)
# Nel titolo dell'export: "Entrata in vigore del provvedimento: 22/1/2004", "... del decreto: 8/1/1995."
_ENTRATA_IN_VIGORE = re.compile(r"entrata\s+in\s+vigore\s+de\w*\s+\w+\s*:\s*(\d{1,2})/(\d{1,2})/(\d{4})", re.I)
_DECADUTO = re.compile(r"decadut\w*\s+per\s+mancata\s+conversione", re.I)


@dataclass
class Storia:
    urn: str
    tipo_doc: str | None
    numero: str | None
    data: date | None
    abrogato: bool
    decaduto: bool
    versioni: int
    data_ultima_versione: date | None
    data_entrata_vigore: date | None
    fine_vigore_originale: date | None = None
    note: list[Nota] = field(default_factory=list)

    @property
    def data_abrogazione(self) -> date | None:
        """Da quando l'atto non è più in vigore.

        Abrogato: inizio dell'ultima versione, che coincide con l'entrata in
        vigore dell'atto abrogante (spike, punto 11). Decaduto: il giorno dopo
        la fine di vigenza del testo originale (60 giorni dalla pubblicazione);
        l'ultima versione qui non serve, perché a volte segue di anni.
        """
        if self.decaduto and self.fine_vigore_originale:
            return self.fine_vigore_originale + timedelta(days=1)
        if self.abrogato or self.decaduto:
            return self.data_ultima_versione
        return None


def chiave_urn(urn: str) -> str:
    """URN nella forma canonica dell'SDK, per confrontare catalogo ed export."""
    try:
        return str(Urn.parse(urn))
    except ValueError:
        return urn.strip().lower()


def _abrogato(valore: Any) -> bool:
    return str(valore or "").strip().lower() in ("si", "sì", "true", "1")


def note_da_metadati(metadati: Mapping[str, Any]) -> list[Nota]:
    note = []
    for grezza in metadati.get("aggiornamentiAtto") or ():
        testo = " ".join(str(grezza.get("testo") or "").split())
        if not testo:
            continue
        riferimenti = []
        for modifica in grezza.get("urnModifiche") or ():
            articolo = modifica.get("articoloAggiornante") or {}
            giorno = leggi_data(articolo.get("dataPubblicazioneGazzetta"))
            if giorno is None:
                continue
            codice = str(articolo.get("codiceRedazionale") or "").strip() or None
            riferimenti.append(Riferimento(codice, giorno, str(articolo.get("idNir") or "").strip() or None))
        note.append(Nota(testo, tuple(riferimenti)))
    return note


def finestre_di_vigenza(documento: Mapping[str, Any]) -> Iterator[tuple[date, date | None]]:
    """Le finestre (inizio, fine) dichiarate dai nodi dell'articolato; fine None = aperta."""

    def scendi(nodo: Mapping[str, Any]) -> Iterator[tuple[date, date | None]]:
        for periodo in nodo.get("dataVigoreVersione") or ():
            if inizio := leggi_data(periodo.get("inizioVigore")):
                yield inizio, leggi_data(periodo.get("fineVigore"))
        for figlio in nodo.get("elementi") or ():
            yield from scendi(figlio)

    for radice in ("articolato", "annessi"):
        yield from scendi(documento.get(radice) or {})


def entrata_in_vigore_dichiarata(titolo: str) -> date | None:
    trovata = _ENTRATA_IN_VIGORE.search(titolo)
    if trovata is None:
        return None
    giorno, mese, anno = (int(parte) for parte in trovata.groups())
    try:
        return date(anno, mese, giorno)
    except ValueError:
        return None


def _documento(archivio: zipfile.ZipFile, nome: str) -> dict[str, Any] | None:
    """Il JSON di una versione, o None se il file è vuoto o illeggibile.

    Succede davvero: nella prima esecuzione completa (27/10/2026) alcuni
    archivi annuali contenevano file vuoti.
    """
    try:
        documento = json.loads(archivio.read(nome))
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("file illeggibile nell'export: %s", nome)
        return None
    return documento if isinstance(documento, dict) else None


def leggi_storie(percorso: Path) -> Iterator[Storia]:
    """Una `Storia` per ogni atto contenuto nell'archivio di export."""
    with zipfile.ZipFile(percorso) as archivio:
        per_atto: dict[str, list[tuple[int, date | None, str]]] = {}
        for nome in archivio.namelist():
            trovato = _VERSIONE.search(nome)
            if trovato is None:
                continue
            vigenza = date.fromisoformat(trovato.group(1)) if trovato.group(1) else None
            per_atto.setdefault(nome.rsplit("/", 1)[0], []).append((int(trovato.group(2)), vigenza, nome))
        for cartella, file in per_atto.items():
            file.sort()
            # L'ultima versione leggibile: è quella con le note e il flag di abrogazione aggiornati.
            ultimo, nome_ultimo = next(
                ((documento, nome) for _, _, nome in reversed(file) if (documento := _documento(archivio, nome))),
                (None, None),
            )
            if ultimo is None:
                logger.warning("nessuna versione leggibile per %s", cartella)
                continue
            if nome_ultimo != file[-1][2]:
                logger.warning("%s: uso la versione %s, le successive sono illeggibili", cartella, nome_ultimo)
            metadati = ultimo.get("metadati") or {}
            urn = str(metadati.get("urn") or "").strip()
            if not urn:
                logger.warning("atto senza URN nell'export: %s", cartella)
                continue
            originale = next((nome for _, vigenza, nome in file if vigenza is None), None)
            documento_originale = ultimo if originale == nome_ultimo else _documento(archivio, originale) if originale else None
            finestre = list(finestre_di_vigenza(documento_originale)) if documento_originale else []
            fini = [fine for _, fine in finestre]
            datate = [vigenza for _, vigenza, _ in file if vigenza is not None]
            titolo = str(metadati.get("titoloDoc") or "")
            yield Storia(
                urn=chiave_urn(urn),
                tipo_doc=str(metadati.get("tipoDoc") or "").strip() or None,
                numero=str(metadati.get("numDoc") or "").strip() or None,
                data=leggi_data(metadati.get("dataDoc")),
                abrogato=_abrogato(metadati.get("abrogato")),
                decaduto=bool(_DECADUTO.search(titolo)),
                versioni=len(file),
                data_ultima_versione=max(datate) if datate else None,
                # Prima la data scritta da Normattiva nel titolo, poi la vigenza più vecchia degli articoli.
                data_entrata_vigore=entrata_in_vigore_dichiarata(titolo) or min((i for i, _ in finestre), default=None),
                fine_vigore_originale=max(fini) if fini and None not in fini else None,
                note=note_da_metadati(metadati),
            )
