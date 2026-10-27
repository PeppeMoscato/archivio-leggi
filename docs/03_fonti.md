# Fonti dati

Verificate il 27/10/2026. Il progetto è non commerciale, quindi sono utilizzabili anche fonti con licenza NC.

| Fonte | Cosa dà | Accesso | Licenza / limiti |
|---|---|---|---|
| Normattiva open data — https://dati.normattiva.it | Testo di ogni atto, tutte le versioni nel tempo (multivigenza), modifiche, abrogazioni | API HTTP gratuita; client Python `normattiva-sdk` (pip) con ricerca, cronologia, export in blocco | CC BY 4.0 dal 1/1/2026. Attribuzione obbligatoria (vedi sotto) |
| Camera dei deputati — https://dati.camera.it | Iter dei progetti di legge, votazioni, firmatari | SPARQL: http://dati.camera.it/sparql | Linked open data |
| Senato — https://dati.senato.it | Disegni di legge e iter, votazioni d'Aula | SPARQL: http://dati.senato.it/sparql | Linked open data |
| Relazioni AIR/VIR | Obiettivi e indicatori ex ante (AIR), verifiche ex post (VIR) | PDF: relazione annuale al Parlamento, piani biennali VIR dei ministeri | Pubbliche; estrazione con Claude + revisione |
| Istat — https://esploradati.istat.it/SDMXWS/rest | Serie storiche per gli indicatori | API SDMX | Max 5 query/minuto per IP → cache locale obbligatoria |
| Openpolis (OPDM API) | Dati parlamentari arricchiti | API, token opzionale | CC BY-NC: ok perché il progetto è non commerciale. Citare "Fonte: Openpolis" |
| Corte dei conti, UPB, Banca d'Italia, studi accademici | Valutazioni e analisi controfattuali | Ricerca manuale, solo per le leggi delle schede | Citare sempre l'URL |

## Attribuzione obbligatoria Normattiva (footer dell'app)
Fonte: Normattiva (https://www.normattiva.it), Istituto Poligrafico e Zecca dello Stato, in licenza CC BY 4.0. Testo non autentico e gratuito: l'unico testo ufficiale è quello pubblicato sulla Gazzetta Ufficiale a mezzo stampa.

## Strumenti utili per prototipare (di terzi, non ufficiali)
- `it-eli-mcp`: server MCP per Normattiva e Corte costituzionale. **Non trovato su PyPI il 27/10/2026**: non usarlo finché non si trova la fonte.
- `open-parlamento-mcp` (PyPI, v0.3.4 al 27/10/2026): iter Camera/Senato, relazioni di modifica Normattiva, Gazzetta Ufficiale, Eurostat.
