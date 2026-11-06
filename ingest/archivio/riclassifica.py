"""Riclassifica le relazioni `converte` già nel database con la regola del 30/10/2026 (PR #16).

Il caricamento le riscrive per ogni atto che ricarica, ma non per gli atti con l'export incompleto,
che restano come erano (69 nel giro del 1/11/2026, tra cui il D.Lgs. 385/1993 e il D.Lgs. 58/1998):
le loro relazioni vengono dal caricamento del 27/10/2026, quando bastava la parola "conversione" nell'azione.
Qui si rilegge la nota salvata con ogni relazione e si applica la regola nuova, senza chiamare Normattiva:

- la nota è il titolo di una legge che converte proprio quel D.L. (relazione dal titolo): resta `converte`;
- altrimenti si cerca la clausola della nota che la regola vecchia leggeva come conversione; resta `converte`
  solo se comincia con "la conversione ... del D.L." e nomina il D.L. di destinazione, altrimenti prende il
  tipo che le darebbe la pipeline di oggi (di solito `modifica`), con l'articolo modificato.

Di default non scrive: conta e mostra degli esempi. Con `scrivi=True` aggiorna `tipo` e `articolo_destinazione`.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field

import psycopg

from archivio.note import _VERBO, _clausole, normalizza, oggetto, tipo_di
from archivio.relazioni import convertito_dal_titolo, convertito_dalla_nota

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Correzione:
    tipo: str
    articolo_destinazione: str | None


def correzione(nota: str, articolo_origine: str | None, urn_destinazione: str, tipo_destinazione: str) -> Correzione | None:
    """Il tipo giusto per una relazione `converte` già salvata; None se è giusta così."""
    if convertito_dal_titolo(nota) == urn_destinazione:
        return None
    testo = normalizza(nota)
    verbo = _VERBO.search(testo)
    corpo = testo[verbo.end() :] if verbo else testo
    clausole = _clausole(corpo) or [(None, corpo)]
    # La regola vecchia: "conversione" nell'azione. Con più clausole, quella dello stesso articolo di origine.
    vecchie = [c for c in clausole if "conversione" in c[1].lower()] or clausole
    _, azione = next((c for c in vecchie if articolo_origine and c[0] == articolo_origine), vecchie[0])
    tipo = tipo_di(azione)
    if tipo != "converte":
        return Correzione(tipo, oggetto(azione))  # come in note.classifica
    if tipo_destinazione != "decreto-legge" or convertito_dalla_nota(nota) not in (None, urn_destinazione):
        return Correzione("modifica", None)  # come in relazioni.relazioni_di, senza articolo
    return None


@dataclass
class Esito:
    controllate: int = 0
    corrette: Counter = field(default_factory=Counter)  # nuovo tipo → quante
    per_destinazione: Counter = field(default_factory=Counter)  # tipo dell'atto di destinazione → quante
    esempi: list[str] = field(default_factory=list)
    decreti_senza_conversione: list[str] = field(default_factory=list)

    def testo(self, scritto: bool) -> str:
        righe = [
            f"Relazioni `converte` controllate: {self.controllate}",
            f"Da correggere: {sum(self.corrette.values())} "
            + (f"({', '.join(f'{t} {n}' for t, n in self.corrette.most_common())})" if self.corrette else ""),
            "- per tipo dell'atto di destinazione: "
            + (", ".join(f"{t} {n}" for t, n in self.per_destinazione.most_common()) or "nessuna"),
            f"- D.L. che restano senza alcuna `converte` (lo stato va ricontrollato): {len(self.decreti_senza_conversione)}"
            + (f" ({', '.join(self.decreti_senza_conversione[:10])}{', ...' if len(self.decreti_senza_conversione) > 10 else ''})"
               if self.decreti_senza_conversione else ""),
            "Scritte nel database." if scritto else "Solo lettura: nessuna modifica scritta.",
        ]
        if self.esempi:
            righe += ["", "Esempi:"] + [f"- {e}" for e in self.esempi]
        return "\n".join(righe) + "\n"


def riclassifica(conn: psycopg.Connection, scrivi: bool = False, esempi: int = 10) -> Esito:
    esito = Esito()
    with conn.cursor() as cur:
        if not scrivi:
            cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(
            """
            SELECT r.id, r.urn_destinazione, l.tipo, r.nota, r.articolo_origine
            FROM relazione_normativa r JOIN legge l ON l.urn = r.urn_destinazione
            WHERE r.tipo = 'converte'
            ORDER BY r.id
            """
        )
        righe = cur.fetchall()
        aggiornamenti = []
        restano: set[str] = set()
        decreti_corretti: set[str] = set()
        for id_, urn, tipo_dest, nota, articolo_origine in righe:
            esito.controllate += 1
            nuova = correzione(nota, articolo_origine, urn, tipo_dest)
            if nuova is None:
                restano.add(urn)
                continue
            esito.corrette[nuova.tipo] += 1
            esito.per_destinazione[tipo_dest] += 1
            if tipo_dest == "decreto-legge":
                decreti_corretti.add(urn)
            aggiornamenti.append((nuova.tipo, nuova.articolo_destinazione, id_))
            if len(esito.esempi) < esempi:
                esito.esempi.append(f"{urn} → {nuova.tipo}: {' '.join(nota.split())[:200]}")
        esito.decreti_senza_conversione = sorted(decreti_corretti - restano)
        if scrivi and aggiornamenti:
            cur.executemany(
                "UPDATE relazione_normativa SET tipo = %s, articolo_destinazione = %s WHERE id = %s", aggiornamenti
            )
    if scrivi:
        conn.commit()
    else:
        conn.rollback()
    return esito
