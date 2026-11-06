Data: 2026-10-29
Decisione: Frontend Next.js su Vercel (Hobby, regione `fra1`): i dati si leggono dal server di Next.js, con cache di un'ora sulle risposte dell'API; pagine di attesa con streaming mentre Render si sveglia (nuovi tentativi fino a 100 s); la home non chiama l'API e sveglia Render
Motivo: Niente CORS e meno richieste a Render e Neon (i dati cambiano al massimo una volta a settimana). Il primo accesso dopo 15 minuti di pausa aspetta circa un minuto: meglio dirlo che mostrare una pagina bianca
