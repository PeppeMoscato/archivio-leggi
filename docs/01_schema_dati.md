# Schema dati — v1.2

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

Vista `legge_estesa`: tutti i campi di `legge` più `numero_modifiche` (relazioni in entrata di tipo modifica, abroga_parziale, proroga) e `modificata` (`numero_modifiche > 0`). "Modificata" non è uno stato: si ricava.

### Parlamento e governi (Task 1.2)

Da dati.senato.it e da dati.camera.it (`docs/sonda_parlamento.md`). Gli `id` di iter, fasi, gruppi e votazioni sono testi con il ramo davanti (`senato:15167`, `camera:vs14_115_096`): restano stabili se si ricarica e dicono da dove viene il dato. I parlamentari hanno un `id` numerico, perché compaiono negli elenchi dei voti e un numero occupa meno spazio.

| Tabella | Campi | Note |
|---|---|---|
| `governo_partito` | `governo_id` (FK governo), `partito`, `ruolo`, `fonte_url` | PK (`governo_id`, `partito`). `ruolo`: governo / appoggio esterno. Compilata a mano (`ingest/archivio/governi_partiti.csv`): nessuna fonte strutturata |
| `iter` | `id` (PK), `urn` (FK legge), `legislatura`, `natura`, `titolo`, `iniziativa`, `data_presentazione`, `data_approvazione`, `numero_legge`, `data_legge`, `fonte_url` | Un procedimento parlamentare, dalla prima presentazione all'approvazione definitiva. `natura`: ordinaria / costituzionale / conversione di decreto-legge / bilancio. `iniziativa`: governativa / parlamentare / popolare / regionale / CNEL / di ente / di commissione (quella della prima fase). `numero_legge` e `data_legge` come li dà la fonte: servono a costruire `urn` e a verificarlo. `urn` vuoto se la legge non si trova in `legge` |
| `fase_iter` | `id` (PK), `iter_id` (FK iter), `progressivo`, `ramo`, `numero`, `titolo`, `data_presentazione`, `stato`, `data_stato`, `fonte_url` | Una lettura in un ramo. `ramo`: camera / senato. `numero` come lo scrive la fonte (`C.2122-BIS`, `S.1271-B`). `stato` è il testo della fonte (es. "approvato con modificazioni") |
| `firmatario` | `id` (PK), `fase_id` (FK fase_iter), `nome`, `tipo`, `primo_firmatario`, `parlamentare_id` (FK parlamentare) | `nome` è il presentatore come lo scrive la fonte (es. "Pres. Consiglio Silvio Berlusconi (Gov. Berlusconi-II)"). `tipo` = tipo di iniziativa. `parlamentare_id` solo se la fonte collega la persona |
| `parlamentare` | `id` (PK, numero), `codice` (unico), `ramo`, `nome`, `cognome`, `fonte_url` | `codice` è l'identificativo della fonte con il ramo davanti (`senato:274`; per la Camera la persona, uguale in tutte le legislature: `camera:305578`). Un deputato e un senatore sono righe diverse anche se è la stessa persona (le fonti non le uniscono) |
| `gruppo` | `id` (PK), `ramo`, `nome`, `sigla` | `nome` e `sigla` = denominazione più recente |
| `denominazione_gruppo` | `gruppo_id` (FK gruppo), `inizio`, `fine`, `nome`, `sigla` | PK (`gruppo_id`, `inizio`). I gruppi cambiano nome nel tempo (Lega Nord → Lega Salvini Premier): l'app mostra il nome valido alla data del voto |
| `adesione_gruppo` | `parlamentare_id` (FK), `gruppo_id` (FK), `inizio`, `fine`, `carica` | PK (`parlamentare_id`, `gruppo_id`, `inizio`). `fine` vuota = adesione in corso |
| `votazione` | `id` (PK), `fase_id` (FK fase_iter), `ramo`, `legislatura`, `data`, `tipo`, `descrizione`, `esito`, `presenti`, `votanti`, `favorevoli`, `contrari`, `astenuti`, `maggioranza`, `voti_favorevoli`, `voti_contrari`, `voti_astenuti`, `fonte_url` | `tipo`: finale / fiducia / articolo / emendamento / pregiudiziale / altro, ricavato da `descrizione` (l'etichetta della fonte). `voti_*` sono elenchi di `parlamentare.id` (array di numeri): vuoti se il voto non è nominale (es. votazione segreta). I totali vengono dalla fonte e non si ricalcolano dagli elenchi |

Vista `voto_gruppo`: per ogni votazione e gruppo, quanti favorevoli, contrari e astenuti, contando ogni parlamentare nel gruppo a cui aderiva il giorno della votazione. Si ricava da `votazione` e `adesione_gruppo`: non è una tabella.

Regole:
- Tutte le votazioni d'Aula sui ddl diventati legge (finali, fiducia, articoli, emendamenti, pregiudiziali), tranne le verifiche del numero legale. I voti su ddl mai diventati legge restano fuori: non si collegano a nessuna legge.
- Una votazione si collega alla sua fase tramite l'oggetto della trattazione della fonte; se manca (legislature più vecchie), dal numero del ddl scritto nell'etichetta ("Disegno di legge n. 3660. Votazione finale"). Le votazioni che non si collegano non si caricano e si contano nel rapporto.
- I voti dei singoli stanno in array di numeri e non in una riga per voto. Senato: circa 44.000 votazioni, circa 60 MB. Una riga per voto sarebbero oltre 10 milioni di righe, più di mezzo GB del piano Free di Neon. Per la Camera (deputati doppi, molte più votazioni) il conto si rifà prima di caricarla.
- Una votazione è di fiducia solo se la fonte lo dice. Al Senato l'etichetta lo dice dalla XVII legislatura (2013); prima non si distingue. Alla Camera il campo `richiestaFiducia` lo dice dalla XIV (2001): segna anche la votazione finale che segue la fiducia, che resta `finale`.
- Camera, XIII-XIX: gli iter e le fasi sono quelli del Senato (che ha anche le letture alla Camera); le votazioni della Camera si attaccano alla fase Camera con lo stesso numero (`C.2122-BIS`). Si carica prima il Senato, poi la Camera; ricaricare il Senato aggiorna iter e fasi senza cancellarli, così le votazioni della Camera restano. Chi "non ha votato" non sta negli elenchi. I voti dei singoli deputati ci sono nell'endpoint solo dalla XVII (2013): per XIII-XVI vengono dalle schede HTML di ogni votazione, con il nome collegato al deputato per cognome e nome (`docs/sonda_parlamento.md` sezione 4).
- Leggi senza voto nominale (approvate in commissione o per alzata di mano): l'iter c'è, la votazione no. L'app scrive "voto non nominale", non zero.
- Leggi 1990-1996: nessun dato del Senato (copre dalla XIII legislatura, maggio 1996) e nessuna votazione nominale alla Camera (dalla XIII). Gli iter vengono dai lavori preparatori della Camera (`camera:L1990_241`): solo le letture alla Camera, con iniziativa e firmatari, senza voti.
- Decreti-legge: iter e voti sono quelli della legge di conversione (relazione `converte`). Decreti legislativi: nessun voto finale in Parlamento.

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
- v1.2, nota (2026-10-28): nessuna modifica alle tabelle. Regole per la Camera (votazioni sulle fasi del Senato, iter 1990-1996 dai lavori preparatori, codice dei deputati per persona, fiducia da `richiestaFiducia`); voti dei deputati dalla XVII, nota del 2026-10-29).
- v1.2 (2026-10-27): dopo la sonda su Camera e Senato (`docs/sonda_parlamento.md`). La tabella `iter` della v1.1 (mai creata nella DDL) diventa `iter` + `fase_iter` + `votazione`; nuove tabelle `firmatario`, `parlamentare`, `gruppo`, `denominazione_gruppo`, `adesione_gruppo`, `governo_partito`; vista `voto_gruppo`. Tutte le votazioni d'Aula sui ddl diventati legge, con i voti individuali in array di `parlamentare.id` numerici.
- v1.1 (2026-10-27): dopo lo spike Normattiva (`docs/spike_normattiva.md`). Nuova tabella `governo`; in `legge` aggiunti `data_entrata_vigore`, `gazzetta_data`, `gazzetta_numero`, `gazzetta_codice`, `governo_id`, `aggiornato_il`; `stato` = vigente / abrogata / decaduta, "modificata" derivata nella vista `legge_estesa`. In `relazione_normativa` aggiunti `articolo_origine`, `articolo_destinazione`, `nota`, `origine_gazzetta_codice`, `origine_gazzetta_data`; nuovi tipi abroga_parziale, converte, delega; `urn_origine` non più FK. Nuova tabella `pronuncia_costituzionale`. `iter`: voti opzionali. Tabella tecnica `gazzetta_urn`.
- v1 (2026-10-27): prima versione.
