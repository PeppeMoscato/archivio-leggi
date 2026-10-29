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
_DELEGA = re.compile(r"\bdeleg", re.I)
_URN = re.compile(r"(urn:nir:[^~#\"'\s&]+)")
_SPAZI = re.compile(r"\s+")
_VUOTI = frozenset({"br", "img", "hr", "input", "meta", "link", "col", "wbr"})


@dataclass
class Premessa:
    citazioni: list[str] = field(default_factory=list)  # "Visto ...", "Vista la deliberazione ...", "Acquisito il parere ..."
    motivazioni: list[str] = field(default_factory=list)  # "Ritenuta la straordinaria necessità ed urgenza di ..."
    proposta: str | None = None  # "Sulla proposta del Presidente del Consiglio dei Ministri ..."
    urn_delega: list[str] = field(default_factory=list)  # atti citati in una premessa che parla di delega

    @property
    def vuota(self) -> bool:
        return not (self.citazioni or self.motivazioni or self.proposta)


class _Lettore(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocchi: list[tuple[str, str, list[str]]] = []  # (classe, testo, urn dei link)
        self._aperto: tuple[str, int] | None = None  # classe del blocco e profondità a cui si chiude
        self._profondita = 0
        self._testo: list[str] = []
        self._link: list[str] = []
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
        if _DELEGA.search(testo):
            premessa.urn_delega += [urn for urn in link if urn.startswith("urn:nir:stato:legge") and urn not in premessa.urn_delega]
    return premessa
