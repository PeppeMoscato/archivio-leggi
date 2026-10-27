# Spike Normattiva

Task 0.2. Domanda: l'API open data di Normattiva, tramite `normattiva-sdk`, restituisce quello che serve per riempire le tabelle `legge` e `relazione_normativa` dello schema v1?

Script: [`ingest/spike_normattiva.py`](../ingest/spike_normattiva.py). Gira sul workflow GitHub Actions "Spike Normattiva" (a ogni PR che lo modifica, o a mano da Actions → Spike Normattiva → Run workflow). Il report esce nel riepilogo del job e il JSON grezzo come artifact `spike-normattiva`.

## 1. Cosa dice il codice dell'SDK (analisi a tavolino, 27/10/2026)

Letto dal pacchetto `normattiva-sdk` 0.1.0 su PyPI (MIT, alpha, una sola release). Ancora da confermare con le risposte reali (sezione 2).

| Campo dello schema v1 | Da dove arriva | Note |
|---|---|---|
| `legge.urn` | `Urn.legge()`, `Urn.decreto_legge()`, `Urn.decreto_legislativo()`; `AttoTrovato.urn` | Formato NIR uguale a quello dello schema. Forma URN verificata dall'SDK per 18 tipi di atto su 30, inclusi i quattro del perimetro e DPR, DPCM e DM |
| `tipo`, `numero`, `data` | `EstremiAtto` (`denominazione`, `numero`, `data`) | |
| `titolo` | `AttoTrovato.titolo`, `DettaglioAtto.titolo` | |
| `link_normattiva` | `DettaglioAtto.permalink` | |
| `stato` (vigente / abrogata) | filtro `classe` della ricerca: `SENZA_AGGIORNAMENTI`, `AGGIORNATO`, `ABROGATO`; flag `abrogato` nell'export | "Modificata" corrisponde alla classe `AGGIORNATO`: conferma che si può ricavare invece di salvarlo |
| `data_abrogazione` | non c'è un campo diretto | Va ricavata dalla fine dell'ultima finestra di vigenza (`FinestraVigenza.fine`) o dalle note di aggiornamento. Da verificare |
| `relazione_normativa` | export multivigente: `AttoStorico.aggiornamenti[].riferimenti[]` con Gazzetta (codice redazionale e data) e articolo dell'atto modificante | Non c'è l'URN dell'atto modificante: va risolto con `dettaglio_da_gazzetta()`, una chiamata per atto modificante distinto. Il `tipo` (modifica / abroga / proroga) si ricava solo dal testo della nota |
| aggiornamenti incrementali | `atti_aggiornati(dal, al)` | Utile per la pipeline settimanale |
| conteggi per tipo e anno | `ricerca_avanzata(...).totale` e faccette | Serve per stimare lo spazio su Neon |

Conseguenze probabili per lo schema v1.1 (da confermare):
- `stato` = vigente / abrogata (più decaduta per i D.L. non convertiti); "modificata" derivata dalla classe `AGGIORNATO`.
- `relazione_normativa` ha bisogno di un passo di risoluzione Gazzetta → URN, e di una cache dei codici redazionali già risolti.
- `relazione_normativa.tipo` all'inizio può valere solo "modifica" e "abroga"; "attua", "proroga", "converte" e "delega" richiedono di leggere il testo.

## 2. Risultati sulle risposte reali

Da compilare con il report del workflow.
