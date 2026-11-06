Data: 2026-10-27
Decisione: Pipeline in due fasi: `estrai` (un job per anno, catalogo dalla ricerca avanzata + storia dall'export multivigente JSON) e `carica` (un job unico)
Motivo: Gli export annuali sono lenti e indipendenti, quindi vanno in parallelo; il caricamento ha bisogno del catalogo completo per risolvere i riferimenti in Gazzetta senza chiamare l'API
