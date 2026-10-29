# Revisione della scheda Sirchia (`04_scheda_esempio.md`)

Data: 29/10/2026. Confronto con `02_metodo_valutazione.md` e `03_fonti.md`, link e fatti verificati sul web.
Esito (29/10/2026, CAPO): proposte approvate, con due varianti dell'autore.
- Numeri senza fonte primaria: restano con l'asterisco e non contano per il verdetto (invece di toglierli).
- Obiettivo secondario: Parzialmente raggiunto, confidenza **Media-Alta**, con una regola nuova sui range in `02_metodo_valutazione.md`.

## In sintesi
- La scheda regge: obiettivo dichiarato, indicatori e verdetto principale sono coerenti con il metodo.
- Un problema di sostanza: sul fumo attivo la scheda dice che solo gli studi prima/dopo trovano un calo. Non è vero: due studi peer-reviewed con controfattuale (Health Policy 2013) trovano un calo piccolo ma significativo. Il verdetto sull'obiettivo secondario e le "letture alternative" vanno riscritti.
- Quattro numeri vengono dalla stampa o da una pagina che non cita la fonte. Per tre ho trovato la fonte primaria.
- Lo stato della legge va aggiornato: l'art. 51 è vigente ed è stato esteso più volte.

## A. Da decidere (CAPO)

### A1. Verdetto sull'obiettivo secondario (fumo attivo)
**Fatti**
- Vuri 2016 (FBK-IRVAPP, working paper, differenze-nelle-differenze): nessun effetto sulla popolazione, calo solo tra i giovani non sposati (-8,8% fumatori, -13,9% sigarette). — [link](https://irvapp.fbk.eu/wp-content/uploads/2017/09/FBK-IRVAPP-Working-Paper-No.-2016-06.pdf)
- Buonanno e Ranzani, *Health Policy* 2013 (esperimento quasi-naturale): prevalenza -1,3%, sigarette al giorno -8%. — [link](https://econpapers.repec.org/RePEc:eee:hepoli:v:109:y:2013:i:2:p:192-199)
- Pieroni et al., *Health Policy* 2013 (regression discontinuity e differenze-nelle-differenze, Istat "Aspetti della vita quotidiana" 2001-2007): effetto significativo su prevalenza e intensità. — [link](https://ideas.repec.org/a/eee/hepoli/v111y2013i2p116-126.html)

**Problema**
- Il conflitto non è "prima/dopo contro controfattuale": è tra studi controfattuali.
- La confidenza "Media" non segue il metodo: Media vuol dire "senza controfattuale", e qui i controfattuali ci sono.

**Opzioni**
1. *(consigliata)* **Parzialmente raggiunto, confidenza Media**, e una riga nuova nel metodo: "se gli studi controfattuali sono in conflitto, la confidenza scende di un livello". Motivazione: effetto piccolo (-1,3% di fumatori) o nullo secondo lo studio.
2. **Parzialmente raggiunto, confidenza Alta**, senza toccare il metodo: c'è un controfattuale, e tutti concordano che l'effetto è al massimo piccolo.
3. **Non raggiunto, confidenza Media**: dà più peso a Vuri. Sconsigliata, perché due studi su rivista trovano un effetto.

### A2. L'obiettivo secondario resta nella scheda?
- Il metodo dice: obiettivi dalla relazione illustrativa o dall'AIR. L'obiettivo secondario ha come fonte uno studio (Vuri 2016, introduzione: questi divieti "creano anche un ambiente che aiuta chi vuole smettere").
- La relazione illustrativa del testo che ha introdotto l'art. 51 non l'ho ancora trovata (la L. 3/2003 è un collegato ordinamentale sulla pubblica amministrazione).
- **Consiglio**: tenerlo, etichettato "atteso, non dichiarato", e cercare la relazione illustrativa negli atti di Camera e Senato. Serve aggiungere "studio" ai valori di `obiettivo.tipo_fonte` (punto 7 della revisione del 27/10).
- Alternativa: toglierlo e lasciare un solo verdetto.

### A3. Numeri presi dalla stampa
| Numero nella scheda | Fonte attuale | Cosa ho trovato | Proposta |
|---|---|---|---|
| Nicotina nell'aria -90/95% | CORDIS 2006, che non cita la fonte | Vuri 2016 lo attribuisce a Gorini et al. 2005, locali di **Firenze** | Citare Gorini et al. 2005 e scrivere "Firenze", non "Italia" |
| Infarti in età lavorativa da -4% a -13% (ISS) | Fortune Italia 2023, che non nomina lo studio ISS | Barone-Adesi 2011 (PLoS ONE, 20 regioni, 2002-2006): **-4% sotto i 70 anni** (RR 0,96, IC 0,95-0,98), nessun effetto sopra i 70 | Sostituire con il dato nazionale del 2011 |
| Asma -10/15% (SIAAIC) | Fortune Italia 2023 | Nessuno studio primario trovato | Togliere la riga, oppure "dato non disponibile" finché non si trova lo studio |
| Fumatori 24,2% nel 2022 | Fortune Italia, che non cita la fonte | [ISS-Doxa 2022](https://smettodifumare.iss.it/public-caf/Files/Fumo%20in%20Italia_2022.pdf): 24,2%, 15 anni e più, circa 22% nel 2019 | Citare ISS-Doxa e correggere "tra il 2020 e il 2022" in "dal 2019 al 2022" |
| Fumatori over 14: 23,8% (2003), poi 22-23% | Quotidiano Sanità (gennaio 2012), dati Istat senza indagine | Istat "Aspetti della vita quotidiana", da recuperare | Citare la tavola Istat (si può fare con la pipeline Istat) |

**Consiglio**: applicare tutta la colonna "Proposta". Così la scheda modello rispetta la regola "la stampa non è mai l'unica fonte di un numero".

## B. Correzioni senza decisione (le applico con il via)
1. **Stato della legge.** Oggi: "vigente, poi estesa (verificare)". Diventa: vigente, estesa da
   - D.L. 104/2013, art. 4: comma 1-bis, aree esterne di scuole e istituti di formazione;
   - [D.Lgs. 6/2016, art. 24](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.dataPubblicazioneGazzetta=2016-01-18&atto.codiceRedazionale=16G00009&atto.articolo.numero=24&atto.articolo.tipoArticolo=0): comma 1-bis esteso alle pertinenze esterne di ospedali e reparti pediatrici e di ostetricia; nuovo comma 1-ter, divieto in auto con minori o donne in gravidanza;
   - commi 10-bis-10-decies su pubblicità e controllo dei prodotti con nicotina: l'atto che li ha inseriti è **da confermare** (la pagina dell'art. 51 su Normattiva non si apre dal mio ambiente; si può leggere da `relazione_normativa` sul nostro database).
2. **Entrata in vigore del divieto (10/1/2005)**: aggiungere la fonte (Vuri 2016; CORDIS 2006).
3. **"Cosa prevede"**: nessuna fonte. Aggiungere il link all'art. 51 e al DPCM 23/12/2003 (requisiti delle sale fumatori).
4. **Violazioni 1,5% su circa 6.000 controlli**: la fonte primaria è Gallus et al. 2006, citato da Vuri. Citarla.
5. **"Trend dei fumatori già in calo tra gli uomini"**: senza fonte. Aggiungere la serie ISS-Doxa o Istat, o togliere la frase.
6. **Effetto sugli infarti**: oggi si cita solo il Piemonte (-11%). Aggiungere il dato nazionale (-4% sotto i 70 anni) nella sezione 5 e nella motivazione del verdetto. Il -11% è il rapporto tra tassi aggiustato (0,89); sui numeri grezzi (922 → 832) il calo è del 9,8%: scriverlo per evitare dubbi.
7. **Sezione 6**: aggiungere i due studi su *Health Policy* 2013.
8. **Il Post 2025**: è nell'elenco delle fonti ma non è usato nel testo, e riporta un 27,6% di fumatori nel 2003 diverso dagli altri. Toglierlo o usarlo solo come contesto.
9. **"Cosa insegna questa scheda"**: aggiungere "risalire sempre alla fonte primaria quando un numero arriva da stampa o divulgazione".

## C. Cosa regge senza cambi
- Identità: URN, data, governo Berlusconi II, ministro Sirchia. Il link uri-res di Normattiva va verificato da un browser normale (dal mio ambiente risponde con un errore).
- Barone-Adesi 2006: 922 → 832 ricoveri, RR 0,89 (IC 0,81-0,98), 0,7% spiegato dal fumo attivo, nessun effetto sopra i 60 anni. Tutto confermato. — [link](https://research.uniupo.it/en/publications/short-term-effects-of-italian-smoking-regulation-on-rates-of-hosp/)
- Vuri 2016: tab. 1 (27,7% → 25,3%), accise di dicembre 2004, conclusioni. Tutto confermato.
- Verdetto sull'obiettivo dichiarato: "Obiettivo raggiunto, confidenza Alta" rispetta la scala (indicatori nella direzione prevista, studi che lo attribuiscono alla legge, controllo della stagionalità e del trend nel 2011).
- Più di 3 anni dall'entrata in vigore: sì.
