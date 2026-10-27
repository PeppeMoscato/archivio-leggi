# Schema dati — v1

Database: PostgreSQL. Chiave unica di ogni legge: URN NIR di Normattiva (es. `urn:nir:stato:legge:1990-08-07;241`).

Il cuore dello schema è il legame **obiettivo → indicatore → misura**.

| Tabella | Campi | Note |
|---|---|---|
| `legge` | `urn` (PK), `tipo`, `numero`, `data`, `titolo`, `materia`, `link_normattiva`, `stato`, `data_abrogazione` | `stato`: vigente / modificata / abrogata |
| `relazione_normativa` | `id` (PK), `urn_origine` (FK legge), `urn_destinazione` (FK legge), `tipo`, `data` | `tipo`: modifica / abroga / attua / proroga |
| `iter` | `id` (PK), `urn` (FK), `camera`, `numero_ddl`, `data_presentazione`, `data_approvazione`, `voti_favorevoli`, `voti_contrari` | da dati.camera.it e dati.senato.it |
| `obiettivo` | `id` (PK), `urn` (FK), `descrizione`, `fonte_url`, `tipo_fonte` | `tipo_fonte`: relazione illustrativa / AIR / dossier |
| `indicatore` | `id` (PK), `obiettivo_id` (FK), `nome`, `unita`, `fonte_dati`, `codice_serie` | `codice_serie`: es. dataflow Istat |
| `misura` | `indicatore_id` (FK), `periodo`, `valore` | PK composta (`indicatore_id`, `periodo`) |
| `valutazione` | `id` (PK), `urn` (FK), `fonte`, `autore`, `data`, `sintesi`, `url` | VIR, Corte dei conti, UPB, studi |
| `verdetto` | `id` (PK), `urn` (FK), `versione`, `esito`, `confidenza`, `motivazione`, `aggiornato_il`, `generato_da`, `approvato_da` | versionato; `generato_da`: umano / claude |

## Regole
- `verdetto` non si sovrascrive: ogni cambio crea una nuova `versione`.
- Nessuna riga in `obiettivo`, `valutazione` o `verdetto` senza URL di fonte.
- Un verdetto generato da Claude è visibile nell'app solo se `approvato_da` è valorizzato.

## Storico modifiche dello schema
- v1 (2026-10-27): prima versione.
