Data: 2026-10-28
Decisione: Indice GIN `legge_titolo_fts` sul titolo (schema v1.2, nessuna tabella cambia)
Motivo: Senza indice la ricerca è circa 8 volte più lenta (250-370 ms contro 30-55 ms su 9.000 titoli in locale); sul compute minimo di Neon sarebbe peggio
