"""Sonda per il Task 1.1: quanto costa esportare un anno di atti, e cosa contiene l'export.

Misura, per un anno di leggi e uno di decreti-legge, le tre modalità di export
(originale, vigente, multivigente): tempo, dimensione, file per atto, metadati
presenti. Stampa anche un campione delle note di aggiornamento per scrivere il
classificatore delle relazioni. Gira solo su GitHub Actions (Normattiva è
bloccata dal container di Claude Code). Da togliere a pipeline conclusa.
"""

from __future__ import annotations

import io
import json
import os
import random
import re
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

from normattiva import ClasseProvvedimento, Format, Normattiva, NormattivaError, Sort
from normattiva.modelli import ExportMode

CARTELLA = Path(__file__).parent / "samples" / "sonda"
CASI = (("LEGGE", 2003), ("DECRETO-LEGGE", 1995))
USCITA: list[str] = []


def scrivi(riga: str = "") -> None:
    print(riga, flush=True)
    USCITA.append(riga)


def elenco(client: Normattiva) -> None:
    scrivi("## Elenco con ricerca_avanzata")
    for per_pagina in (100, 200, 500):
        try:
            esito = client.ricerca_avanzata(denominazione="LEGGE", anno=2003, per_pagina=per_pagina, sort=Sort.OLDEST)
            scrivi(f"- per_pagina={per_pagina}: totale {esito.totale}, ricevuti {len(esito.atti)}, pagine {esito.pagine}")
        except NormattivaError as errore:
            scrivi(f"- per_pagina={per_pagina}: errore {type(errore).__name__}: {errore}")
    esito = client.ricerca_avanzata(denominazione="DECRETO-LEGGE", anno=2019, per_pagina=200, sort=Sort.OLDEST)
    urn = Counter(str(a.urn) for a in esito.atti)
    scrivi(f"- D.L. 2019: totale {esito.totale}, ricevuti {len(esito.atti)}, URN doppi {[u for u, n in urn.items() if n > 1]}")
    for atto in esito.atti[:3]:
        scrivi(f"  - {atto.estremi} | {atto.gazzetta} | cod {atto.gazzetta.codice_redazionale} | ultima_modifica {atto.ultima_modifica} | modificanti {atto.atti_modificanti[:3]} | {atto.titolo[:80]}")
    for classe in ClasseProvvedimento:
        esito = client.ricerca_avanzata(denominazione="DECRETO-LEGGE", anno=1995, classe=classe, per_pagina=1)
        scrivi(f"- D.L. 1995 classe {classe.name}: {esito.totale}")
    scrivi()


def riassunto_metadati(metadati: dict) -> dict:
    return {k: (v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} {len(v)}>") for k, v in metadati.items()}


def finestre_articoli(documento: dict, quanti: int = 3) -> list:
    risultato = []

    def scendi(nodo: dict) -> None:
        if len(risultato) >= quanti:
            return
        if nodo.get("nomeNir") == "articolo":
            risultato.append((nodo.get("numNir"), nodo.get("dataVigoreVersione")))
        for figlio in nodo.get("elementi") or ():
            scendi(figlio)

    for nodo in (documento.get("articolato") or {}).get("elementi") or ():
        scendi(nodo)
    return risultato


def analizza_zip(dati: bytes, note: list[str], dettagli: bool) -> None:
    archivio = zipfile.ZipFile(io.BytesIO(dati))
    nomi = [n for n in archivio.namelist() if n.lower().endswith(".json")]
    per_atto: dict[str, list[str]] = {}
    for nome in nomi:
        per_atto.setdefault(nome.rsplit("/", 1)[0], []).append(nome)
    scrivi(f"  - atti {len(per_atto)}, file json {len(nomi)}, altri file {len(archivio.namelist()) - len(nomi)}")
    con_agg = abrogati = 0
    for indice, (cartella, file) in enumerate(sorted(per_atto.items())):
        file.sort()
        ultimo = json.loads(archivio.read(file[-1]))
        metadati = ultimo.get("metadati") or {}
        aggiornamenti = metadati.get("aggiornamentiAtto") or []
        con_agg += bool(aggiornamenti)
        abrogati += str(metadati.get("abrogato") or "").lower() in ("si", "sì", "true")
        for aggiornamento in aggiornamenti:
            note.append(" ".join(str(aggiornamento.get("testo") or "").split()))
        if dettagli and indice < 2:
            scrivi(f"  - cartella {cartella}: file {[f.rsplit('/', 1)[1] for f in file][:6]}")
            scrivi(f"    - chiavi documento: {sorted(ultimo.keys())}")
            scrivi(f"    - metadati: {json.dumps(riassunto_metadati(metadati), ensure_ascii=False)[:1500]}")
            if aggiornamenti:
                scrivi(f"    - primo aggiornamento grezzo: {json.dumps(aggiornamenti[0], ensure_ascii=False)[:1200]}")
            primo = json.loads(archivio.read(file[0]))
            scrivi(f"    - finestre articoli ({file[0].rsplit('/', 1)[1]}): {finestre_articoli(primo)}")
    scrivi(f"  - atti con aggiornamenti {con_agg}, abrogati {abrogati}")
    if dettagli:
        abrogato = next(
            (
                (c, f)
                for c, f in sorted(per_atto.items())
                if str((json.loads(archivio.read(sorted(f)[-1])).get("metadati") or {}).get("abrogato") or "").lower() in ("si", "sì")
            ),
            None,
        )
        if abrogato:
            cartella, file = abrogato
            file.sort()
            scrivi(f"  - esempio abrogato {cartella}: file {[f.rsplit('/', 1)[1] for f in file]}")
            ultimo = json.loads(archivio.read(file[-1]))
            scrivi(f"    - metadati: {json.dumps(riassunto_metadati(ultimo.get('metadati') or {}), ensure_ascii=False)[:1500]}")
            for agg in (ultimo.get("metadati") or {}).get("aggiornamentiAtto") or []:
                scrivi(f"    - nota: {' '.join(str(agg.get('testo')).split())[:400]}")
            scrivi(f"    - finestre articoli ultimo file: {finestre_articoli(ultimo)}")


def esporta(client: Normattiva, denominazione: str, anno: int, modo: ExportMode, note: list[str]) -> None:
    inizio = time.monotonic()
    try:
        export = client.start_export(format=Format.JSON, mode=modo, massimo_atti=None, denominazione=denominazione, anno=anno)
        export.wait(timeout=2400)
        attesa = time.monotonic() - inizio
        dati = export._scarica()
    except NormattivaError as errore:
        scrivi(f"- {denominazione} {anno} {modo.value}: errore dopo {time.monotonic() - inizio:.0f}s: {type(errore).__name__}: {errore}")
        return
    totale = time.monotonic() - inizio
    scrivi(f"- {denominazione} {anno} {modo.value}: attesa {attesa:.0f}s, totale {totale:.0f}s, zip {len(dati) / 1e6:.1f} MB")
    CARTELLA.mkdir(parents=True, exist_ok=True)
    (CARTELLA / f"{denominazione}_{anno}_{modo.value}.zip").write_bytes(dati)
    analizza_zip(dati, note, dettagli=True)


def campione_note(note: list[str]) -> None:
    scrivi("## Note di aggiornamento")
    scrivi(f"Totale note: {len(note)}")
    verbi = Counter()
    for nota in note:
        trovato = re.search(r"ha (disposto|dichiarato)[^)]*\)?\s*(?:l[a'’]\s*|il\s+|lo\s+|i\s+|gli\s+|le\s+)?(\w+)", nota)
        verbi[(trovato.group(1), trovato.group(2).lower()) if trovato else ("?", nota[:60])] += 1
    for (verbo, parola), quante in verbi.most_common(60):
        scrivi(f"- {quante}: {verbo} … {parola}")
    scrivi("### Campione")
    random.seed(1)
    for nota in random.sample(note, min(60, len(note))):
        scrivi(f"- {nota[:500]}")


def main() -> int:
    user_agent = "archivio-leggi sonda (+https://github.com/PeppeMoscato/archivio-leggi)"
    note: list[str] = []
    with Normattiva(user_agent=user_agent, timeout=300.0) as client:
        elenco(client)
        scrivi("## Export")
        for denominazione, anno in CASI:
            for modo in (ExportMode.ORIGINALE, ExportMode.VIGENTE, ExportMode.MULTIVIGENTE):
                esporta(client, denominazione, anno, modo, note if modo is ExportMode.MULTIVIGENTE else [])
        scrivi()
    campione_note(note)
    if riepilogo := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(riepilogo, "a", encoding="utf-8") as file:
            file.write("\n".join(USCITA) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
