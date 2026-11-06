Fase: Fase 1 — Archivio
Voce: Ingestione iter da Camera e Senato (SPARQL)
Fatto: no
Nota: Task 1.2: Senato unito (PR #4), Camera in revisione (PR #5); caricamento su Neon da fare
Situazione: Task 1.2, parte Senato, unita (PR #4): pipeline dati.senato.it → Postgres (`ingest/archivio/senato.py`, `parlamento.py`), workflow "Pipeline Senato", che scrive su Neon solo se lanciato a mano con `scrivi_su_neon`. Task 1.2, parte Camera, in revisione (PR #5): pipeline dati.camera.it → Postgres (`ingest/archivio/camera.py`), workflow "Pipeline Camera"; votazioni e voti dei deputati XIII-XIX (XIII-XVI dalle schede HTML), iter dai lavori preparatori per X-XII. Tutto sta nel piano Free di Neon (Camera circa 215 MB). Prossimi passi: unire la PR #5, poi, con il via libera dell'autore, lanciare su Neon la Pipeline Senato (legislature `13-19`) e dopo la Pipeline Camera (`10-19`, una legislatura alla volta); i partiti dei governi sono compilati (`ingest/archivio/governi_partiti.csv`).
