# Archivio Leggi — istruzioni per Claude Code

App gratuita e non commerciale che archivia le leggi statali italiane (dal 1990) e valuta, a distanza di anni, se hanno raggiunto i loro obiettivi.

## Prima di lavorare
- Leggi `docs/05_stato_e_decisioni.md`: fase attuale, decisioni prese, roadmap. Non riproporre scelte già scartate; se una decisione va rivista, dillo e spiega perché.
- Rispetta schema (`docs/01_schema_dati.md`), metodo (`docs/02_metodo_valutazione.md`) e fonti (`docs/03_fonti.md`).
- Visione e perimetro: `docs/00_visione.md`. Leggi dell'MVP: `docs/06_leggi_mvp.md`. Scheda modello: `docs/04_scheda_esempio.md`.

## Regole di sviluppo
- Un task della roadmap per sessione. Se il task è troppo ampio, proponi come dividerlo.
- Stack fissato: Python (ingestione), PostgreSQL su Neon, FastAPI, Next.js. Niente alternative senza un problema concreto.
- Nessuna modifica allo schema dati senza aggiornare `docs/01_schema_dati.md` (nuova versione e storico).
- A fine sessione aggiorna `docs/05_stato_e_decisioni.md` (fase, decisioni, roadmap, log).
- Italiano per documenti, commenti e messaggi di commit.

## Struttura
- `docs/` — documenti di progetto (fonte di verità).
- `ingest/` — pipeline Python di ingestione (Normattiva, Camera, Senato, Istat).
- `api/` — FastAPI (da creare, Fase 1).
- `web/` — Next.js (da creare, Fase 1).

## Comandi
```bash
cd ingest
pip install -e ".[dev]"
pytest                  # prove offline
pytest -m rete          # prove contro i servizi reali (serve internet)
python spike_normattiva.py   # spike: scrive samples/ e stampa il report
```

## Fonti e licenze
- Normattiva: CC BY 4.0, attribuzione obbligatoria nel footer dell'app (testo in `docs/03_fonti.md`).
- Istat: max 5 query al minuto per IP, cache locale obbligatoria.
- Ogni dato salvato in `obiettivo`, `valutazione` e `verdetto` deve avere l'URL della fonte.
