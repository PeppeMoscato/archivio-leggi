Data: 2026-10-28
Decisione: API in sola lettura: `GET /leggi` (ricerca), `/leggi/{urn}` (dettaglio con governo e conteggi), `/leggi/{urn}/relazioni`, `/pronunce`, `/iter`, `/votazioni`, `/governi`, `/salute`
Motivo: Le liste lunghe (relazioni, votazioni) hanno endpoint propri e paginati: una legge come la 241/1990 riceve centinaia di modifiche, una legge di bilancio centinaia di votazioni. L'URN intero sta nel percorso (non contiene `/`)
