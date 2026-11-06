Data: 2026-10-29
Decisione: Il controllo di salute di Render chiama `/`, non `/salute`
Motivo: `/salute` interroga il database: chiamato da Render ogni pochi secondi terrebbe sveglio il compute di Neon
