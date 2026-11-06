Data: 2026-10-29
Testo: API, voto per gruppo. `GET /votazioni/{id}` con la legge, il ddl e il voto per gruppo (denominazione valida alla data); `/leggi/{urn}/votazioni?gruppi=true` aggiunge i gruppi a ogni votazione della pagina. Nessuna modifica allo schema: usa la vista `voto_gruppo`. 31 prove su Postgres 16 locale; prova di carico in locale su 44.000 votazioni generate.
