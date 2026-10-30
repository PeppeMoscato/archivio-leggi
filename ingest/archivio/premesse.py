"""Premesse del testo originale di un atto: perché il governo dice di averlo adottato.

Forme reali, osservate con la sonda del 29/10/2026 (`sonda_contesto.py`, D.L. 223/2006):
- `preamble-citation-akn`: "Visti gli articoli 77 e 87 della Costituzione;",
  "Vista la deliberazione del Consiglio dei Ministri, adottata nella riunione del 30 giugno 2006;"
- `preamble-text-akn`: "Ritenuta la straordinaria necessità ed urgenza di rafforzare la libera scelta
  dei consumatori ...;" e "Sulla proposta del Presidente del Consiglio dei Ministri, ...;"
- `preamble-end-akn` ("Emana", "Promulga") chiude la premessa.

`normattiva-sdk` 0.1.0 tiene solo la formula ("IL PRESIDENTE DELLA REPUBBLICA ... Emana"):
le citazioni e le motivazioni si leggono qui dall'HTML. Le leggi ordinarie non hanno
premesse utili ("La Camera dei deputati ed il Senato della Repubblica hanno approvato").
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

CITAZIONE = "preamble-citation-akn"
TESTO = "preamble-text-akn"
FINE = "preamble-end-akn"
ARTICOLO = "article-num-akn"

_MOTIVAZIONE = re.compile(r"^ritenut[aoie]\b", re.I)
_PROPOSTA = re.compile(r"^sulla\s+proposta\b", re.I)
# Citazioni che indicano la legge delega di un decreto legislativo. Prova 2006 (Pipeline premesse, 30/10/2026):
# con il solo "deleg" 33 D.Lgs. su 73; mancavano le leggi comunitarie ("Vista la legge 18 aprile 2005, n. 62,
# ... Legge comunitaria 2004"), i correttivi ("che consente di apportare disposizioni integrative e correttive")
# e le deleghe citate per articolo ("Visto l'articolo 10 della legge 29 luglio 2003, n. 229").
_DELEGA = re.compile(r"\bdeleg|comunitari|delegazione europea|appartenenza dell.italia|correttiv|integrativ", re.I)
_PER_ARTICOLO = re.compile(r"\bin particolare\b|^vist[oi] (l'|gli )articol", re.I)
_ART_76 = re.compile(r"\b76\b.*costituzione", re.I)  # "Visti gli articoli 76 e 87 della Costituzione"
# Leggi generali sui decreti legislativi e sugli obblighi europei: citate quasi sempre, non sono la delega.
LEGGI_GENERALI = frozenset({
    ("1988", "400"),  # disciplina dell'attività di governo (art. 14: i decreti legislativi)
    ("2005", "11"),  # partecipazione al processo normativo dell'Unione europea
    ("2012", "234"),  # partecipazione alla formazione e all'attuazione del diritto dell'Unione europea
})
_LEGGE = re.compile(r"^urn:nir:stato:legge:(\d{4})(?:-\d\d-\d\d)?;(\d+)")
_URN = re.compile(r"(urn:nir:[^~#\"'\s&]+)(?:~art(\w+))?")
_SPAZI = re.compile(r"\s+")
_VUOTI = frozenset({"br", "img", "hr", "input", "meta", "link", "col", "wbr"})


@dataclass
class Delega:
    urn: str  # la legge citata, senza articolo
    articolo: str | None  # "1", "14bis": dal link (~art1-com7), quando c'è
    citazione: str  # la frase della premessa, da cui si verifica


@dataclass
class Premessa:
    citazioni: list[str] = field(default_factory=list)  # "Visto ...", "Vista la deliberazione ...", "Acquisito il parere ..."
    motivazioni: list[str] = field(default_factory=list)  # "Ritenuta la straordinaria necessità ed urgenza di ..."
    proposta: str | None = None  # "Sulla proposta del Presidente del Consiglio dei Ministri ..."
    deleghe: list[Delega] = field(default_factory=list)  # leggi citate in una premessa che parla di delega

    @property
    def vuota(self) -> bool:
        return not (self.citazioni or self.motivazioni or self.proposta)


class _Lettore(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocchi: list[tuple[str, str, list[tuple[str, str]]]] = []  # (classe, testo, (urn, articolo) dei link)
        self._aperto: tuple[str, int] | None = None  # classe del blocco e profondità a cui si chiude
        self._profondita = 0
        self._testo: list[str] = []
        self._link: list[tuple[str, str]] = []
        self.finita = False

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        pass  # <br/>: nessun testo e nessun livello in più

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _VUOTI:
            return
        self._profondita += 1
        if self.finita:
            return
        classi = set((dict(attrs).get("class") or "").split())
        if classi & {FINE, ARTICOLO}:
            self.finita = True
            return
        if self._aperto is None and classi & {CITAZIONE, TESTO}:
            self._aperto = (CITAZIONE if CITAZIONE in classi else TESTO, self._profondita)
            self._testo, self._link = [], []
        elif self._aperto and tag == "a" and (href := dict(attrs).get("href")):
            self._link += _URN.findall(html.unescape(href))

    def handle_endtag(self, tag: str) -> None:
        if tag in _VUOTI:
            return
        if self._aperto and self._profondita == self._aperto[1]:
            testo = _SPAZI.sub(" ", "".join(self._testo)).strip()
            if testo:
                self.blocchi.append((self._aperto[0], testo, self._link))
            self._aperto = None
        self._profondita -= 1

    def handle_data(self, data: str) -> None:
        if self._aperto and not self.finita:
            self._testo.append(data)


def premessa_da_html(testo_html: str) -> Premessa:
    """Le parti della premessa, nell'ordine del testo. Vuota se l'atto non ne ha."""
    lettore = _Lettore()
    lettore.feed(testo_html)
    premessa = Premessa()
    for classe, testo, link in lettore.blocchi:
        if classe == TESTO and _MOTIVAZIONE.match(testo):
            premessa.motivazioni.append(testo)
        elif classe == TESTO and _PROPOSTA.match(testo) and premessa.proposta is None:
            premessa.proposta = testo
        else:
            premessa.citazioni.append(testo)
    premessa.deleghe = _deleghe(lettore.blocchi)
    return premessa


def _deleghe(blocchi: list[tuple[str, str, list[tuple[str, str]]]]) -> list[Delega]:
    """Le leggi delega citate. Per ogni citazione conta la prima legge: "Vista la legge 10 dicembre 2014,
    n. 183, recante deleghe al Governo ..., e in particolare l'articolo 1, comma 7, come modificato dalla
    legge ..." → la 183/2014. Senza una citazione esplicita, e solo se l'atto cita l'art. 76 della
    Costituzione, la prima legge citata per articolo ("Vista la legge ..., ed in particolare l'articolo 1")."""
    citazioni = []
    for classe, testo, link in blocchi:
        legge = next(((urn, articolo) for urn, articolo in link if (chiave := chiave_legge(urn))
                      and chiave not in LEGGI_GENERALI), None)
        if classe == CITAZIONE and legge:
            citazioni.append((testo, legge))
    scelte = [(testo, legge) for testo, legge in citazioni if _DELEGA.search(testo)]
    if not scelte and any(_ART_76.search(testo) for classe, testo, _ in blocchi if classe == CITAZIONE):
        scelte = [(testo, legge) for testo, legge in citazioni if _PER_ARTICOLO.search(testo)][:1]
    deleghe: dict[tuple[str, str], Delega] = {}
    for testo, (urn, articolo) in scelte:
        # "della citata legge n. 150 del 2005" ha un URN senza giorno (legge:2005;150): è la stessa legge
        # della citazione prima, si tiene quella.
        deleghe.setdefault(chiave_legge(urn), Delega(urn, articolo or None, testo))
    return list(deleghe.values())


def chiave_legge(urn: str) -> tuple[str, str] | None:
    """(anno, numero) di una legge: `urn:nir:stato:legge:2005-07-25;150` e `urn:nir:stato:legge:2005;150`."""
    trovata = _LEGGE.match(urn)
    return trovata.groups() if trovata else None
