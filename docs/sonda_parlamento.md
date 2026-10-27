# Sonda Camera e Senato

Task 1.2 (ingestione iter da Camera e Senato). Domanda: cosa danno davvero gli endpoint SPARQL di dati.camera.it e dati.senato.it su iter, iniziativa, votazioni, gruppi e governi? Le risposte servono a scrivere lo schema v1.2 prima della pipeline.

Script: [`ingest/sonda_parlamento.py`](../ingest/sonda_parlamento.py). Gira sul workflow GitHub Actions "Sonda Camera e Senato" (Actions → Run workflow, oppure a ogni PR che lo modifica). Il report esce nel log e nel riepilogo del job. Dal container cloud di Claude Code i due domini sono bloccati.

Esecuzioni del 27/10/2026: [run 40578550705](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40578550705), [40579509709](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40579509709), [40579983356](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40579983356), [40580318126](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40580318126).

## 1. Camera (dati.camera.it)

Fra le 20:29 e le 20:42 del 27/10/2026 l'endpoint ha risposto **502 Bad Gateway** a ogni richiesta, anche a una query banale (`SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 3`), sia in HTTPS sia in HTTP. È un problema del server della Camera, non della query. Da riprovare: finché non risponde, i voti dei deputati non sono verificati.

## 2. Senato (dati.senato.it)

Endpoint Virtuoso, risposte in 1-4 secondi. Limiti del motore: niente `SAMPLE` né `BIND`; i confronti con una stringa vanno fatti con `FILTER(STR(?x) = "...")`.

### Copertura
Dati dalla **XIII legislatura (9 maggio 1996)** in poi. Per le leggi 1990-1996 (legislature X, XI e XII) il Senato non ha dati strutturati.

| Legislatura | Ddl (fasi) | Votazioni d'Aula | Fasi del Senato diventate legge | … con votazioni collegate | Votazioni finali |
|---|---|---|---|---|---|
| XIII (1996-2001) | 13.318 | 6.578 | 1.228 | 196 | 161 |
| XIV (2001-2006) | 10.483 | 15.031 | 824 | 258 | 213 |
| XV (2006-2008) | 5.568 | 2.214 | 125 | 56 | 49 |
| XVI (2008-2013) | 9.572 | 7.054 | 450 | 222 | 231 |
| XVII (2013-2018) | 8.004 | 17.310 | 419 | 278 | 284 |
| XVIII (2018-2022) | 6.479 | 7.694 | 339 | 226 | 234 |
| XIX (dal 2022) | 5.303 | 8.400 | 388 | 258 | 261 |

### Cosa c'è
1. **Iter completo, anche alla Camera.** Ogni lettura è un `osr:Ddl` (una "fase"), con ramo (C o S), numero (es. `C.2122-BIS`, `S.1271-B`), data di presentazione, stato e data dello stato. Le fasi dello stesso iter si raccolgono con `osr:IterDdl`. Esempio, Legge Sirchia (L. 3/2003): C.2122 (stralcio) → C.2122-BIS approvato il 19/3/2002 → S.1271 approvato con modificazioni il 6/11/2002 → C.2122-BIS-B approvato con modificazioni l'11/12/2002 → S.1271-B approvato definitivamente il 20/12/2002.
2. **Legame con la legge pubblicata.** Le fasi dell'iter diventato legge hanno `osr:numeroLegge` e `osr:dataLegge`: con tipo, data e numero si costruisce l'URN di Normattiva. Natura del ddl: ordinaria, costituzionale, di conversione di decreto-legge, di approvazione di bilancio. Anomalie: 35 date `2100-01-01` (segnaposto) e alcune fasi con due numeri di legge; vanno scartate o segnalate.
3. **Iniziativa e firmatari.** `osr:iniziativa` porta il tipo (Parlamentare, Governativa, di ente, Popolare, di commissione, Regionale, CNEL), il presentatore come testo (es. "Pres. Consiglio Silvio Berlusconi (Gov. Berlusconi-II)") e il primo firmatario. I deputati firmatari sono collegati ai deputati della Camera (`ocd:rif_deputato`).
4. **Votazioni d'Aula con il voto di ogni senatore.** Ogni votazione ha esito, presenti, votanti, favorevoli, contrari, astenuti, maggioranza, numero legale, seduta (con data) e tipo (elettronica, segreta, nominale con appello, verifica del numero legale, controprova). Per ogni senatore: `osr:favorevole`, `osr:contrario`, `osr:astenuto`, `osr:presenteNonVotante`, `osr:inCongedoMissione`. In una votazione finale della XVIII: 168 favorevoli, 48 contrari, 43 astenuti, tutti con nome.
5. **Votazione → fase.** `osr:oggetto` → `osr:OggettoTrattazione` → `osr:relativoA` → ddl. Per le legislature più vecchie il collegamento manca spesso, ma l'etichetta riporta il numero ("Disegno di legge n. 3660. Votazione finale", "DDL n. 1306-B. Votazione finale").
6. **Gruppi parlamentari con le date.** Adesioni di ogni senatore (`ocd:aderisce`: gruppo, inizio, fine, carica) e denominazioni del gruppo nel tempo (es. il gruppo 33: Lega Nord → Lega Nord Padania → … → Lega Salvini Premier - Partito Sardo d'Azione), con sigla.
7. **Questione di fiducia.** Si riconosce dall'etichetta ("DDL n. 2542. Votazione questione di fiducia") solo dalla XVII legislatura: 1 votazione nella XVII, 30 nella XVIII, 59 nella XIX. Prima di allora le votazioni di fiducia non sono distinguibili nei dati del Senato.

### Cosa non c'è
- Partiti della coalizione di governo: nessun dato strutturato. Il governo compare solo nel testo del presentatore ("Gov. Berlusconi-II").
- Leggi 1990-1996.
- Un voto nominale per ogni legge: molte leggi sono approvate in commissione (sede deliberante) o per alzata di mano. Nella XIII, 161 votazioni finali per 1.228 fasi diventate legge.

## 3. Conseguenze per lo schema (proposta v1.2)
- La tabella `iter` della v1.1 (una riga con i voti) non basta: servono iter → fasi → votazioni, più parlamentari, gruppi e adesioni.
- I voti dei singoli parlamentari in forma compatta (un elenco per votazione) e solo per le votazioni finali e di fiducia: il resto (emendamenti, articoli) si aggiunge dopo con le stesse tabelle.
- Il voto per gruppo si ricava dai voti individuali e dalle adesioni alla data della votazione: è una vista, non dati copiati.
- I partiti dei governi si compilano a mano, con la fonte, come la tabella `governo`.
- La Camera entra nelle stesse tabelle quando l'endpoint risponde.
