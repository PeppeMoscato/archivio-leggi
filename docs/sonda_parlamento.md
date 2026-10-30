# Sonda Camera e Senato

Task 1.2 (ingestione iter da Camera e Senato). Domanda: cosa danno davvero gli endpoint SPARQL di dati.camera.it e dati.senato.it su iter, iniziativa, votazioni, gruppi e governi? Le risposte servono a scrivere lo schema v1.2 prima della pipeline.

Script: [`ingest/sonda_parlamento.py`](../ingest/sonda_parlamento.py). Gira sul workflow GitHub Actions "Sonda Camera e Senato" (Actions → Run workflow, oppure a ogni PR che lo modifica). Il report esce nel log e nel riepilogo del job. Dal container cloud di Claude Code i due domini sono bloccati.

Esecuzioni del 27/10/2026: [run 40578550705](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40578550705), [40579509709](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40579509709), [40579983356](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40579983356), [40580318126](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40580318126).

## 1. Camera (dati.camera.it)

Fra le 20:29 e le 20:42 del 27/10/2026 l'endpoint ha risposto **502 Bad Gateway** a ogni richiesta, anche a una query banale (`SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 3`), sia in HTTPS sia in HTTP. È un problema del server della Camera, non della query. Da riprovare: finché non risponde, i voti dei deputati non sono verificati.

Alle 21:10 dello stesso giorno l'endpoint è tornato a rispondere ([run 40584430068](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40584430068), job `sonda (camera)`): 22 classi esplorate (atti, votazioni, voti, deputati, gruppi, governi, membri del governo). Le query mirate della seconda tornata sono nel [run 40587072564](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40587072564).

Endpoint Virtuoso come quello del Senato: risposte troncate a 10.000 righe, OFFSET oltre 10.000 righe ordinate in errore (`SR353`), quindi paginazione per chiave. Funzionano `FILTER IN`, `VALUES` e le sottoquery. **Ogni tripla compare due volte** (due grafi): i conteggi senza DISTINCT sono gonfiati. I numeri qui sotto sono quelli della sonda divisi per due (per la XV: 112 leggi, come al Senato) e vanno presi come ordine di grandezza; i conti esatti delle votazioni da caricare sono nella stima della Pipeline Camera (sezione 4).

### Copertura
| Legislatura | Leggi (`ocd:legge`) | Votazioni d'Aula | … collegate a un atto | Votazioni finali |
|---|---|---|---|---|
| X (1987-1992) | 1.077 | — | — | — |
| XI (1992-1994) | 314 | — | — | — |
| XII (1994-1996) | 295 | — | — | — |
| XIII (1996-2001) | 906 | 34.629 | 32.254 | 857 |
| XIV (2001-2006) | 686 | 23.721 | 22.140 | 654 |
| XV (2006-2008) | 112 | 5.308 | 4.572 | 151 |
| XVI (2008-2013) | 387 | 10.517 | 9.265 | 407 |
| XVII (2013-2018) | 378 | 24.930 | 19.361 | 481 |
| XVIII (2018-2022) | 314 | 10.724 | 7.053 | 327 |
| XIX (dal 2022) | 361 | 20.177 | 10.457 | 416 |

Le votazioni nominali della Camera cominciano con la XIII legislatura, come i dati del Senato. **Il voto di ogni deputato però c'è solo dalla XVII (2013)**: per XIII-XVI l'endpoint ha le votazioni con esito e totali, ma nessun `ocd:voto` (sonda `camera-voti` del 29/10/2026, sezione 4).

### Cosa c'è
1. **Leggi con l'URN di Normattiva.** `ocd:legge` ha `ocd:lex` (il permalink di Normattiva con l'URN), numero, data, titolo, tipo (Ordinaria / Costituzionale) e i lavori preparatori (`ocd:lavoriPreparatori` → `ocd:rif_attoCamera`), anche per la X, XI e XII legislatura. Esempio: L. 241/1990 → atto C.1913 della X. I lavori preparatori indicano a volte un atto diverso da quello votato: per la Legge Sirchia citano C.2122-quater, mentre le votazioni sono su C.2122-bis e C.2122-bis-B (gli stessi atti dell'iter del Senato).
2. **Atti.** Numero (dall'IRI, es. `ac14_2122-bis` → `2122-BIS`), data di presentazione, titolo, iniziativa (Parlamentare, Governo, Popolare, Regioni, CNEL, Mista), governo (`ocd:rif_governo`), primo firmatario e altri firmatari come persone (`ocd:primo_firmatario`, `ocd:altro_firmatario`) e come testo (`dc:creator`, `dc:contributor`, es. "TREMONTI GIULIO, Ministro dell'Economia e delle finanze (II Governo Berlusconi)"). Gli stati dell'iter ci sono solo dalla XVII.
3. **Votazioni.** Titolo ("Votazione Emendamento 2.2 DDL n.2122-BIS"), descrizione ("EMENDAMENTO 2.2 VALPIANA (RC)"), tipo (Emendamento, Articolo, Ordine del Giorno, Mozione, Finale atto Camera, Risoluzione, Pregiudiziale, ...), data, presenti, votanti, favorevoli, contrari, astenuti, maggioranza, approvato, `votazioneFinale`, `votazioneSegreta`, `richiestaFiducia`, atto (`ocd:rif_attoCamera`) e la scheda sul sito della Camera.
4. **Voti dei deputati, dalla XVII.** Un `ocd:voto` per deputato e votazione (`vd17_487_077_302779`), con `ocd:rif_votazione`, `ocd:rif_deputato`, il gruppo e il voto in `dc:type`. In una votazione della XVII: 26 favorevoli, 417 contrari, 7 astenuti, 179 "non ha votato". Per XIII-XVI i nomi stanno solo nella scheda HTML di ogni votazione (`dc:relation`, sezione 4).
5. **Fiducia.** `richiestaFiducia = 1` dalla XIV: dalla XIV alla XIX (conteggi della sonda, con i doppioni: da 36 nella XV a 154 nella XIX). Segna tutta la procedura: l'articolo su cui il governo pone la fiducia e anche la votazione finale che segue. La pipeline tiene "finale" la finale e chiama "fiducia" le altre.
6. **Deputati e gruppi.** Un deputato per legislatura (`d305578_17`), con la persona nell'identificativo (305578): si usa la persona, uguale in tutte le legislature. Adesioni ai gruppi con date (`ocd:aderisce`). Gruppi per legislatura con sigla e date; i nomi precedenti stanno in `ocd:denominazione` ("gia' ITALIA VIVA (IV) fino a 31.07.2022").
7. **Governi** con date di inizio e fine dal 1948: coincidono con `governi.csv` (fonte Senato).

### Cosa non c'è
- Votazioni prima della XIII legislatura: per le leggi 1990-1996 ci sono iter e firmatari, non i voti.
- Voti dei singoli deputati per XIII-XVI (1996-2013) nell'endpoint: solo nelle schede HTML.
- Partiti della coalizione di governo: come al Senato, nessun dato strutturato.
- Letture al Senato degli iter 1990-1996.

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
- La Camera entra nelle stesse tabelle: votazioni sulle fasi Camera degli iter del Senato (XIII-XIX), iter propri per la X-XII.

## 4. Camera: votazioni da caricare e voti dei deputati (28-30/10/2026)

**Stima** (`camera-stima`, [run 40717998103](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40717998103), job `stima`): votazioni sulle fasi Camera degli iter diventati legge e voti individuali ricavati dai totali della fonte (favorevoli + contrari + astenuti).

| Legislatura | Votazioni da caricare | Palesi | Voti individuali (dai totali) | Voti dei deputati nell'endpoint |
|---|---|---|---|---|
| XIII | 24.445 | 24.441 | 8.956.929 | no |
| XIV | 23.748 | 23.048 | 9.771.052 | no |
| XV | 3.431 | 3.416 | 1.574.899 | no |
| XVI | 8.489 | 8.480 | 4.096.521 | no |
| XVII | 18.093 | 17.983 | 7.407.784 | sì |
| XVIII | 7.996 | 7.922 | 3.462.911 | sì |
| XIX | 13.883 | 13.879 | 3.620.791 | sì |
| Totale | 100.085 | 99.169 | 38.890.887 | |

**Prima prova della XV** nel Postgres temporaneo (stesso run, job `carica`, prima di leggere le schede): 3.431 votazioni (2.023 emendamenti, 437 articoli, 116 finali, 14 fiducie, 14 pregiudiziali, 827 altre) su 123 fasi Camera degli iter del Senato, 114 con una votazione finale nominale; 1,2 MB di righe. Nessun voto individuale (vedi sotto). XII: 295 iter dai lavori preparatori, tutti collegati a una legge di Normattiva.

**Voti dei deputati** (sonda `camera-voti`, [run 40881947732](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40881947732)): per XVII, XVIII e XIX ogni votazione ha i suoi `ocd:voto` e ogni deputato ha i suoi voti; per XIII, XIV, XV e XVI nessuna tripla punta alle votazioni e i deputati non hanno voti. La pipeline chiede i voti all'endpoint dalla XVII (`PRIMA_CON_VOTI_INDIVIDUALI`) e li legge dalle schede HTML per XIII-XVI.

**Schede HTML** (sonda `camera-schede`, [run 40885410769](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40885410769)): la scheda di ogni votazione su documenti.camera.it (l'URL in `dc:relation`) ha l'elenco completo anche per XIII-XVI: nominativo (COGNOME NOME), sigla del gruppo e voto (Favorevole, Contrario, Astensione, Non ha partecipato, In missione). Circa 75 KB a pagina, una pagina per votazione: circa 60.000 pagine per XIII-XVI. I nomi non hanno identificativi e sono i nomi d'uso ("BINDI ROSY", "CAPARINI DAVIDE"), mentre l'endpoint ha quelli dell'anagrafe ("ROSARIA", "DAVIDE CARLO"): la pipeline li collega ai deputati della legislatura per cognome e nome, senza accenti né apostrofi; se non basta, per il cognome più lungo che corrisponde (anche un doppio cognome accorciato) e, tra più candidati, per sigla del gruppo e poi iniziale del nome. Decisione del 29/10/2026 (utente): si leggono le schede per avere i voti dei deputati anche per XIII-XVI.

**Carico sul sito** (verifica di liceità del 29/10/2026): una legislatura alla volta (`max-parallel: 1`), tre pagine alla volta con mezzo secondo di pausa (circa 2 pagine al secondo), `Retry-After` rispettato su 429 e 503 (al massimo 10 minuti), stop dopo 20 errori di fila, un User-Agent con il link al repository. Schede e voti dell'endpoint vanno in una cache (`dati/cache/camera_<leg>_*.jsonl.gz`) salvata dal workflow anche quando il job fallisce: rilanciando i job falliti si riparte da dove ci si era fermati. Serviva anche per i guasti dell'endpoint: il 29/10/2026 ha risposto 502 per oltre 11 minuti nel pomeriggio e poi dalle 18:25 UTC fino alla notte.

**Prova della XV e della XIX** ([run 40930651361](https://github.com/PeppeMoscato/archivio-leggi/actions/runs/40930651361), 30/10/2026, Postgres temporaneo):

| | XV (schede HTML) | XIX (endpoint) |
|---|---|---|
| Votazioni | 3.431 | 13.883 |
| Voti individuali caricati | 1.543.636 (98% dei 1.574.899 dei totali) | 3.620.791 (uguale ai totali) |
| Righe di `votazione` | 7,4 MB | 19 MB |
| Tempo di estrazione | circa 21 minuti di schede | |
| Votazioni con elenchi diversi dai totali | 3.328 | 0 |

XV: 50 schede senza tabella dei voti; 5 nominativi non collegati (6.450 voti), tra cui D'ANTONA OLGA, ROSSI GASPARRINI FEDERICA e CATANOSO BASILIO; 58 nominativi collegati per cognome, controllati uno per uno (es. BINDI ROSY → ROSARIA, MINNITI MARCO → DOMENICO). Oltre ai nomi non collegati mancano circa 24.800 voti, circa 7 per votazione: gli elenchi delle schede non tornano esattamente con i totali della fonte. È un limite noto dei voti XIII-XVI: i totali della votazione restano quelli ufficiali, gli elenchi servono al voto per gruppo e per deputato. XIX: 112 voti di deputati che non risultano tra i deputati caricati (su 3,6 milioni).

**Spazio su Neon.** Dalle prove: circa 4 byte a voto più circa 380 byte a votazione, più il 9% per indici e tabelle collegate. Camera XIII-XIX: 100.085 votazioni e 38,9 milioni di voti, circa 195 MB di righe, **circa 215 MB** in tutto. Senato XIII-XIX circa 70 MB. Con Normattiva (qualche decina di MB) l'archivio resta ben sotto 1 GB del piano Free: si caricano tutte le votazioni.
