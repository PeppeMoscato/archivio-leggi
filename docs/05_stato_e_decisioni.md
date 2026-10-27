# Stato del progetto e decisioni

Ultimo aggiornamento: 27/10/2026
Aggiornare a fine di ogni sessione di lavoro.

## Fase attuale
Fase 0 — Setup. Repository creato (https://github.com/PeppeMoscato/archivio-leggi). Task 0.2 completato: l'API di Normattiva funziona (da GitHub Actions) e restituisce stato, versioni e modifiche. Prossimo passo: approvare lo schema v1.1 proposto in `docs/spike_normattiva.md`, poi Task 1.1.

## Decisioni prese
| Data | Decisione | Motivo |
|---|---|---|
| 2026-10-27 | Perimetro: leggi statali italiane dal 1990 | Partire piccoli; regioni e UE dopo |
| 2026-10-27 | Progetto gratuito e non commerciale | Libertà sulle fonti (Openpolis CC BY-NC utilizzabile) |
| 2026-10-27 | Hosting quasi gratuito, budget < 10 €/mese | Vercel (frontend), Neon (Postgres), Render o Fly.io (FastAPI) su piani free |
| 2026-10-27 | Stack: Python per ingestione, PostgreSQL, FastAPI, Next.js | Client esistenti per Normattiva e Istat; competenze dell'autore |
| 2026-10-27 | Progetto Claude per design e schede; Claude Code su repo GitHub per il codice | Il codice va eseguito e testato |
| 2026-10-27 | MVP = archivio completo + 30 schede valutate | Il valore sono le schede, non la quantità |
| 2026-10-27 | Nessun verdetto pubblicato senza approvazione umana | Rischio di errori e allucinazioni |
| 2026-10-27 | Database: Neon (piano Free) invece di Supabase | Postgres puro (servono solo i dati, FastAPI è a parte). Free: 1 GB per progetto (da ottobre 2026), 100 CU-ore al mese, il compute si sospende dopo 5 minuti e si riattiva alla prima richiesta. Supabase Free mette in pausa il progetto dopo 7 giorni di inattività (500 MB): scomodo per un sito con poco traffico all'inizio |
| 2026-10-27 | Nel database solo metadati, relazioni, serie e schede; testi integrali solo per le 30 leggi dell'MVP | Il limite di 1 GB non basta per tutti i testi in multivigenza; gli altri testi si leggono al bisogno da Normattiva tramite link e API |
| 2026-10-27 | Lista delle 30 leggi in `06_leggi_mvp.md` | Copertura dei governi dal 1994, mix di leggi vigenti e abrogate |
| 2026-10-27 | Scheda di esempio: Legge Sirchia (L. 3/2003, art. 51) | Obiettivo chiaro, buoni studi, poco divisiva: ideale per fissare il metodo |
| 2026-10-27 | Perimetro iniziale degli atti: legge, legge costituzionale, decreto-legge, decreto legislativo (dal 1990) | Sono gli atti delle 30 leggi MVP e hanno un URN verificato su Normattiva. L'obiettivo di lungo periodo è archiviare tutte le decisioni dei governi (anche DPR, DPCM, decreti ministeriali) |
| 2026-10-27 | I documenti di progetto vivono in `docs/` del repository; la cartella del Progetto Claude ne è una copia | Una sola fonte di verità, versionata con il codice |
| 2026-10-27 | Client Normattiva: `normattiva-sdk` (PyPI, MIT, non ufficiale, versione 0.1.0 alpha) | Copre tutta l'API open data; confermato dallo spike su 5 leggi MVP |
| 2026-10-27 | Le chiamate a Normattiva, Camera, Senato e Istat girano su GitHub Actions | Dal container cloud di Claude Code quei domini sono bloccati |

## Ancora da decidere
- Schema v1.1, dopo lo spike: `data_entrata_vigore`, `governo`, relazioni `converte` e `delega`, valori di `stato`. Dettagli in `docs/revisioni/2026-10-27_revisione_documentazione.md`.
- Prima della Fase 2: schede su un singolo articolo, un verdetto per obiettivo, dove vive la scheda (file nel repo o database) e come si approva.
- Effetti a breve, medio e lungo periodo: il metodo oggi chiede "almeno 3 anni". Valutare un verdetto per orizzonte temporale (es. 1-2 anni, 3-5 anni, 10+ anni).
- Gerarchia delle fonti: la stampa non può essere l'unica fonte di un numero.
- Dove gira la pipeline di aggiornamento (proposta: GitHub Actions con cron settimanale).
- Licenza del codice del repository.
- Da rivedere al primo deploy: se il traffico supera il piano Free di Neon, passare al piano Launch (a consumo).

## Roadmap
### Fase 0 — Setup
- [ ] Creare Progetto Claude e caricare la knowledge
- [x] Creare repo GitHub `archivio-leggi`
- [x] Task 0.2: `CLAUDE.md`, `docs/`, spike Normattiva (risultati in `docs/spike_normattiva.md`)
- [ ] Schema v1.1 sui risultati dello spike
- [x] Compilare `04_scheda_esempio.md` su una legge vera (Legge Sirchia; resta la revisione a mano)
- [x] Scegliere le 30 leggi dell'MVP (`06_leggi_mvp.md`)
- [ ] Rileggere e approvare la scheda di esempio

### Fase 1 — Archivio
- [ ] Pipeline Normattiva → Postgres (leggi dal 1990, stato, modifiche, abrogazioni)
- [ ] Ingestione iter da Camera e Senato (SPARQL)
- [ ] API FastAPI: ricerca e dettaglio legge
- [ ] Frontend: ricerca e pagina legge con timeline delle modifiche

### Fase 2 — Schede "ha funzionato?"
- [ ] Ingestione serie Istat con cache
- [ ] Schede: obiettivi, indicatori, valutazioni, verdetto con approvazione
- [ ] Grafici prima/dopo

### Fase 3 — Scala
- [ ] Bozze di schede in batch con Claude API + coda di approvazione
- [ ] Segnalazioni degli utenti
- [ ] Leggi regionali e UE

### Idee per dopo (non pianificate)
- [ ] Carosello TikTok "pagella politica": una slide per legge con verdetto, confidenza e 2-3 numeri chiave, generata dalle schede approvate. Da collegare al progetto separato di automazione TikTok. Usare solo schede con verdetto approvato e sempre con il link alle fonti.

## Log sessioni
- 2026-10-27: definiti visione, schema v1, metodo, fonti, stack e decisioni.
- 2026-10-27: scelto Neon, definita la lista delle 30 leggi, compilata la scheda di esempio sulla Legge Sirchia.
- 2026-10-27: annotata l'idea del carosello TikTok "pagella politica" per dopo l'MVP.
- 2026-10-27: revisione della documentazione (vedi `docs/revisioni/`); creato il repository; deciso il perimetro iniziale degli atti; Task 0.2 completato (circa 8.900 atti nel perimetro dal 1990; proposte per lo schema v1.1).
