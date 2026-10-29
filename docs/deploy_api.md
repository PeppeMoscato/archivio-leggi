# Deploy dell'API

L'API FastAPI (`api/`) gira su **Render**, piano Free, e legge Neon con un ruolo di **sola lettura**.
La configurazione è nel repository (`render.yaml`, `api/deploy/ruolo_sola_lettura.sql`); account,
password e variabili d'ambiente li crea l'autore, una volta sola, con i passi qui sotto.

## Perché Render e non Fly.io
| | Render (Free) | Fly.io |
|---|---|---|
| Costo | 0 €, nessuna carta richiesta | nessun piano gratuito per i nuovi account: a consumo, la macchina più piccola costa circa 2 $/mese, carta obbligatoria |
| Inattività | si spegne dopo 15 minuti senza richieste, si riaccende alla prima (circa 1 minuto) | resta accesa (e si paga) o si ferma con l'autostop |
| Limiti | 750 ore di istanza al mese (basta per un servizio sempre acceso), 512 MB di RAM, 5 GB al mese di traffico in uscita per lo spazio di lavoro Hobby | secondo quanto si paga |
| Configurazione | `render.yaml` nel repo, deploy da GitHub senza installare nulla | `fly.toml` e la CLI `flyctl` |

Lo spegnimento dopo 15 minuti aiuta anche Neon: quando Render dorme non resta nessuna connessione
aperta e il compute di Neon si sospende dopo 5 minuti. Il prezzo è la prima richiesta dopo una pausa,
che aspetta il risveglio di Render (circa un minuto) e di Neon (meno di un secondo). Senza una carta
registrata, se si superano ore o traffico il servizio si sospende fino al mese dopo: nessun addebito a sorpresa.

Fonti (verificate il 29/10/2026): [Render, Deploy for Free](https://render.com/docs/free),
[Render, Blueprint spec](https://render.com/docs/blueprint-spec), [Fly.io, Pricing](https://fly.io/pricing),
[il cambio dei piani Render dell'1/8/2026](https://jwatte.com/blog/render-com-platform-review.md).

## Cosa c'è nel repository
- `render.yaml`: il servizio `archivio-leggi-api` (piano Free, Francoforte, cartella `api/`, Python 3.12).
  Si aggiorna da solo a ogni push su `main`, ma solo con la CI verde (`autoDeployTrigger: checksPass`).
  Il controllo di salute di Render chiama `/`, che non tocca il database: su `/salute` terrebbe Neon
  sveglio per tutto il tempo in cui il servizio è acceso.
- `api/deploy/ruolo_sola_lettura.sql`: crea il ruolo `api_lettura` con il solo `SELECT` sulle tabelle
  (anche su quelle che le pipeline creeranno dopo), transazioni in sola lettura per default, query
  interrotte dopo 15 secondi e al massimo 10 connessioni.
- Workflow "Prova API online" (Actions → Run workflow): interroga l'API pubblicata e misura i tempi.
  Serve perché dal container di Claude Code `onrender.com` non è raggiungibile.

## Passi manuali

### 1. Neon: ruolo di sola lettura
1. Apri il progetto su [console.neon.tech](https://console.neon.tech) → **SQL Editor**, database `neondb`
   (quello dell'archivio), con il ruolo proprietario (di solito `neondb_owner`).
2. Genera una password lunga, per esempio con
   `python -c "import secrets; print(secrets.token_urlsafe(24))"`, e salvala nel tuo gestore di password.
3. Copia nell'editor il contenuto di `api/deploy/ruolo_sola_lettura.sql`, sostituisci
   `SOSTITUISCI_CON_UNA_PASSWORD` con la password ed esegui. Se dimentichi di sostituirla, lo script si
   ferma con un errore.
4. Nello stesso editor crea l'indice della ricerca, che su Neon non c'è ancora (arriverebbe solo con il
   prossimo caricamento di una pipeline; è già in `ingest/archivio/schema.sql`):
   ```sql
   CREATE INDEX IF NOT EXISTS legge_titolo_fts ON legge USING gin (to_tsvector('italian', titolo));
   ```
5. Componi il `DATABASE_URL` dell'API partendo da quello delle pipeline (secret `DATABASE_URL` su GitHub,
   o **Connect** nella console di Neon): cambia utente e password, e usa l'indirizzo **diretto**, senza
   `-pooler` nel nome dell'host. L'API ha già il suo pool (al massimo 5 connessioni), quindi il pooler
   di Neon non serve.
   ```
   postgresql://api_lettura:LA_PASSWORD@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```

### 2. Render: il servizio
1. Crea un account su [render.com](https://render.com) entrando con GitHub.
2. **New → Blueprint**, collega il repository `PeppeMoscato/archivio-leggi` (Render chiede di installare
   la sua app GitHub: basta questo repository) e scegli il ramo `main`.
3. Render legge `render.yaml` e chiede due valori:
   - `DATABASE_URL`: quello del punto 1.5, con il ruolo `api_lettura`.
   - `CORS_ORIGINI`: l'indirizzo del frontend, es. `https://archivio-leggi.vercel.app`. Finché il
     frontend non esiste puoi lasciarlo vuoto: l'API risponde lo stesso, solo i browser di altri siti
     non possono chiamarla. Più origini si separano con virgole.
4. **Apply**. Il primo deploy dura qualche minuto; l'indirizzo sarà simile a
   `https://archivio-leggi-api.onrender.com` (la documentazione interattiva è su `/docs`).

I valori segreti si chiedono solo alla creazione: per cambiarli dopo (per esempio `CORS_ORIGINI`
quando c'è il frontend) vai sul servizio → **Environment**.

### 3. Prova
Actions → **Prova API online** → Run workflow, con l'indirizzo di Render (e, se c'è, l'origine del
frontend). Il workflow aspetta il risveglio, chiama ricerca, dettaglio, relazioni, iter e governi della
Legge Sirchia e controlla le intestazioni CORS.

## Consumi da tenere d'occhio
- **Neon** (100 CU-ore al mese): ogni gruppo di visite tiene acceso il compute almeno 5 minuti. Al
  compute minimo (0,25 CU) le 100 CU-ore sono circa 400 ore di attività al mese. Il consumo si vede in
  console → **Monitoring**. Se il traffico cresce oltre il piano Free, valutare il piano Launch (vedi
  `05_stato_e_decisioni.md`).
- **Render**: ore di istanza e traffico in uscita in **Billing**. Con un solo servizio Free le 750 ore
  bastano; il limite da guardare è il traffico, 5 GB al mese.
