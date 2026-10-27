# Revisione della documentazione — 27/10/2026

**Verdetto: sì, si può iniziare la Fase 1 (archivio).** I documenti sono coerenti su visione, stack, fonti e roadmap. Le lacune vere riguardano lo schema dati delle *schede* (Fase 2), quindi non bloccano l'avvio. Prima del primo commit servono però tre cose piccole (sezione A).

---

## A. Da sistemare prima di iniziare (bloccanti per la Fase 1)

1. **Manca il repository GitHub.** Non esiste ancora un repo `archivio-leggi` collegato. Va creato su GitHub da te (io non posso creare repository); appena esiste lo collego e preparo la struttura.
2. **Perimetro dei tipi di atto non definito.** "Leggi statali" non dice quali atti. La lista MVP contiene leggi, decreti legislativi e decreti legge. Proposta: legge, legge costituzionale, decreto legge, decreto legislativo. Esclusi DPR e regolamenti. Va scritto in `00_visione.md` e nel campo `legge.tipo`.
3. **Schema v1.1, piccoli ritocchi alla tabella `legge` e alle relazioni** (riguardano la pipeline Normattiva, quindi vanno fatti prima):
   - `data_entrata_vigore`: il metodo conta "almeno 3 anni dall'entrata in vigore", ma lo schema ha solo `data`. Esempio: Sirchia è del 2003, il divieto è in vigore dal 2005.
   - `governo`: serve per il bilanciamento del campione (`06_leggi_mvp.md`) e per i filtri nell'app. Basta una tabella `governo` (nome, inizio, fine) e l'assegnazione per data.
   - `relazione_normativa.tipo`: aggiungere `converte` (decreto legge → legge di conversione) e `delega` (legge delega → decreto legislativo). Senza, l'iter di un D.L. o D.Lgs. non si collega al Parlamento.
   - `legge.stato`: "modificata" non è uno stato che Normattiva restituisce, si ricava dalle relazioni. Proposta: `stato` = vigente / abrogata / decaduta (D.L. non convertito); "modificata" diventa un campo derivato (`numero_modifiche > 0`).

## B. Da sistemare prima della Fase 2 (schede), non bloccanti ora

4. **Schede su un singolo articolo.** Tre leggi MVP sono articoli (L. 3/2003 art. 51, D.L. 201/2011 art. 24, D.L. 34/2020 art. 119), ma `obiettivo`, `valutazione` e `verdetto` puntano all'intera legge. Proposta: una tabella `scheda` (id, urn, articolo opzionale, stato revisione) a cui agganciare obiettivi, valutazioni e verdetti.
5. **Un verdetto per obiettivo.** La scheda Sirchia dà due verdetti (obiettivo dichiarato e obiettivo secondario). Lo schema prevede un solo verdetto per legge. Serve `obiettivo_id` (opzionale) su `verdetto`, oppure un esito per obiettivo.
6. **Campi della scheda senza tabella.** "Altri fattori" (passo 5 del metodo) e "Letture alternative" non hanno un posto nello schema. `obiettivo` non distingue dichiarato e atteso.
7. **`obiettivo.tipo_fonte` troppo stretto.** Ammette solo relazione illustrativa, AIR o dossier, ma l'obiettivo secondario di Sirchia ha come fonte uno studio (Vuri 2016).
8. **`misura` è troppo rigida per i dati da studi.** Nella scheda ci sono intervalli ("da -4% a -13%"), intervalli di confidenza e variazioni percentuali senza valore assoluto. Servono `fonte_url` sulla misura o sull'indicatore e un campo `nota`.
9. **Dove vive la scheda?** Non è deciso se la fonte di verità è il file Markdown o il database, né come avviene l'approvazione umana (`approvato_da`). Proposta semplice: schede come file nel repo, approvazione = merge della pull request, import automatico nel DB. Va deciso prima della Fase 2.

## C. Incoerenze di metodo e fonti

10. **Fonti della scheda esempio vs regole.** Le regole del progetto ammettono Normattiva, GU, Camera, Senato, Istat, Banca d'Italia, Corte dei conti, UPB, AIR/VIR. La scheda Sirchia usa anche studi peer-reviewed (giusto, il metodo li valorizza) e stampa (Fortune Italia, Quotidiano Sanità, Il Post) anche per numeri, ad esempio asma -10/15% e fumatori 23,8%. Proposta: una gerarchia esplicita in `03_fonti.md`: (1) fonti ufficiali e dati, (2) studi peer-reviewed o working paper di istituti, (3) stampa solo per contesto, mai come unica fonte di un numero. Poi, alla revisione della scheda, sostituire i numeri presi dalla stampa con la fonte primaria.
11. **La scheda esempio non è ancora approvata** e lo stato della legge è "da verificare". Non blocca il codice, ma blocca l'uso della scheda come modello per le altre 29.
12. **Iter e votazioni.** I decreti legislativi non hanno un voto parlamentare (si vota la legge delega). Per le legislature più vecchie i dati di voto su dati.camera.it e dati.senato.it possono essere incompleti. `voti_favorevoli` e `voti_contrari` vanno resi opzionali.
13. **Strumenti di terzi da verificare.** `normattiva-sdk`, `it-eli-mcp` e `open-parlamento-mcp` sono client non ufficiali: il primo task deve verificare che esistano, funzionino e restituiscano cronologia, modifiche e abrogazioni. Se no, si usa direttamente l'API di dati.normattiva.it.

## D. Rischi (nessuna modifica proposta)

- **Doppio cold start**: Render Free si sospende dopo 15 minuti di inattività e Neon dopo 5. La prima visita può richiedere decine di secondi. Accettabile per l'MVP; da rivedere al primo deploy.
- **Dove gira la pipeline di aggiornamento**: non è deciso. Proposta: GitHub Actions con cron settimanale (gratis per repo pubblici).
- **Campione dal 1994**: il perimetro parte dal 1990, ma la prima legge MVP è del 1994. Va bene, ma conviene scriverlo come scelta.

---

## Primo task proposto

**Task 0.2 — Repository e verifica di Normattiva** (una sessione Claude Code)

1. Struttura del repo: `CLAUDE.md` (ruolo, regole, link ai documenti), `docs/` con i file 00–06, `ingest/` (progetto Python con `pyproject.toml`), `.github/workflows/` vuota.
2. Uno script di prova in `ingest/spike_normattiva.py` che scarica 10 atti (5 leggi MVP di tipo diverso: L. 3/2003, D.Lgs. 9/2002, D.L. 4/2019, L. 109/1994 abrogata, D.Lgs. 626/1994 abrogato) e salva in `ingest/samples/` cosa restituisce l'API: URN, tipo, date, stato, elenco delle modifiche e delle abrogazioni.
3. Un breve report in `docs/spike_normattiva.md`: quali campi dello schema si riempiono davvero, quali no, quanti atti ci sono dal 1990 per tipo (per stimare lo spazio su Neon).

- **Dipendenze**: Python 3.12, `httpx`, eventualmente `normattiva-sdk` se esiste.
- **Come testarlo**: lo script gira in locale senza database; un test `pytest` controlla che per ogni atto di prova ci siano URN, tipo e data.
- **Perché prima della pipeline**: lo schema v1.1 va confermato su dati veri, non su ipotesi.

Dopo lo spike: schema v1.1 definitivo, poi **Task 1.1 — Pipeline Normattiva → Postgres**.
