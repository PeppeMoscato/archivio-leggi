"""Estrazione da dati.camera.it (Task 1.2, parte Camera): votazioni con i voti dei deputati, iter 1990-1996, deputati e gruppi.

Cosa prende e perché (`docs/sonda_parlamento.md`):
- Legislature XIII-XIX (dal 1996): le votazioni d'Aula della Camera sui ddl
  diventati legge, con il voto di ogni deputato. Gli iter li dà già il Senato,
  con le letture alla Camera: le votazioni si collegano a quelle fasi per
  numero (`C.2122-BIS`). L'elenco delle fasi Camera degli iter diventati legge
  si chiede al Senato, così si scaricano solo i voti che servono.
- Legislature X-XII (1987-1996): il Senato non ha dati e la Camera non ha
  votazioni, ma ha le leggi (`ocd:legge`, con l'URN di Normattiva) e i loro
  lavori preparatori alla Camera: da lì iter, fasi, iniziativa e firmatari.
- Deputati e gruppi dalla X legislatura: per i voti e per i firmatari.

L'endpoint è un Virtuoso come quello del Senato: risposte troncate a 10.000
righe e niente OFFSET grandi, quindi si scorre per chiave (`senato.scorri`).
Ogni tripla compare due volte (due grafi): tutte le query sono DISTINCT.
"""

from __future__ import annotations

import html
import json
import logging
import re
import time
import unicodedata
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from archivio import senato
from archivio.senato import _intero, _json, numero_ddl_da_etichetta, numero_senza_ramo, scorri
from archivio.sparql import Sparql

logger = logging.getLogger(__name__)

ENDPOINT = "https://dati.camera.it/sparql"
PREFISSI = """PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""
LEGISLATURE = range(10, 20)  # dalla X (1987): le leggi dal 1990
PRIMA_CON_VOTI = 13  # la Camera ha votazioni nominali dalla XIII; il Senato ha gli iter dalla XIII
# Il voto di ogni deputato (ocd:voto) c'è solo dalla XVII: per XIII-XVI l'endpoint ha esiti e totali ma nessun voto
# individuale (sonda camera-voti del 29/10/2026). I nomi sono nelle schede HTML di documenti.camera.it (dc:relation).
PRIMA_CON_VOTI_INDIVIDUALI = 17
SCHEDA = "https://documenti.camera.it/votazioni/votazionitutte/schedavotazione.asp?Legislatura={romano}&RifVotazione={rif}&tipo=dettaglio"
SCHEDE_IN_PARALLELO = 3  # pagine scaricate insieme: un sito HTML, non un servizio dati
PAUSA_SCHEDA = 0.5  # secondi di pausa di ogni lettore dopo una pagina
INIZIO_PERIMETRO = date(1990, 1, 1)
VOTAZIONI_PER_RICHIESTA = 14  # 14 × 630 deputati al massimo: sotto il limite di 10.000 righe
ATTI_PER_RICHIESTA = 40

ATTO = "http://dati.camera.it/ocd/attocamera.rdf/"
VOTAZIONE = "http://dati.camera.it/ocd/votazione.rdf/"
GRUPPO = "http://dati.camera.it/ocd/gruppoParlamentare.rdf/"
LEGGE = "http://dati.camera.it/ocd/legge.rdf/"
PERSONA = "http://dati.camera.it/ocd/persona.rdf/p"
VOTI = {"Favorevole": "favorevoli", "Contrario": "contrari", "Astensione": "astenuti"}


def legislatura_iri(numero: int) -> str:
    return f"http://dati.camera.it/ocd/legislatura.rdf/repubblica_{numero:02d}"


# --- Modelli intermedi (JSON fra estrazione e caricamento) ---------------------


@dataclass
class LeggeCamera:
    id: str  # IRI
    urn: str | None  # dall'ocd:lex, il permalink di Normattiva
    numero: int | None
    data: date | None
    titolo: str
    tipo: str | None  # Ordinaria / Costituzionale
    atti: list[str] = field(default_factory=list)  # IRI degli atti Camera dei lavori preparatori


@dataclass
class AttoCamera:
    id: str  # IRI
    numero: str  # "2122-BIS", dall'IRI
    titolo: str | None
    data: date | None  # presentazione
    iniziativa: str | None  # testo della fonte: Governo, Parlamentare, ...
    primo_firmatario: str | None  # identificativo della persona
    scheda: str | None
    firmatari: list[str] = field(default_factory=list)  # dc:creator
    altri_firmatari: list[str] = field(default_factory=list)  # dc:contributor


@dataclass
class VotazioneCamera:
    id: str  # IRI
    titolo: str
    descrizione: str | None
    tipo_fonte: str | None  # dc:type: Emendamento, Articolo, Finale atto Camera, ...
    data: date | None
    finale: bool
    fiducia: bool  # ocd:richiestaFiducia: votazione nella procedura di una questione di fiducia
    segreta: bool
    approvato: bool | None
    presenti: int | None
    votanti: int | None
    favorevoli: int | None
    contrari: int | None
    astenuti: int | None
    maggioranza: int | None
    numero: str | None  # numero dell'atto Camera ("2122-BIS"), dal collegamento o dall'etichetta
    fonte_url: str | None
    # favorevoli/contrari/astenuti → identificativi delle persone (senza PERSONA davanti)
    voti: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class LegislaturaCamera:
    numero: int
    leggi: list[LeggeCamera]
    atti: list[AttoCamera]  # solo per le legislature senza dati del Senato (X-XII)
    votazioni: list[VotazioneCamera]  # solo quelle sulle fasi Camera degli iter diventati legge
    votazioni_scartate: int = 0
    fasi_senato: list[str] = field(default_factory=list)  # numeri delle fasi Camera negli iter del Senato


@dataclass
class Deputato:
    id: str  # persona
    nome: str | None
    cognome: str | None


@dataclass
class AdesioneCamera:
    deputato: str
    gruppo: str  # IRI
    inizio: date
    fine: date | None


@dataclass
class GruppoCamera:
    id: str  # IRI
    legislatura: int
    nome: str
    sigla: str | None
    inizio: date
    fine: date | None
    precedenti: list[tuple[str, str | None, date | None]] = field(default_factory=list)  # nome, sigla, fino a


@dataclass
class GovernoCamera:
    titolo: str
    inizio: date
    fine: date | None


@dataclass
class PersoneCamera:
    deputati: list[Deputato]
    adesioni: list[AdesioneCamera]
    gruppi: list[GruppoCamera]
    governi: list[GovernoCamera]


# --- Regole pure (provate offline) ---------------------------------------------

_ATTO = re.compile(r"/ac(\d+)_([^/]+)$")
_PERSONA = re.compile(r"/(?:d|p)(\d+)(?:_\d+)?$")
_DATE_FINALI = re.compile(r"\s*\(\d{2}\.\d{2}\.\d{4}\s*-\s*(?:\d{2}\.\d{2}\.\d{4})?\)\s*$")
_FINO_A = re.compile(r"fino a (\d{2})\.(\d{2})\.(\d{4})")


def numero_atto(iri: str) -> str | None:
    """".../attocamera.rdf/ac14_2122-bis-b" → "2122-BIS-B"."""
    trovato = _ATTO.search(iri)
    return trovato.group(2).upper() if trovato else None


def persona(iri: str) -> str | None:
    """Deputato (".../deputato.rdf/d305578_17") o persona (".../persona.rdf/p305578") → "305578"."""
    trovato = _PERSONA.search(iri)
    return trovato.group(1) if trovato else None


def data_camera(valore: str | None) -> date | None:
    """"20020114" → 2002-01-14; accetta anche le date ISO."""
    if not valore:
        return None
    cifre = valore.strip()[:10].replace("-", "")
    try:
        return date(int(cifre[:4]), int(cifre[4:6]), int(cifre[6:8]))
    except ValueError:
        return None


def testo(valore: str | None) -> str | None:
    """Le etichette della Camera hanno entità HTML, a volte doppie ("&amp;#39;")."""
    if valore is None:
        return None
    return html.unescape(html.unescape(valore)).strip()


def nome_gruppo(titolo: str, sigla: str | None) -> str:
    """"ALLEANZA NAZIONALE (AN) (04.06.2001-27.04.2006)" → "ALLEANZA NAZIONALE"."""
    nome = _DATE_FINALI.sub("", titolo).strip()
    if sigla and nome.endswith(f"({sigla})"):
        nome = nome[: -len(sigla) - 2].strip()
    return nome


def fino_a(etichetta: str | None) -> date | None:
    """"gia' ITALIA VIVA (IV) fino a 31.07.2022" → 2022-07-31."""
    trovato = _FINO_A.search(etichetta or "")
    return date(int(trovato.group(3)), int(trovato.group(2)), int(trovato.group(1))) if trovato else None


def numero_votazione(atti: list[str], titolo: str, descrizione: str | None) -> str | None:
    """Il numero dell'atto su cui si vota: dal collegamento della fonte, se manca dall'etichetta ("DDL n.2798")."""
    for atto in atti:
        if numero := numero_atto(atto):
            return numero
    for etichetta in (titolo, descrizione or ""):
        if numero := numero_ddl_da_etichetta(etichetta):
            return numero
    return None


def tipo_votazione(v: VotazioneCamera) -> str:
    """finale / fiducia / pregiudiziale / emendamento / articolo / altro.

    La Camera segna con `richiestaFiducia` tutte le votazioni della procedura
    di fiducia, compresa la votazione finale che segue: la finale resta finale,
    le altre (l'articolo o l'emendamento su cui il governo pone la fiducia)
    sono il voto di fiducia.
    """
    if v.finale or v.tipo_fonte == "Finale atto Camera":
        return "finale"
    if v.fiducia or "fiducia" in v.titolo.lower():
        return "fiducia"
    fonte = (v.tipo_fonte or "").lower()
    if fonte in ("pregiudiziale", "pregiudiziali", "questione sospensiva", "sospensiva"):
        return "pregiudiziale"
    if fonte == "emendamento":
        return "emendamento"
    if fonte == "articolo":
        return "articolo"
    if fonte:
        return "altro"
    return senato.tipo_votazione(v.titolo)


INIZIATIVE = {
    "governo": "governativa",
    "parlamentare": "parlamentare",
    "popolare": "popolare",
    "regioni": "regionale",
    "cnel": "CNEL",
}


def iniziativa(testo_fonte: str | None) -> str | None:
    """"Governo" → governativa; "Mista (Governo, Parlamentare)" → governativa, come al Senato."""
    if not testo_fonte:
        return None
    valore = testo_fonte.strip().lower()
    if valore.startswith("mista"):
        return "governativa" if "governo" in valore else "parlamentare"
    return INIZIATIVE.get(valore, valore)


def natura(legge: LeggeCamera) -> str:
    if (legge.tipo or "").lower().startswith("costituzional"):
        return "costituzionale"
    titolo = legge.titolo.lower()
    if titolo.startswith("conversione in legge"):
        return "conversione di decreto-legge"
    if titolo.startswith("bilancio di previsione"):
        return "bilancio"
    return "ordinaria"


def urn_da_lex(lex: str | None) -> str | None:
    """"http://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1990-08-07;241" → l'URN."""
    if not lex or "urn:nir:" not in lex:
        return None
    return lex[lex.index("urn:nir:"):]


def _vero(valore: str | None) -> bool:
    return (valore or "").strip().lower() in ("1", "true")


def _iri_in(iri: list[str]) -> str:
    return ", ".join(f"<{x}>" for x in iri)


# --- Estrazione -----------------------------------------------------------------


def estrai_leggi(sparql: Sparql, leg: int) -> list[LeggeCamera]:
    modello = f"""SELECT DISTINCT ?l ?lex ?numero ?data ?titolo ?tipo ?atto WHERE {{
  ?l a ocd:legge ; ocd:rif_leg <{legislatura_iri(leg)}> ; dc:title ?titolo .
  OPTIONAL {{ ?l ocd:lex ?lex }} OPTIONAL {{ ?l dc:identifier ?numero }} OPTIONAL {{ ?l dc:date ?data }} OPTIONAL {{ ?l dc:type ?tipo }}
  OPTIONAL {{ ?l ocd:lavoriPreparatori ?lp . ?lp ocd:rif_attoCamera ?atto }}
  %DOPO% }}"""
    leggi: dict[str, LeggeCamera] = {}
    for r in scorri(sparql, modello, "l"):
        legge = leggi.get(r["l"])
        if legge is None:
            legge = leggi[r["l"]] = LeggeCamera(
                r["l"], urn_da_lex(r.get("lex")), _intero(r.get("numero")), data_camera(r.get("data")),
                testo(r["titolo"]) or "", r.get("tipo"),
            )
        if (atto := r.get("atto")) and atto not in legge.atti:
            legge.atti.append(atto)
    return list(leggi.values())


def estrai_atti(sparql: Sparql, iri: list[str]) -> list[AttoCamera]:
    atti: dict[str, AttoCamera] = {}
    for inizio in range(0, len(iri), ATTI_PER_RICHIESTA):
        gruppo = _iri_in(iri[inizio:inizio + ATTI_PER_RICHIESTA])
        for r in sparql.select(f"""SELECT DISTINCT ?a ?titolo ?data ?iniz ?primo ?scheda WHERE {{ ?a a ocd:atto .
  OPTIONAL {{ ?a dc:title ?titolo }} OPTIONAL {{ ?a dc:date ?data }} OPTIONAL {{ ?a ocd:iniziativa ?iniz }}
  OPTIONAL {{ ?a ocd:primo_firmatario ?primo }} OPTIONAL {{ ?a dcterms:isReferencedBy ?scheda }} FILTER(?a IN ({gruppo})) }}"""):
            if r["a"] not in atti and (numero := numero_atto(r["a"])):
                primo = persona(r["primo"]) if r.get("primo") else None
                atti[r["a"]] = AttoCamera(
                    r["a"], numero, testo(r.get("titolo")), data_camera(r.get("data")), r.get("iniz"), primo, r.get("scheda"),
                )
        for r in sparql.select(f"""SELECT DISTINCT ?a ?p ?nome WHERE {{ ?a ?p ?nome FILTER(?a IN ({gruppo}))
  FILTER(?p IN (dc:creator, dc:contributor)) }}"""):
            if atto := atti.get(r["a"]):
                elenco = atto.firmatari if r["p"].endswith("creator") else atto.altri_firmatari
                if (nome := testo(r["nome"])) and nome not in elenco:
                    elenco.append(nome)
    return list(atti.values())


def estrai_votazioni(sparql: Sparql, leg: int) -> list[VotazioneCamera]:
    modello = f"""SELECT DISTINCT ?v ?titolo ?descr ?tipo ?data ?fin ?fid ?seg ?appr ?presenti ?votanti ?fav ?con ?ast ?magg ?atto ?rel WHERE {{
  ?v a ocd:votazione ; ocd:rif_leg <{legislatura_iri(leg)}> ; dc:title ?titolo .
  OPTIONAL {{ ?v dc:description ?descr }} OPTIONAL {{ ?v dc:type ?tipo }} OPTIONAL {{ ?v dc:date ?data }}
  OPTIONAL {{ ?v ocd:votazioneFinale ?fin }} OPTIONAL {{ ?v ocd:richiestaFiducia ?fid }} OPTIONAL {{ ?v ocd:votazioneSegreta ?seg }}
  OPTIONAL {{ ?v ocd:approvato ?appr }} OPTIONAL {{ ?v ocd:presenti ?presenti }} OPTIONAL {{ ?v ocd:votanti ?votanti }}
  OPTIONAL {{ ?v ocd:favorevoli ?fav }} OPTIONAL {{ ?v ocd:contrari ?con }} OPTIONAL {{ ?v ocd:astenuti ?ast }}
  OPTIONAL {{ ?v ocd:maggioranza ?magg }} OPTIONAL {{ ?v ocd:rif_attoCamera ?atto }} OPTIONAL {{ ?v dc:relation ?rel }}
  %DOPO% }}"""
    votazioni: dict[str, VotazioneCamera] = {}
    atti: dict[str, list[str]] = {}
    for r in scorri(sparql, modello, "v"):
        if r["v"] not in votazioni:
            votazioni[r["v"]] = VotazioneCamera(
                r["v"], testo(r["titolo"]) or "", testo(r.get("descr")), r.get("tipo"), data_camera(r.get("data")),
                _vero(r.get("fin")), _vero(r.get("fid")), _vero(r.get("seg")),
                _vero(r["appr"]) if r.get("appr") not in (None, "") else None,
                _intero(r.get("presenti")), _intero(r.get("votanti")), _intero(r.get("fav")), _intero(r.get("con")),
                _intero(r.get("ast")), _intero(r.get("magg")), None, r.get("rel"),
            )
        if (atto := r.get("atto")) and atto not in atti.setdefault(r["v"], []):
            atti[r["v"]].append(atto)
    for v in votazioni.values():
        v.numero = numero_votazione(atti.get(v.id, []), v.titolo, v.descrizione)
    return list(votazioni.values())


def estrai_voti(sparql: Sparql, votazioni: list[VotazioneCamera]) -> None:
    """Riempie `voti` delle votazioni palesi, a gruppi di VOTAZIONI_PER_RICHIESTA. Chi non ha votato non si salva."""
    palesi = [v for v in votazioni if not v.segreta]
    for inizio in range(0, len(palesi), VOTAZIONI_PER_RICHIESTA):
        gruppo = {v.id: v for v in palesi[inizio:inizio + VOTAZIONI_PER_RICHIESTA]}
        righe = sparql.select(f"""SELECT DISTINCT ?v ?d ?t WHERE {{ ?x ocd:rif_votazione ?v ; ocd:rif_deputato ?d ; dc:type ?t
  FILTER(?v IN ({_iri_in(list(gruppo))})) FILTER(STR(?t) IN ("Favorevole", "Contrario", "Astensione")) }}""")
        if len(righe) >= senato.LIMITE_RIGHE:
            raise RuntimeError(f"risposta troncata per le votazioni da {palesi[inizio].id}")
        for r in righe:
            if (chi := persona(r["d"])) and (voto := VOTI.get(r["t"])):
                elenco = gruppo[r["v"]].voti.setdefault(voto, [])
                if chi not in elenco:
                    elenco.append(chi)
        if inizio and inizio % 1000 < VOTAZIONI_PER_RICHIESTA:
            logger.info("voti: %s votazioni su %s", inizio, len(palesi))
    if vuote := sum(1 for v in palesi if not v.voti and (v.favorevoli or v.contrari or v.astenuti)):
        logger.warning("voti: %s votazioni palesi su %s senza alcun voto individuale", vuote, len(palesi))


# --- voti XIII-XVI dalle schede HTML ---------------------------------------------------
# Ogni votazione ha una pagina su documenti.camera.it (dc:relation) con una riga per deputato:
# <tr><td>ABATERUSSO ERNESTO</td><td>DS-U</td><td><span class="rosso">Contrario</span></td></tr>.
# Il voto è Favorevole, Contrario, Astensione, Non ha partecipato o In missione; il nome non ha
# identificativi e si collega ai deputati della legislatura per cognome e nome (sigla del gruppo
# per gli omonimi).

VOTI_SCHEDA = {"Favorevole": "favorevoli", "Contrario": "contrari", "Astensione": "astenuti"}
_ROMANI = {13: "XIII", 14: "XIV", 15: "XV", 16: "XVI", 17: "XVII", 18: "XVIII", 19: "XIX"}
_TABELLA_SCHEDA = re.compile(r'(?is)<table[^>]*id="tabellaPartecipazioneVoto".*?</table>')
_RIGA_SCHEDA = re.compile(r"(?is)<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>")
_VOTAZIONE_IRI = re.compile(r"/vs(\d+)_(\d+)_(\d+)$")


def url_scheda(v: VotazioneCamera) -> str | None:
    """La scheda della votazione: dc:relation in HTTPS, altrimenti ricostruita dall'IRI (vs13_128_059 → 128_59)."""
    if v.fonte_url and "schedavotazione" in v.fonte_url:
        return v.fonte_url.replace("http://", "https://", 1)
    if not (trovato := _VOTAZIONE_IRI.search(v.id)) or int(trovato.group(1)) not in _ROMANI:
        return None
    leg, seduta, numero = (int(g) for g in trovato.groups())
    return SCHEDA.format(romano=_ROMANI[leg], rif=f"{seduta}_{numero}")


def _senza_tag(testo_html: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", testo_html)).split())


def righe_scheda(pagina: str) -> list[tuple[str, str, str]]:
    """(nominativo, sigla del gruppo, voto) per ogni deputato della scheda."""
    tabella = _TABELLA_SCHEDA.search(pagina)
    if not tabella:
        return []
    return [(_senza_tag(a), _senza_tag(b), _senza_tag(c)) for a, b, c in _RIGA_SCHEDA.findall(tabella.group(0))]


def chiave_nome(testo_nome: str) -> str:
    """"Nicolò D'Alia" e "NICOLO' D ALIA" → "NICOLO DALIA": niente accenti, apostrofi né spazi doppi."""
    senza_accenti = "".join(c for c in unicodedata.normalize("NFKD", testo_nome) if not unicodedata.combining(c))
    return " ".join(re.sub(r"['`’.]", "", senza_accenti).replace("-", " ").upper().split())


@dataclass
class NomiDeputati:
    """Deputati di una legislatura per "COGNOME NOME", con le sigle dei loro gruppi."""

    per_nome: dict[str, list[str]] = field(default_factory=dict)
    sigle: dict[str, set[str]] = field(default_factory=dict)

    def aggiungi(self, chi: str, cognome: str, nome: str, sigla: str | None) -> None:
        elenco = self.per_nome.setdefault(chiave_nome(f"{cognome} {nome}"), [])
        if chi not in elenco:
            elenco.append(chi)
        if sigla:
            self.sigle.setdefault(chi, set()).add(chiave_nome(sigla))

    def trova(self, nominativo: str, sigla: str) -> str | None:
        candidati = self.per_nome.get(chiave_nome(nominativo), [])
        if len(candidati) > 1:
            candidati = [c for c in candidati if chiave_nome(sigla) in self.sigle.get(c, set())]
        return candidati[0] if len(candidati) == 1 else None


def nomi_deputati(sparql: Sparql, leg: int) -> NomiDeputati:
    nomi = NomiDeputati()
    for r in scorri(sparql, f"""SELECT DISTINCT ?d ?cognome ?nome ?sigla WHERE {{ ?d a ocd:deputato ; ocd:rif_leg <{legislatura_iri(leg)}> ;
  foaf:surname ?cognome ; foaf:firstName ?nome .
  OPTIONAL {{ ?d ocd:aderisce ?a . ?a ocd:rif_gruppoParlamentare ?g . ?g dcterms:alternative ?sigla }} %DOPO% }}""", "d"):
        if chi := persona(r["d"]):
            nomi.aggiungi(chi, testo(r["cognome"]) or "", testo(r["nome"]) or "", testo(r.get("sigla")))
    return nomi


def scarica_scheda(url: str, tentativi: int = 6) -> str:
    agente = "archivio-leggi (progetto non commerciale; github.com/PeppeMoscato/archivio-leggi)"
    richiesta = urllib.request.Request(url, headers={"User-Agent": agente})
    for tentativo in range(1, tentativi + 1):
        try:
            with urllib.request.urlopen(richiesta, timeout=60) as risposta:
                grezzo = risposta.read()
                codifica = risposta.headers.get_content_charset() or "windows-1252"
            return grezzo.decode(codifica, errors="replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as errore:
            if tentativo == tentativi or (isinstance(errore, urllib.error.HTTPError) and errore.code < 500 and errore.code != 429):
                raise
            logger.warning("scheda %s: %s, tentativo %s", url, errore, tentativo)
            time.sleep(10 * tentativo)
    raise AssertionError("non raggiungibile")


def estrai_voti_schede(
    votazioni: list[VotazioneCamera], nomi: NomiDeputati, scarica: Callable[[str], str] = scarica_scheda
) -> list[str]:
    """Riempie `voti` delle votazioni palesi dalle schede HTML; restituisce le righe del rapporto."""
    palesi = [v for v in votazioni if not v.segreta and url_scheda(v)]

    def leggi(v: VotazioneCamera) -> tuple[VotazioneCamera, list[tuple[str, str, str]] | None]:
        try:
            pagina = scarica(url_scheda(v) or "")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as errore:
            logger.warning("scheda di %s non scaricata: %s", v.id, errore)
            return v, None
        finally:
            time.sleep(PAUSA_SCHEDA)
        return v, righe_scheda(pagina)

    non_scaricate = vuote = diverse = 0
    sconosciuti: dict[str, int] = {}
    with ThreadPoolExecutor(SCHEDE_IN_PARALLELO) as lettori:
        for fatte, (v, righe) in enumerate(lettori.map(leggi, palesi), 1):
            if righe is None:
                non_scaricate += 1
                continue
            if not righe:
                vuote += 1
            for nominativo, sigla, voto in righe:
                if not (chiave := VOTI_SCHEDA.get(voto)):
                    continue
                if (chi := nomi.trova(nominativo, sigla)) is None:
                    sconosciuti[f"{nominativo} ({sigla})"] = sconosciuti.get(f"{nominativo} ({sigla})", 0) + 1
                elif chi not in (elenco := v.voti.setdefault(chiave, [])):
                    elenco.append(chi)
            conti = (len(v.voti.get("favorevoli", [])), len(v.voti.get("contrari", [])), len(v.voti.get("astenuti", [])))
            if righe and conti != (v.favorevoli or 0, v.contrari or 0, v.astenuti or 0):
                diverse += 1
            if fatte % 1000 == 0:
                logger.info("schede: %s su %s", fatte, len(palesi))
    rapporto = [
        f"schede lette: {len(palesi) - non_scaricate} su {len(palesi)} votazioni palesi; non scaricate: {non_scaricate}; senza tabella: {vuote}",
        f"votazioni con elenchi diversi dai totali della fonte: {diverse}",
        f"nomi non collegati a un deputato: {len(sconosciuti)} ({sum(sconosciuti.values())} voti)"
        + (": " + ", ".join(f"{n} ×{c}" for n, c in sorted(sconosciuti.items(), key=lambda x: -x[1])[:15]) if sconosciuti else ""),
    ]
    for riga in rapporto:
        logger.info("voti dalle schede: %s", riga)
    return rapporto


def fasi_camera_del_senato(sparql_senato: Sparql, leg: int) -> list[str]:
    """I numeri delle letture alla Camera ("2122-BIS") negli iter diventati legge della legislatura, dal Senato."""
    fasi = senato.estrai_fasi(sparql_senato, leg)
    return sorted({numero_senza_ramo(f.numero) for f in fasi.values() if f.ramo.upper() == "C"})


def scegli_votazioni(votazioni: list[VotazioneCamera], numeri: set[str]) -> tuple[list[VotazioneCamera], int]:
    """Le votazioni sugli atti che stanno negli iter diventati legge; le altre si contano e basta."""
    scelte = [v for v in votazioni if v.numero and v.numero in numeri]
    return scelte, len(votazioni) - len(scelte)


def estrai_legislatura(camera: Sparql, senato_client: Sparql | None, leg: int) -> LegislaturaCamera:
    leggi = [legge for legge in estrai_leggi(camera, leg) if legge.data is None or legge.data >= INIZIO_PERIMETRO]
    logger.info("legislatura %s: %s leggi dal 1990", leg, len(leggi))
    if leg < PRIMA_CON_VOTI:
        atti = estrai_atti(camera, sorted({a for legge in leggi for a in legge.atti}))
        logger.info("legislatura %s: %s atti Camera nei lavori preparatori", leg, len(atti))
        return LegislaturaCamera(leg, leggi, atti, [])
    if senato_client is None:
        raise ValueError("dalla XIII legislatura servono le fasi Camera degli iter del Senato")
    numeri = fasi_camera_del_senato(senato_client, leg)
    tutte = estrai_votazioni(camera, leg)
    scelte, scartate = scegli_votazioni(tutte, set(numeri))
    logger.info("legislatura %s: %s votazioni sugli iter diventati legge, %s altre", leg, len(scelte), scartate)
    if leg >= PRIMA_CON_VOTI_INDIVIDUALI:
        estrai_voti(camera, scelte)
    else:
        logger.info("legislatura %s: voti dei deputati dalle schede HTML (l'endpoint ha solo esiti e totali)", leg)
        estrai_voti_schede(scelte, nomi_deputati(camera, leg))
    return LegislaturaCamera(leg, leggi, [], scelte, scartate, numeri)


def stima_legislatura(camera: Sparql, senato_client: Sparql, leg: int) -> tuple[int, int, int]:
    """Senza scaricare i voti: votazioni da caricare, quante palesi e quanti voti individuali (dai totali della fonte).

    Prima della XVII i voti individuali si contano lo stesso: sono quelli che darebbero le schede HTML."""
    numeri = set(fasi_camera_del_senato(senato_client, leg))
    scelte, _ = scegli_votazioni(estrai_votazioni(camera, leg), numeri)
    palesi = [v for v in scelte if not v.segreta]
    voti = sum((v.favorevoli or 0) + (v.contrari or 0) + (v.astenuti or 0) for v in palesi)
    return len(scelte), len(palesi), voti


def estrai_persone(sparql: Sparql, legislature: list[int]) -> PersoneCamera:
    deputati: dict[str, Deputato] = {}
    adesioni: dict[tuple[str, str, date], AdesioneCamera] = {}
    gruppi: dict[str, GruppoCamera] = {}
    for leg in legislature:
        leg_iri = legislatura_iri(leg)
        for r in scorri(sparql, f"""SELECT DISTINCT ?d ?nome ?cognome WHERE {{ ?d a ocd:deputato ; ocd:rif_leg <{leg_iri}> .
  OPTIONAL {{ ?d foaf:firstName ?nome }} OPTIONAL {{ ?d foaf:surname ?cognome }} %DOPO% }}""", "d"):
            if (chi := persona(r["d"])) and chi not in deputati:
                deputati[chi] = Deputato(chi, testo(r.get("nome")), testo(r.get("cognome")))
        for r in scorri(sparql, f"""SELECT DISTINCT ?d ?g ?inizio ?fine WHERE {{ ?d a ocd:deputato ; ocd:rif_leg <{leg_iri}> ; ocd:aderisce ?a .
  ?a ocd:rif_gruppoParlamentare ?g ; ocd:startDate ?inizio . OPTIONAL {{ ?a ocd:endDate ?fine }} %DOPO% }}""", "d"):
            chi, inizio = persona(r["d"]), data_camera(r["inizio"])
            if chi and inizio:
                adesioni[(chi, r["g"], inizio)] = AdesioneCamera(chi, r["g"], inizio, data_camera(r.get("fine")))
        for r in sparql.select(f"""SELECT DISTINCT ?g ?titolo ?sigla ?inizio ?fine WHERE {{ ?g a ocd:gruppoParlamentare ; ocd:rif_leg <{leg_iri}> ;
  dc:title ?titolo ; ocd:startDate ?inizio . OPTIONAL {{ ?g dcterms:alternative ?sigla }} OPTIONAL {{ ?g ocd:endDate ?fine }} }}"""):
            inizio = data_camera(r["inizio"])
            if inizio and r["g"] not in gruppi:
                sigla = testo(r.get("sigla"))
                gruppi[r["g"]] = GruppoCamera(r["g"], leg, nome_gruppo(testo(r["titolo"]) or "", sigla), sigla, inizio, data_camera(r.get("fine")))
        for r in sparql.select(f"""SELECT DISTINCT ?g ?titolo ?sigla ?etichetta WHERE {{ ?g a ocd:gruppoParlamentare ; ocd:rif_leg <{leg_iri}> ;
  ocd:denominazione ?d . ?d dc:title ?titolo OPTIONAL {{ ?d dcterms:alternative ?sigla }} OPTIONAL {{ ?d rdfs:label ?etichetta }} }}"""):
            if gruppo := gruppi.get(r["g"]):
                precedente = (testo(r["titolo"]) or "", testo(r.get("sigla")), fino_a(testo(r.get("etichetta"))))
                if precedente not in gruppo.precedenti:
                    gruppo.precedenti.append(precedente)
        logger.info("legislatura %s: %s deputati, %s adesioni, %s gruppi finora", leg, len(deputati), len(adesioni), len(gruppi))
    governi = [
        GovernoCamera(testo(r["titolo"]) or "", data_camera(r["inizio"]), data_camera(r.get("fine")))
        for r in sparql.select("""SELECT DISTINCT ?titolo ?inizio ?fine WHERE { ?g a ocd:governo ; dc:title ?titolo ; ocd:startDate ?inizio
  OPTIONAL { ?g ocd:endDate ?fine } FILTER(STR(?inizio) >= "1989") }""")
        if data_camera(r["inizio"])
    ]
    return PersoneCamera(list(deputati.values()), list(adesioni.values()), list(gruppi.values()), sorted(governi, key=lambda g: g.inizio))


def client() -> Sparql:
    # L'endpoint della Camera va a tratti in 502 per minuti (27/10/2026): più tentativi che al Senato,
    # con attese crescenti (10, 20, ... 110 s: circa 11 minuti in tutto).
    return Sparql(ENDPOINT, PREFISSI, tentativi=12)


# --- File intermedi ---------------------------------------------------------------


def scrivi(percorso: Path, oggetto) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(asdict(oggetto), default=_json, ensure_ascii=False), encoding="utf-8")


def _date(d: dict, *campi: str) -> dict:
    for campo in campi:
        if isinstance(d.get(campo), str):
            d[campo] = date.fromisoformat(d[campo])
    return d


def leggi_legislatura(percorso: Path) -> LegislaturaCamera:
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    return LegislaturaCamera(
        dati["numero"],
        [LeggeCamera(**_date(legge, "data")) for legge in dati["leggi"]],
        [AttoCamera(**_date(a, "data")) for a in dati["atti"]],
        [VotazioneCamera(**_date(v, "data")) for v in dati["votazioni"]],
        dati.get("votazioni_scartate", 0),
        dati.get("fasi_senato", []),
    )


def leggi_persone(percorso: Path) -> PersoneCamera:
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    gruppi = []
    for g in dati["gruppi"]:
        _date(g, "inizio", "fine")
        g["precedenti"] = [(nome, sigla, date.fromisoformat(fine) if fine else None) for nome, sigla, fine in g["precedenti"]]
        gruppi.append(GruppoCamera(**g))
    return PersoneCamera(
        [Deputato(**d) for d in dati["deputati"]],
        [AdesioneCamera(**_date(a, "inizio", "fine")) for a in dati["adesioni"]],
        gruppi,
        [GovernoCamera(**_date(g, "inizio", "fine")) for g in dati["governi"]],
    )
