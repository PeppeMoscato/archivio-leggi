# Maggioranza nel tempo: casi dubbi

Scelte fatte nella compilazione delle date di `ingest/archivio/governi_partiti.csv` (schema v1.6, PR #29) e accettate dall'autore l'8/11/2026 (decisione `docs/stato/decisioni/2026-11-08_02_rapporti-partiti-casi-dubbi-accettati.md`). Per ogni caso c'è la scelta in vigore (**ora**), e le alternative restano nella `nota` della riga del CSV. Un caso nuovo va aggiunto qui; cambiare una scelta richiede una decisione nuova.

Regole che questi casi applicano (commento di `ingest/archivio/governi.py`):
- "governo" = partito con almeno un ministro; "appoggio esterno" = fiducia senza ministri (viceministri e sottosegretari non bastano).
- L'uscita è il giorno delle dimissioni dei ministri secondo dati.camera.it. Se il partito non ha ministri, o la fonte data l'uscita prima delle dimissioni, vale la data della fonte e la differenza va nella `nota`.
- Hanno una riga nuova solo i partiti nati da una scissione o da una fusione di partiti già nella maggioranza, e quelli che entrano con ministri.

1. **Draghi.** Per M5S, Lega e FI non c'è una data di uscita, perché la fonte non riporta un'uscita dichiarata: il 14/7 e il 20/7/2022 i tre partiti non votano la fiducia, e i ministri di FI restano fino al 26/7. **Ora:** restano nella maggioranza fino alla fine del governo, con una nota che lo spiega. Un'alternativa possibile è un'uscita il 20/7 (voto di fiducia al Senato).
2. **Letta.** Forza Italia rinasce il 16/11/2013 ed esce il 26/11. Ha avuto un viceministro e alcuni sottosegretari, dimessi tra il 29/11 e il 6/12. **Ora:** "appoggio esterno" dal 16 al 26/11, perché non aveva ministri.
3. **Monti.** Il PdL annuncia l'uscita il 6/12/2012 ma il 20/12 vota la fiducia sulla legge di stabilità. **Ora:** esce il 6/12.
4. **Gentiloni.** Articolo Uno nasce il 25/2/2017 con un viceministro (Bubbico) ma senza ministri. Il 3/10/2017 annuncia il passaggio all'appoggio esterno, e la stessa pagina di Wikipedia fa finire quell'appoggio il 24/10. Bubbico si dimette il 9/11 secondo dati.camera.it. **Ora:** appoggio esterno dal 25/2 al 24/10; la nota riporta le altre date.
5. **Piccoli partiti entrati dopo il giuramento senza ministri.** Sono rimasti esclusi, per la regola del perimetro: CU nel Dini (14/6/1995), IdV nel Monti (fino al 16/12/2011), Italia di Mezzo nel Prodi II, IR e PT nel Berlusconi IV, MAIE nel Renzi e altri. Si possono aggiungere come "appoggio esterno" se vuoi.
6. **D'Alema I.** L'UDR si scioglie il 24/2/1999 in UDEUR, CDU e UpR, e la fonte non dice in quale di questi partiti siano andati i ministri. **Ora:** tutti e tre come "governo" dal 24/2. Per l'UpR l'uscita è il 25/7/1999 (dalla cronologia), anche se l'introduzione della stessa pagina la mette a dicembre 1999.
7. **Ciampi.** I ministri del PDS e dei Verdi sono rimasti in carica dal 28/4 al 4/5/1993. **Ora:** esclusi, come aveva deciso la regola del 30/10.
8. **Dimissioni dell'Andreotti VII.** Il riquadro della pagina di Wikipedia dice 24/4/1992, il testo della stessa pagina dice 28/4. **Ora:** 24/4.
9. **Italia Viva nel Conte II.** Il partito nasce il 18/9/2019, i suoi gruppi parlamentari il 19/9. **Ora:** 18/9.
10. **SDI nel Prodi II.** Il passaggio da SDI a Partito Socialista (ottobre 2007) non è rappresentato. **Ora:** resta SDI per tutto il governo.
