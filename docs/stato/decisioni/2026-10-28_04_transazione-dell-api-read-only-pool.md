Data: 2026-10-28
Decisione: Ogni transazione dell'API è `READ ONLY`; pool che parte vuoto e chiude le connessioni ferme da un minuto
Motivo: Le scritture sono solo delle pipeline. Connessioni sempre aperte terrebbero sveglio il compute di Neon e consumerebbero le 100 CU-ore al mese del piano Free
