# Deploy del frontend

Il sito (`web/`, Next.js) gira su **Vercel**, piano Hobby (gratuito, solo per progetti personali e non
commerciali: è il nostro caso). Legge i dati dall'API su Render; il database non lo tocca mai.

## Come funziona
- Le pagine che mostrano dati (`/cerca`, `/legge/...`) sono generate sul server di Vercel, che chiama l'API.
  Il browser non chiama mai l'API direttamente: per questo **non serve CORS** e `CORS_ORIGINI` su Render
  può restare vuota.
- Ogni risposta dell'API resta in cache su Vercel per un'ora (i governi per un giorno). Due visitatori che
  aprono la stessa legge nella stessa ora fanno una sola richiesta a Render e a Neon.
- Render Free si spegne dopo 15 minuti senza richieste. Alla prima visita dopo una pausa la pagina mostra
  subito "L'archivio si sta svegliando…" e intanto il server di Vercel riprova l'API fino a 100 secondi.
  La home non chiama l'API: si apre subito e nel frattempo sveglia Render (chiamando `/`, che non tocca
  il database, quindi Neon resta sospeso).
- Le funzioni di Vercel girano a Francoforte (`web/vercel.json`, regione `fra1`), vicino a Render e Neon.

## Passi manuali (una volta sola)
1. Entra su [vercel.com](https://vercel.com) con **Continue with GitHub**. Scegli il piano **Hobby**.
2. **Add New → Project**. Vercel chiede di installare la sua app GitHub: basta il repository
   `PeppeMoscato/archivio-leggi`. Poi **Import** accanto al repository.
3. Nella schermata di configurazione:
   - **Root Directory**: premi **Edit** e scegli `web`. È il passo importante: il repository contiene anche
     la pipeline e l'API.
   - **Framework Preset**: Next.js (lo riconosce da solo). Comandi di build e cartella di output: lascia i
     valori proposti.
   - **Environment Variables**: nessuna è obbligatoria. Se l'indirizzo dell'API su Render non è
     `https://archivio-leggi-api.onrender.com`, aggiungi `API_URL` con l'indirizzo giusto (senza `/` finale).
4. **Deploy**. Dopo un paio di minuti il sito è su un indirizzo come `https://archivio-leggi.vercel.app`
   (se il nome è preso, Vercel aggiunge un suffisso). L'indirizzo si vede nella pagina del progetto, sotto
   **Domains**.
5. Controlla in **Settings → Functions** che **Fluid compute** sia attivo (lo è per i progetti nuovi): serve
   perché una pagina possa aspettare il risveglio di Render (fino a 120 secondi per pagina; il massimo
   del piano Hobby è 300).

Da quel momento ogni push su `main` pubblica il sito, e ogni pull request ha un'anteprima con il suo
indirizzo (lo scrive Vercel nella PR). Facoltativo: in **Settings → Build and Deployment** attiva
"Skip deployments when there are no changes to the root directory", così le PR che toccano solo la
pipeline o l'API non ricostruiscono il sito.

## Prova
1. Apri l'indirizzo di Vercel. La home deve aprirsi subito.
2. Cerca "L. 3/2003": la prima ricerca dopo una pausa può mostrare il messaggio di risveglio per circa un
   minuto, poi compare la legge. La ricerca successiva è immediata.
3. Apri la legge: stato, governo, Gazzetta, timeline delle modifiche e, se ci sono, iter e votazioni.

## Consumi da tenere d'occhio
Piano Hobby, al mese ([limiti](https://vercel.com/docs/plans/hobby), verificati il 29/10/2026):
1 milione di invocazioni di funzioni, 4 ore di CPU attiva (l'attesa dell'API non conta), 100 GB di
traffico. Se un limite si supera, la funzione si ferma fino a 30 giorni dopo: nessun addebito. I consumi
sono in **Usage** nella dashboard di Vercel. Per il traffico di un sito appena lanciato il limite più vicino
resta quello di Render e Neon, non quello di Vercel (vedi `docs/deploy_api.md`).
