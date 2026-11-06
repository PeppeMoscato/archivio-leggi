# Stato del progetto e decisioni

Stato, decisioni, questioni aperte, roadmap e log del progetto stanno in `docs/stato/`, **un file per voce**.
Questo file non cambia a ogni sessione: spiega dove sono le cose e come si aggiornano.

Per leggere tutto in un solo documento, nel vecchio formato (fase attuale, tabella delle decisioni,
ancora da decidere, roadmap, log):

```bash
python docs/stato/componi.py                    # stampa il documento
python docs/stato/componi.py --uscita stato.md  # lo scrive in un file (per esempio per il Progetto Claude)
```

Il documento composto non si salva nel repository.

## Perché un file per voce
Fino al 06/11/2026 tutto stava in questo file. Ogni thread aggiungeva una riga in fondo alla tabella
delle decisioni e al log, e riscriveva la riga della fase attuale e la data dell'ultimo aggiornamento.
Due PR aperte in parallelo toccavano quindi sempre le stesse righe, e a ogni unione l'altra PR andava
in conflitto. Con un file per voce, due thread aggiungono file diversi e git li unisce da solo.
Un conflitto resta possibile solo se due thread cambiano la stessa voce (la stessa questione aperta o
la stessa voce di roadmap): in quel caso è un conflitto vero, da decidere.

## Dove sta cosa
| Cartella o file | Contenuto | Nome del file |
|---|---|---|
| `docs/stato/fase.md` | Fase attuale, una o due righe | — |
| `docs/stato/roadmap/` | Una voce di roadmap per file: fase, voce, fatto, nota, situazione dettagliata | `NN_parole-chiave.md` |
| `docs/stato/decisioni/` | Una decisione per file: data, decisione, motivo | `AAAA-MM-GG_NN_parole-chiave.md` |
| `docs/stato/aperte/` | Una questione ancora da decidere per file | `NN_parole-chiave.md` |
| `docs/stato/log/` | Una voce del log delle sessioni per file | `AAAA-MM-GG_NN_parole-chiave.md` |

`NN` è un numero di due cifre che dà l'ordine (per le decisioni e il log, l'ordine nella stessa
giornata). Si usa il numero successivo a quelli che si vedono nel proprio branch: se un altro thread
usa lo stesso numero non importa, perché le parole chiave rendono diverso il nome.
Le parole chiave sono minuscole, senza accenti, separate da `-` (per esempio `voti-camera-xiii-xvi`).

## Formato dei file
Ogni file è fatto di righe `Campo: valore`. Un valore può continuare sulle righe successive, finché
non comincia un altro campo (tranne `Decisione` e `Motivo`, che finiscono in una tabella e restano su una riga).

Decisione (`decisioni/2026-10-29_06_api-render-piano-free-render-yaml.md`):
```
Data: 2026-10-29
Decisione: API su Render, piano Free (`render.yaml`), non Fly.io
Motivo: Fly.io non ha più un piano gratuito per i nuovi account ...
```

Voce di roadmap (`roadmap/09_aggiornamento-settimanale-incrementale-pipeline.md`):
```
Fase: Fase 1 — Archivio
Voce: Aggiornamento settimanale incrementale della pipeline
Fatto: no
Nota: PR #18 in revisione
Situazione: testo più lungo che compare sotto "Fase attuale" (facoltativo)
```
`Fatto` vale `sì` o `no`; `Nota` e `Situazione` sono facoltativi.

Questione aperta (`aperte/08_licenza-codice-repository.md`):
```
Questione: Licenza del codice del repository.
```

Voce del log (`log/2026-11-01_01_conversioni-sbagliate-rimaste-secondo-giro-pipeline.md`):
```
Data: 2026-11-01
Testo: conversioni sbagliate rimaste. ...
```
La `Data` comincia con la data del nome del file; può proseguire (per esempio `2026-10-30/31`).

## Come si aggiorna, a fine sessione
1. **Decisione nuova**: un file nuovo in `decisioni/`. Le decisioni degli altri non si toccano.
   Se una decisione ne cambia una vecchia, il file nuovo la cita nel `Motivo` e la vecchia resta come storico.
2. **Log**: un file nuovo in `log/` per la sessione (o per ogni risultato importante). Le voci vecchie non si cambiano.
3. **Questioni aperte**: una nuova è un file nuovo; se cambia si modifica solo il suo file; quando è
   decisa si cancella il file e si aggiunge la decisione.
4. **Roadmap**: si modifica solo il file della voce su cui si è lavorato (`Fatto`, `Nota`, `Situazione`);
   una voce nuova è un file nuovo.
5. **Fase**: `fase.md` cambia solo quando cambia la fase del progetto.
6. Prima del commit: `python docs/stato/componi.py --controlla` (gira anche nella CI, job `documenti`).

Se una PR aperta prima di questa struttura modifica ancora questo file, al prossimo aggiornamento del
branch va in conflitto un'ultima volta: si tiene questa versione del file e si riportano le sue righe
nuove come file in `docs/stato/` (decisioni, log, voci di roadmap e questioni aperte).
