Data: 2026-10-27
Decisione: Database: Neon (piano Free) invece di Supabase
Motivo: Postgres puro (servono solo i dati, FastAPI è a parte). Free: 1 GB per progetto (da ottobre 2026), 100 CU-ore al mese, il compute si sospende dopo 5 minuti e si riattiva alla prima richiesta. Supabase Free mette in pausa il progetto dopo 7 giorni di inattività (500 MB): scomodo per un sito con poco traffico all'inizio
