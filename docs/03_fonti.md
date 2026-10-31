# Fonti dati

Verificate il 27/10/2026. Il progetto è non commerciale, quindi sono utilizzabili anche fonti con licenza NC.

| Fonte | Cosa dà | Accesso | Licenza / limiti |
|---|---|---|---|
| Normattiva open data — https://dati.normattiva.it | Testo di ogni atto, tutte le versioni nel tempo (multivigenza), modifiche, abrogazioni; premesse del testo originale di D.L. e D.Lgs. (motivazioni, basi giuridiche, legge delega) | API HTTP gratuita; client Python `normattiva-sdk` (pip) con ricerca, cronologia, export in blocco | CC BY 4.0 dal 1/1/2026. Attribuzione obbligatoria (vedi sotto) |
| Camera dei deputati — https://dati.camera.it | Iter dei progetti di legge, votazioni, firmatari, deputati e gruppi | SPARQL: http://dati.camera.it/sparql. I voti dei deputati 1996-2013 (XIII-XVI) solo dalle schede HTML di documenti.camera.it: 3 pagine alla volta, una legislatura alla volta, cache delle schede lette | **CC BY-SA 4.0** (pagine dei dataset, es. https://dati.camera.it/dataset/5364, verificato il 29/10/2026): attribuzione, e i dati della Camera che ridistribuiamo, anche rielaborati, con la stessa licenza. Le schede HTML non indicano una licenza; il robots.txt non le esclude |
| Senato — https://dati.senato.it | Disegni di legge e iter, votazioni d'Aula, identificativo del testo presentato (`osr:testoPresentato`) | SPARQL: http://dati.senato.it/sparql. Le pagine e i PDF di www.senato.it (testo presentato e relazione illustrativa) rispondono con un controllo anti-robot ai programmi (sonda del 29/10/2026): solo link, non si aggira. Il 31/10/2026 lo SPARQL ha risposto 403 dopo qualche migliaio di richieste di voti di fila: per aggiornare solo iter e fasi c'è `senato-estrai --senza-voti` | Linked open data |
| Relazioni AIR/VIR | Obiettivi e indicatori ex ante (AIR), verifiche ex post (VIR) | PDF: relazione annuale al Parlamento, piani biennali VIR dei ministeri | Pubbliche; estrazione con Claude + revisione |
| Istat — https://esploradati.istat.it/SDMXWS/rest | Serie storiche per gli indicatori | API SDMX | Max 5 query/minuto per IP → cache locale obbligatoria |
| Openpolis (OPDM API) | Dati parlamentari arricchiti | API, token opzionale | CC BY-NC: ok perché il progetto è non commerciale. Citare "Fonte: Openpolis" |
| Wikipedia — https://en.wikipedia.org | Partiti di ciascun governo (`ingest/archivio/governi_partiti.csv`): riquadro "Member parties" ed "External support" della pagina del governo | Lettura a mano. Ripiego: senato.it, storia.camera.it e governo.it non si leggono dai programmi (30/10/2026); da confrontare con storia.camera.it | CC BY-SA 4.0: citare la pagina (una per riga del CSV) |
| Corte dei conti, UPB, Banca d'Italia, studi accademici | Valutazioni e analisi controfattuali | Ricerca manuale, solo per le leggi delle schede | Citare sempre l'URL |

## Gerarchia delle fonti nelle schede
Decisa il 29/10/2026, alla revisione della scheda Sirchia.
1. **Fonti ufficiali e dati**: Normattiva, Gazzetta Ufficiale, Camera, Senato, Istat, ISS, Banca d'Italia, Corte dei conti, UPB, AIR/VIR.
2. **Studi**: articoli peer-reviewed e working paper di istituti di ricerca. Un working paper si segnala come tale.
3. **Stampa e divulgazione**: solo per contesto, o per trovare la fonte primaria.

Regole:
- Ogni numero si cita dalla fonte primaria. Se arriva dalla stampa, si risale allo studio o alla tavola originale.
- Se la fonte primaria non si trova, il numero resta nella scheda con l'asterisco e la nota "dato riportato dalla stampa, studio originale non trovato". Un numero con l'asterisco non conta per il verdetto.
- Ogni numero dice a quale zona, fascia d'età e periodo si riferisce (uno studio su Firenze non vale per l'Italia).

## Attribuzione obbligatoria Normattiva (footer dell'app)
Fonte: Normattiva (https://www.normattiva.it), Istituto Poligrafico e Zecca dello Stato, in licenza CC BY 4.0. Testo non autentico e gratuito: l'unico testo ufficiale è quello pubblicato sulla Gazzetta Ufficiale a mezzo stampa.

## Strumenti utili per prototipare (di terzi, non ufficiali)
- `it-eli-mcp`: server MCP per Normattiva e Corte costituzionale. **Non trovato su PyPI il 27/10/2026**: non usarlo finché non si trova la fonte.
- `open-parlamento-mcp` (PyPI, v0.3.4 al 27/10/2026): iter Camera/Senato, relazioni di modifica Normattiva, Gazzetta Ufficiale, Eurostat.
