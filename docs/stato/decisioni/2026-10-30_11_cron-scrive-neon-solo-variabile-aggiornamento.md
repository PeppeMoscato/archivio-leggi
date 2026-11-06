Data: 2026-10-30
Decisione: Il cron scrive su Neon solo con la variabile del repository `AGGIORNAMENTO_SU_NEON` = `true`; a mano solo con `scrivi_su_neon`. Altrimenti carica in un Postgres temporaneo. Non va lanciato mentre gira una pipeline completa su Neon
Motivo: Niente scritture su Neon senza il via dell'autore, e non durante i caricamenti completi (Camera in corso, poi Normattiva da rilanciare)
