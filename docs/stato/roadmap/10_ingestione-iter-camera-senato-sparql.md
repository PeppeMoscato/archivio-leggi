Fase: Fase 1 — Archivio
Voce: Ingestione iter da Camera e Senato (SPARQL)
Fatto: sì
Nota: Task 1.2: Senato (PR #4) e Camera (PR #5) uniti e caricati su Neon il 30-31/10/2026
Situazione: Task 1.2 completato. Senato: pipeline dati.senato.it → Postgres (`ingest/archivio/senato.py`, `parlamento.py`), workflow "Pipeline Senato". Camera: pipeline dati.camera.it → Postgres (`ingest/archivio/camera.py`), workflow "Pipeline Camera"; votazioni e voti dei deputati XIII-XIX (XIII-XVI dalle schede HTML), iter dai lavori preparatori per X-XII. Entrambi scrivono su Neon solo se lanciati a mano con `scrivi_su_neon`; la Camera va caricata dopo il Senato. Senato (XIII-XIX) e Camera (X-XIX) sono su Neon dal 31/10/2026: database 368 MB su 1 GB del piano Free.
