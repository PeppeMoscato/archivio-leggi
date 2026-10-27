# Schema dati — v1.1

Database: PostgreSQL (Neon). Chiave unica di ogni legge: URN NIR di Normattiva (es. `urn:nir:stato:legge:1990-08-07;241`).

Il cuore dello schema è il legame **obiettivo → indicatore → misura**.

La DDL eseguibile è in [`ingest/archivio/schema.sql`](../ingest/archivio/schema.sql) e va tenuta allineata a questa pagina.

## Archivio (Fase 1)

| Tabella | Campi | Note |
|---|---|---|
| `governo` | `id` (PK), `nome`, `presidente`, `inizio`, `fine`, `fonte_url` | `inizio` = giuramento; `fine` = giuramento del governo successivo (vuota per il governo in carica). Così ogni giorno ha uno e un solo governo, compresi i periodi di "affari correnti" dopo le dimissioni |
| `legge` | `urn` (PK), `tipo`, `numero`, `data`, `titolo`, `materia`, `link_normattiva`, `stato`, `data_abrogazione`, `data_entrata_vigore`, `gazzetta_data`, `gazzetta_numero`, `gazzetta_codice`, `governo_id` (FK governo), `aggiornato_il` | `tipo`: legge / legge costituzionale / decreto-legge / decreto legislativo. `data` = emanazione. `stato`: vigente / abrogata / decaduta (D.L. non convertito). `gazzetta_*` = pubblicazione originale (la più vecchia, se l'URN ne ha più di una). `governo_id` assegnato per data di emanazione |
| `relazione_normativa` | `id` (PK), `urn_origine`, `urn_destinazione` (FK legge), `tipo`, `data`, `articolo_origine`, `articolo_destinazione`, `nota`, `origine_gazzetta_codice`, `origine_gazzetta_data` | Verso: `urn_origine` è l'atto che dispone, `urn_destinazione` l'atto che subisce. `tipo`: modifica / abroga / abroga_parziale / converte / attua / proroga / delega. `data` = pubblicazione in Gazzetta dell'atto di origine. `urn_origine` non è FK e può essere vuoto (vedi sotto) |
| `pronuncia_costituzionale` | `id` (PK), `urn_legge` (FK legge), `articolo`, `numero_sentenza`, `anno`, `data_gazzetta`, `gazzetta_codice`, `nota` | Sentenze di illegittimità della Corte costituzionale: non sono leggi, quindi non stanno in `relazione_normativa`. Le note di Normattiva non riportano il numero della sentenza: per ora resta il riferimento in Gazzetta (`data_gazzetta`, `gazzetta_codice`) |
| `iter` | `id` (PK), `urn` (FK), `camera`, `numero_ddl`, `data_presentazione`, `data_approvazione`, `voti_favorevoli`, `voti_contrari` | da dati.camera.it e dati.senato.it. Voti opzionali: i D.Lgs. non hanno voto finale e per le legislature più vecchie i dati possono mancare |

Vista `legge_estesa`: tutti i campi di `legge` più `numero_modifiche` (relazioni in entrata di tipo modifica, abroga_parziale, proroga) e `modificata` (`numero_modifiche > 0`). "Modificata" non è uno stato: si ricava.

### Tabelle tecniche
| Tabella | Campi | Note |
|---|---|---|
| `gazzetta_urn` | `codice_redazionale`, `data_gazzetta` (PK composta), `urn`, `tipo`, `risolto_il` | Cache della risoluzione "riferimento in Gazzetta → URN" fatta con `dettaglio_da_gazzetta`. `urn` vuoto = Normattiva non ha restituito l'atto (es. sentenze, comunicati); non si richiede di nuovo |

## Schede (Fase 2)

| Tabella | Campi | Note |
|---|---|---|
| `obiettivo` | `id` (PK), `urn` (FK), `descrizione`, `fonte_url`, `tipo_fonte` | `tipo_fonte`: relazione illustrativa / AIR / dossier |
| `indicatore` | `id` (PK), `obiettivo_id` (FK), `nome`, `unita`, `fonte_dati`, `codice_serie` | `codice_serie`: es. dataflow Istat |
| `misura` | `indicatore_id` (FK), `periodo`, `valore` | PK composta (`indicatore_id`, `periodo`) |
| `valutazione` | `id` (PK), `urn` (FK), `fonte`, `autore`, `data`, `sintesi`, `url` | VIR, Corte dei conti, UPB, studi |
| `verdetto` | `id` (PK), `urn` (FK), `versione`, `esito`, `confidenza`, `motivazione`, `aggiornato_il`, `generato_da`, `approvato_da` | versionato; `generato_da`: umano / claude |

Le tabelle delle schede non sono ancora nella DDL: si creano in Fase 2, dopo le decisioni aperte in `05_stato_e_decisioni.md` (schede per articolo, verdetto per obiettivo).

## Regole
- `verdetto` non si sovrascrive: ogni cambio crea una nuova `versione`.
- Nessuna riga in `obiettivo`, `valutazione` o `verdetto` senza URL di fonte.
- Un verdetto generato da Claude è visibile nell'app solo se `approvato_da` è valorizzato.
- Relazioni: `urn_origine` resta vuoto quando il riferimento in Gazzetta non si risolve in un atto di Normattiva; in quel caso `origine_gazzetta_codice` e `origine_gazzetta_data` conservano il riferimento. `urn_origine` non è una FK perché l'atto che dispone può essere fuori perimetro (DPR, decreti ministeriali, atti anteriori al 1990).
- `nota` conserva il testo originale della nota di aggiornamento di Normattiva: il `tipo` è ricavato da quel testo e va sempre verificabile.
- La data della nota di Normattiva non è la data della modifica (è quasi sempre la data di caricamento): non si usa.

## Come si riempie `legge` (pipeline Normattiva, Task 1.1)
| Campo | Origine |
|---|---|
| `tipo`, `numero`, `data`, `titolo` | ricerca avanzata di Normattiva |
| `gazzetta_data`, `gazzetta_numero`, `gazzetta_codice` | ricerca avanzata; con più pubblicazioni per lo stesso URN si tiene la più vecchia |
| `link_normattiva` | permalink costruito dall'URN |
| `stato` | `abrogata` se Normattiva segna l'atto come abrogato; `decaduta` se è un D.L. che Normattiva dichiara "decaduto per mancata conversione", oppure un D.L. abrogato senza legge di conversione il cui testo originale ha smesso di valere entro 60 giorni (o senza export); altrimenti `vigente`. Per i decaduti `data_abrogazione` è il giorno dopo la fine di vigenza del testo originale |
| `data_abrogazione` | inizio dell'ultima versione nell'export multivigente (coincide con l'entrata in vigore dell'atto abrogante) |
| `data_entrata_vigore` | inizio di vigenza più vecchio fra gli articoli del testo originale |
| `governo_id` | governo in carica alla data di emanazione |
| `materia` | non disponibile da Normattiva: resta vuota |

Le relazioni `converte` vengono dalle note di aggiornamento del D.L. e, perché le note la citano solo a volte, dal titolo della legge di conversione ("Conversione in legge, con modificazioni, del decreto-legge 28 gennaio 2019, n. 4"): in quel caso `nota` contiene il titolo della legge.

## Storico modifiche dello schema
- v1.1 (2026-10-27): dopo lo spike Normattiva (`docs/spike_normattiva.md`). Nuova tabella `governo`; in `legge` aggiunti `data_entrata_vigore`, `gazzetta_data`, `gazzetta_numero`, `gazzetta_codice`, `governo_id`, `aggiornato_il`; `stato` = vigente / abrogata / decaduta, "modificata" derivata nella vista `legge_estesa`. In `relazione_normativa` aggiunti `articolo_origine`, `articolo_destinazione`, `nota`, `origine_gazzetta_codice`, `origine_gazzetta_data`; nuovi tipi abroga_parziale, converte, delega; `urn_origine` non più FK. Nuova tabella `pronuncia_costituzionale`. `iter`: voti opzionali. Tabella tecnica `gazzetta_urn`.
- v1 (2026-10-27): prima versione.
