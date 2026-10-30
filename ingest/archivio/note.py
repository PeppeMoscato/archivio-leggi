"""Classificazione delle note di aggiornamento di Normattiva.

Forme reali, osservate con la sonda del 27/10/2026 (leggi 2003, D.L. 1995):
- "ha disposto (con l'art. 2268, comma 1) l'abrogazione dell'intero provvedimento." → abroga
- "ha disposto (con l'art. 11, comma 5, lettera c)) l'abrogazione del comma 14 dell'art. 10." → abroga_parziale
- "ha disposto (con l'art. 12, comma 1) la modifica dell'art. 26, comma 1." → modifica
- ", di conversione, ha disposto (con l'art. 1, comma 1) l'introduzione dell'art. 4-sexies." → modifica
- "ha disposto (con l'art. 1, comma 1) la conversione, con modificazioni, del D.L. ..." → converte
- ", convertito con modificazioni dalla L. ... ha confermato (con l'art. 24) l'abrogazione dell'intero provvedimento." → abroga
- "ha disposto (con l'art. 24, comma 1) la modifica dell'art. 51, comma 1-bis; (con l'art. 24, comma 2) l'introduzione ..."
  → più azioni nella stessa nota: una classificazione per azione
- "ha dichiarato l'illegittimita' costituzionale dell'art. 10, comma 6." → pronuncia della Consulta
- "... che "Le disposizioni ... si applicano dalla data di entrata in vigore della legge di conversione del
  presente decreto"." → modifica: "conversione" in una citazione non è una conversione (errore visto sulla
  L. 241/1990, 30/10/2026)

La nota non nomina l'atto che dispone (lo identificano i riferimenti in
Gazzetta). Il tipo si ricava solo dal testo: ogni relazione conserva la nota
originale, così una classificazione sbagliata si può sempre verificare.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

PRONUNCIA = "pronuncia"

_VERBO = re.compile(r"\bha\s+(?:conseguentemente\s+)?(?:disposto|confermato)\b", re.I)
_DICHIARATO = re.compile(r"\bha\s+dichiarato\b.*?illegittimit\S*\s+costituzionale\s*(?P<oggetto>.*)", re.I)
_SENTENZA = re.compile(r"sentenza\b.{0,60}?\bn\.\s*(?P<numero>\d+)", re.I)
_ANNO_SENTENZA = re.compile(r"sentenza\b.{0,40}?(?P<anno>(?:19|20)\d{2})", re.I)
# L'azione è una conversione solo se comincia così: "la conversione, con modificazioni, del D.L. ...".
# Altrove la parola compare nelle citazioni ("dalla legge di conversione del presente decreto") o è
# un'altra conversione ("la conversione in euro degli importi", sul D.Lgs. 504/1995 nella prova del 1995).
_CONVERSIONE = re.compile(
    r"^(?:la\s+)?conversione\b(?:\s+in\s+legge)?\W*(?:(?:con|senza)\s+modificazioni\W*)?"
    r"(?:del|dello)\s+(?:d\.\s*l\.|decreto|presente\s+decreto)",
    re.I,
)
_INTERO = re.compile(r"\bintero\s+provvedimento\b|\bdel\s+provvedimento\b|\bdel\s+presente\s+(?:decreto|atto)\b", re.I)
_AZIONE = re.compile(r"^(?:la|l'|il|lo|i|gli|le)?\s*[a-zàèéìòù]+\s*", re.I)
_PREPOSIZIONE = re.compile(r"^(?:dell'|dello|della|delle|degli|dei|del|di)\s*", re.I)
_CON = re.compile(r"^con\s+(?:l'|il|lo|la|gli|i|le)?\s*", re.I)
_SEPARATORE = re.compile(r";\s*(?=\(con\b)", re.I)
_CLAUSOLA = re.compile(
    r"^\s*\((?P<origine>con\b.*?)(?P<chiuse>\)+)\s*(?P<azione>(?:l'|la\s|il\s|lo\s|le\s|gli\s|i\s|un\s|una\s).*)$",
    re.I | re.S,
)


@dataclass(frozen=True)
class Classificazione:
    tipo: str
    articolo_origine: str | None = None
    articolo_destinazione: str | None = None
    numero_sentenza: str | None = None
    anno_sentenza: int | None = None


def normalizza(testo: str) -> str:
    """Spazi uniformi e apostrofi tipografici resi semplici."""
    testo = unicodedata.normalize("NFC", testo).replace("’", "'").replace("`", "'")
    testo = re.sub(r"\b(l|dell|all|nell|dall|sull)'\s+", r"\1'", testo, flags=re.I)  # "dell' intero" → "dell'intero"
    return " ".join(testo.split())


def _pulisci(testo: str) -> str | None:
    testo = testo.strip(" .;,")
    return testo or None


def oggetto(azione: str) -> str | None:
    """Su cosa agisce l'azione: "la modifica dell'art. 26, comma 1." → "art. 26, comma 1"."""
    if _INTERO.search(azione):
        return None
    resto = _AZIONE.sub("", azione.strip(), count=1)
    return _pulisci(_PREPOSIZIONE.sub("", resto, count=1))


def tipo_di(azione: str) -> str:
    azione = azione.lower()
    if _CONVERSIONE.match(azione.strip()):
        return "converte"
    if "abrogazione" in azione:
        return "abroga" if _INTERO.search(azione) else "abroga_parziale"
    if "proroga" in azione or "differimento" in azione:
        return "proroga"
    return "modifica"


def _clausole(corpo: str) -> list[tuple[str | None, str]]:
    """Divide "(con l'art. 1) la modifica ...; (con l'art. 2) l'introduzione ..." in coppie (origine, azione).

    L'origine finisce alla parentesi chiusa seguita dall'articolo dell'azione
    ("la", "l'", "il", ...): non si possono contare le parentesi, perché
    "lettera c)" ne chiude una che non ha aperto.
    """
    clausole = []
    for pezzo in _SEPARATORE.split(corpo):
        trovato = _CLAUSOLA.match(pezzo)
        if trovato is None:
            if pezzo.strip(" .;"):
                clausole.append((None, pezzo.strip()))
            continue
        origine = _CON.sub("", trovato.group("origine")) + ")" * (len(trovato.group("chiuse")) - 1)
        clausole.append((_pulisci(origine), trovato.group("azione").strip()))
    return clausole


def classifica(testo: str) -> list[Classificazione]:
    """Una classificazione per ogni azione descritta nella nota (almeno una)."""
    testo = normalizza(testo)
    dichiarato = _DICHIARATO.search(testo)
    if dichiarato:
        sentenza = _SENTENZA.search(testo)
        anno = _ANNO_SENTENZA.search(testo)
        return [
            Classificazione(
                PRONUNCIA,
                articolo_destinazione=_pulisci(_PREPOSIZIONE.sub("", dichiarato.group("oggetto"), count=1)),
                numero_sentenza=sentenza.group("numero") if sentenza else None,
                anno_sentenza=int(anno.group("anno")) if anno else None,
            )
        ]
    verbo = _VERBO.search(testo)
    corpo = testo[verbo.end() :] if verbo else testo
    clausole = _clausole(corpo) or [(None, corpo)]
    return [
        Classificazione(
            tipo_di(azione),
            articolo_origine=origine,
            articolo_destinazione=None if tipo_di(azione) == "converte" else oggetto(azione),
        )
        for origine, azione in clausole
    ]


def nomina_conversione(testo: str) -> bool:
    """La nota nomina una conversione dopo il verbo: fino al 30/10/2026 bastava per farne una `converte`."""
    testo = normalizza(testo)
    if _DICHIARATO.search(testo):
        return False
    verbo = _VERBO.search(testo)
    corpo = testo[verbo.end() :] if verbo else testo
    return "conversione" in corpo.lower()
