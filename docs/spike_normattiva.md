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

## 2. Risultati sulle risposte reali (27/10/2026)

Prima esecuzione: [run 40489368803](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40489368803). L'API risponde da GitHub Actions senza problemi (circa 2 minuti e mezzo in tutto).

### Atti di prova

| Atto | Classe | Stato atteso | Abrogato (export) | Versioni | Modifiche | Primo atto modificante risolto |
|---|---|---|---|---|---|---|
| L. 3/2003 (Sirchia) | AGGIORNATO | vigente | no | 28 | 20 | D.L. 4/2003 |
| D.Lgs. 9/2002 (patente a punti) | AGGIORNATO | vigente | no | 3 | 12 | D.L. 121/2002 |
| D.L. 4/2019 (RdC) | AGGIORNATO | RdC abrogato | no | 28 | 44 | L. 26/2019 (legge di conversione) |
| L. 109/1994 (Merloni) | ABROGATO | abrogata | sì | 23 | 49 | D.Lgs. 163/2006 |
| D.Lgs. 626/1994 | ABROGATO | abrogato | sì | 34 | 196 | D.Lgs. 81/2008 |

### Atti emanati dal 1990

| Tipo | Nel perimetro | Totale | Abrogati | Aggiornati |
|---|---|---|---|---|
| Legge | sì | 4.335 | 269 | 911 |
| Legge costituzionale | sì | 28 | 0 | 0 |
| Decreto-legge | sì | 2.463 | 1.416 | 1.023 |
| Decreto legislativo | sì | 2.101 | 291 | 856 |
| DPR | no | 1.425 | 279 | 362 |
| DPCM | no | 341 | 68 | 55 |
| Decreto ministeriale | no | 70 | 23 | 22 |

### Cosa ne ricaviamo
1. **L'SDK funziona** per ricerca, dettaglio, export multivigente e risoluzione Gazzetta → URN. Si può usare per la pipeline.
2. **Lo stato è affidabile a livello di atto intero**: le due leggi abrogate risultano ABROGATO, le altre AGGIORNATO. Il D.L. 4/2019 risulta non abrogato perché è abrogata solo la parte sul RdC: lo stato per articolo serve per le schede, non per l'archivio.
3. **Le relazioni di modifica si ricostruiscono**: dal riferimento di Gazzetta si arriva all'URN dell'atto modificante con una chiamata. Per la conversione del D.L. 4/2019 il modificante è la L. 26/2019: la relazione `converte` è ricavabile.
4. **Un URN può essere ambiguo**: per il D.L. 4/2019 il dettaglio risponde con due atti distinti (probabilmente il decreto originale e il testo coordinato con la legge di conversione: da confermare con la seconda esecuzione). La pipeline deve gestire più pubblicazioni per lo stesso URN.
5. **Volume**: circa 8.900 atti nel perimetro dal 1990. I soli metadati stanno largamente nel piano Free di Neon (1 GB).
6. **Decreti-legge "abrogati"**: 1.416 su 2.463. Probabilmente la classe ABROGATO comprende anche i D.L. decaduti o reiterati negli anni '90. Va verificato prima di mostrare il dato come "abrogato".
7. **Obiettivo di lungo periodo**: Normattiva contiene solo 341 DPCM e 70 decreti ministeriali dal 1990, una piccola parte di quelli emanati. Per "tutte le decisioni dei governi" servirà un'altra fonte (Gazzetta Ufficiale, siti dei ministeri).
