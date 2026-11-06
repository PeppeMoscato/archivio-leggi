Data: 2026-10-29
Decisione: L'API legge Neon con il ruolo `api_lettura` (`api/deploy/ruolo_sola_lettura.sql`): solo SELECT, sola lettura per default, `statement_timeout` 15 s, massimo 10 connessioni; indirizzo diretto, non il pooler
Motivo: Una seconda barriera oltre al READ ONLY dell'API; una query lenta non consuma CU-ore. L'API ha già il suo pool
