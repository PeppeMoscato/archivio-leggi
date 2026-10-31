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
- `ingest/` — pipeline Python di ingestione (Normattiva, Camera, Senato, Istat). Pacchetto `ingest/archivio/`: pipeline Normattiva → Postgres.
- `api/` — FastAPI in sola lettura (pacchetto `api/archivio_api/`): ricerca e dettaglio delle leggi.
- `web/` — Next.js (ricerca e pagina legge), legge solo l'API dal server; deploy su Vercel (`docs/deploy_frontend.md`).

## Comandi
```bash
cd ingest
pip install -e ".[dev]"
pytest                  # prove offline (con TEST_DATABASE_URL anche quelle sul database)
pytest -m rete          # prove contro i servizi reali (serve internet)
python spike_normattiva.py   # spike: scrive samples/ e stampa il report

# Pipeline Normattiva → Postgres (Task 1.1)
python -m archivio estrai --anni 2003 --uscita dati        # catalogo + export, un JSONL per anno
DATABASE_URL=... python -m archivio carica --da dati       # relazioni, stato, governo → database

# Pipeline Senato → Postgres (Task 1.2)
python -m archivio senato-estrai --legislature 15 --uscita dati   # iter, fasi, firmatari, votazioni, un JSON per legislatura
python -m archivio senato-persone --uscita dati                   # senatori, gruppi, adesioni
python -m archivio senato-estrai --legislature 17 --senza-voti --uscita dati  # solo iter e fasi: le votazioni già nel database restano
DATABASE_URL=... python -m archivio senato-carica --da dati

# Pipeline premesse → Postgres (contesto delle leggi, schema v1.4; dopo Normattiva)
python -m archivio premesse-estrai --anni 2006 --uscita dati      # premesse di D.L. e D.Lgs. dal testo originale, un JSONL per anno
DATABASE_URL=... python -m archivio premesse-carica --da dati     # tabella premessa e relazioni delega

# Pipeline Camera → Postgres (Task 1.2, dopo il Senato)
python -m archivio camera-estrai --legislature 15 --uscita dati   # votazioni (XIII-XIX) o iter dai lavori preparatori (X-XII)
python -m archivio camera-persone --uscita dati                   # deputati, gruppi, adesioni, governi
python -m archivio camera-stima --legislature 13-19               # votazioni e voti da caricare, senza scaricare i voti
DATABASE_URL=... python -m archivio camera-carica --da dati

# Partiti dei governi (CSV compilati a mano; li carica anche senato-carica)
DATABASE_URL=... python -m archivio partiti-carica

# API FastAPI, sola lettura
cd ../api
pip install -e ".[dev]"
pytest                                                  # con TEST_DATABASE_URL anche le prove sul database
DATABASE_URL=... uvicorn archivio_api.app:app --reload  # documentazione interattiva su /docs

# Frontend Next.js
cd ../web
npm ci
npm test && npm run typecheck
API_URL=http://localhost:8000 npm run dev               # senza API_URL usa l'API su Render
```
- Normattiva non è raggiungibile dal container di Claude Code: la pipeline gira sul workflow "Pipeline Normattiva" (Actions → Run workflow, campo `anni`). Con il secret `DATABASE_URL` scrive su Neon, altrimenti pubblica il dump `archivio-db` come artifact.
- Anche le premesse girano su GitHub Actions: workflow "Pipeline premesse" (campo `anni`), scrive su Neon solo con `scrivi_su_neon` spuntato e dopo il caricamento Normattiva. Le relazioni `delega` le scrive solo questa pipeline.
- www.senato.it (schede dei ddl, PDF) risponde con un controllo anti-robot: solo link, non va aggirato.
- I partiti dei governi (`ingest/archivio/governi_partiti.csv`) si compilano a mano, una fonte per riga; regola in `docs/05_stato_e_decisioni.md`. Su Neon: workflow "Partiti dei governi" con `scrivi_su_neon`.
- dati.senato.it e dati.camera.it non sono raggiungibili dal container: il Senato gira sul workflow "Pipeline Senato", la Camera su "Pipeline Camera" (campo `legislature`); scrivono su Neon solo con `scrivi_su_neon` spuntato. Su Neon la Camera va caricata dopo il Senato.
- La Camera XIII-XVI legge i voti dalle schede HTML (circa 2 pagine al secondo, circa 2 ore per la XIII): una legislatura alla volta. Schede e voti vanno nella cache `dati/cache/`, salvata dal workflow anche se il job fallisce: dopo un guasto di dati.camera.it basta rilanciare i job falliti.
- La DDL è `ingest/archivio/schema.sql`: va tenuta allineata a `docs/01_schema_dati.md`. L'API la usa anche nelle sue prove.
- L'API non scrive mai: ogni transazione è `READ ONLY`, e su Neon usa il ruolo `api_lettura` (`api/deploy/ruolo_sola_lettura.sql`).
- Il frontend gira su Vercel, piano Hobby (`web/vercel.json`, guida in `docs/deploy_frontend.md`). Chiama l'API solo dal server con cache di un'ora: non serve CORS.
- L'API gira su Render, piano Free (`render.yaml`, guida in `docs/deploy_api.md`): onrender.com non è raggiungibile dal container, si prova con il workflow "Prova API online" (campo `url`).

## Fonti e licenze
- Normattiva: CC BY 4.0, attribuzione obbligatoria nel footer dell'app (testo in `docs/03_fonti.md`).
- Istat: max 5 query al minuto per IP, cache locale obbligatoria.
- Ogni dato salvato in `obiettivo`, `valutazione` e `verdetto` deve avere l'URL della fonte.
