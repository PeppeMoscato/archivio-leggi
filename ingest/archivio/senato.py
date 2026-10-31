"""Estrazione da dati.senato.it (Task 1.2): iter, fasi, firmatari, votazioni, senatori e gruppi.

Il Senato ha dati dalla XIII legislatura (1996) e l'iter completo, comprese le
letture alla Camera (`docs/sonda_parlamento.md`). Si prendono solo gli iter
diventati legge e, per quelli, tutte le votazioni d'Aula tranne le verifiche
del numero legale.

L'endpoint è un Virtuoso vecchio: niente VALUES, BIND e SAMPLE; risposte
troncate a 10.000 righe e OFFSET grandi che vanno in errore. Per questo le
query scorrono per chiave (`scorri`) invece che per OFFSET, e i voti dei singoli
si chiedono a gruppi di votazioni con FILTER IN.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from archivio.sparql import Sparql

logger = logging.getLogger(__name__)

ENDPOINT = "https://dati.senato.it/sparql"
PREFISSI = """PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""
LEGISLATURE = range(13, 20)  # dalla XIII (1996); la XIX è in corso
LIMITE_RIGHE = 10_000  # Virtuoso non restituisce di più
VOTAZIONI_PER_RICHIESTA = 25  # 25 × 320 senatori al massimo: sotto il limite di righe

SENATORE = "http://dati.senato.it/senatore/"
GRUPPO = "http://dati.senato.it/gruppo/"
DDL = "http://dati.senato.it/ddl/"
VOTAZIONE = "http://dati.senato.it/votazione/"
VOTI = {"favorevole": "favorevoli", "contrario": "contrari", "astenuto": "astenuti"}


def scheda_iter(legislatura: int, id_ddl: str) -> str:
    return f"https://www.senato.it/leg/{legislatura}/BGT/Schede/Ddliter/{id_ddl}.htm"


# --- Modelli intermedi (JSON fra estrazione e caricamento) ---------------------


@dataclass
class Fase:
    id: str  # IRI del ddl
    id_ddl: str  # identificativo dell'iter
    progressivo: int
    ramo: str  # C / S come nella fonte
    numero: str
    titolo: str
    natura: str
    data_presentazione: date | None
    stato: str | None
    data_stato: date | None
    numeri_legge: list[int] = field(default_factory=list)
    date_legge: list[date] = field(default_factory=list)
    # Identificativo del testo presentato (con la relazione illustrativa), es.
    # urn:nir:senato.repubblica:disegno.legge:14.legislatura;1271; c'è in circa il 38% delle fasi (sonda del 29/10/2026).
    testo_presentato: str | None = None


@dataclass
class Iniziativa:
    fase_id: str
    nome: str
    tipo: str | None
    primo_firmatario: bool
    senatore: str | None  # IRI


@dataclass
class Votazione:
    id: str  # IRI
    descrizione: str
    tipo_votazione: str | None
    esito: str | None
    presenti: int | None
    votanti: int | None
    favorevoli: int | None
    contrari: int | None
    astenuti: int | None
    maggioranza: int | None
    data: date | None
    fasi_oggetto: list[str] = field(default_factory=list)  # IRI dei ddl collegati dall'oggetto della trattazione
    # favorevoli/contrari/astenuti → identificativi dei senatori (l'IRI senza SENATORE, per non gonfiare i file)
    voti: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Legislatura:
    numero: int
    fasi: list[Fase]
    iniziative: list[Iniziativa]
    votazioni: list[Votazione]  # solo quelle collegate a una fase degli iter diventati legge
    votazioni_scartate: int = 0  # su ddl mai diventati legge o senza collegamento
    # False quando si estraggono solo iter e fasi (--senza-voti): il caricamento lascia le votazioni già nel database.
    con_voti: bool = True


@dataclass
class Senatore:
    id: str
    nome: str | None
    cognome: str | None


@dataclass
class Adesione:
    senatore: str
    gruppo: str
    inizio: date
    fine: date | None
    carica: str | None


@dataclass
class Denominazione:
    gruppo: str
    inizio: date
    fine: date | None
    nome: str
    sigla: str | None


@dataclass
class Persone:
    senatori: list[Senatore]
    adesioni: list[Adesione]
    denominazioni: list[Denominazione]


# --- Regole pure (provate offline) ---------------------------------------------

_NUMERO_DDL = re.compile(r"(?:disegno di legge|d\.?d\.?l\.?)\s*(?:n\.?\s*)?(\d+(?:-[a-z]+)*)", re.IGNORECASE)


def numero_ddl_da_etichetta(etichetta: str) -> str | None:
    """"Disegno di legge n. 3660. Votazione finale" → "3660"; "DDL n. 1306-B" → "1306-B"."""
    trovato = _NUMERO_DDL.search(etichetta)
    return trovato.group(1).upper() if trovato else None


def tipo_votazione(etichetta: str) -> str:
    """Il tipo della votazione dall'etichetta della fonte: finale / fiducia / pregiudiziale / emendamento / articolo / altro."""
    testo = etichetta.lower()
    if "fiducia" in testo and "sfiducia" not in testo:
        return "fiducia"
    if "votazione finale" in testo or "nel suo complesso" in testo:
        return "finale"
    if "pregiudizial" in testo or "sospensiv" in testo:
        return "pregiudiziale"
    if re.search(r"emendament|\bemm?\.|^\s*\d+\.\d+", testo):
        return "emendamento"
    if re.search(r"\barticol|\bart\.", testo):
        return "articolo"
    return "altro"


NATURE = {
    "ordinaria": "ordinaria",
    "costituzionale": "costituzionale",
    "di conversione di decreto-legge": "conversione di decreto-legge",
    "di approvazione di bilancio": "bilancio",
}

INIZIATIVE = {
    "governativa": "governativa",
    "parlamentare": "parlamentare",
    "popolare": "popolare",
    "regionale": "regionale",
    "cnel": "CNEL",
    "di ente": "di ente",
    "di commissione": "di commissione",
}


def natura(testo: str) -> str:
    return NATURE.get(testo.strip().lower(), testo.strip().lower())


def iniziativa(tipi: list[str | None]) -> str | None:
    """L'iniziativa dell'iter dai tipi della prima fase: governativa se il governo è fra i presentatori."""
    noti = [INIZIATIVE.get((t or "").strip().lower(), (t or "").strip().lower()) for t in tipi if t]
    if "governativa" in noti:
        return "governativa"
    return noti[0] if noti else None


def numero_senza_ramo(numero: str) -> str:
    """"S.1271-B" → "1271-B": il numero come lo scrivono le etichette delle votazioni."""
    return re.sub(r"^\s*[SC]\.\s*", "", numero.strip().upper())


def collega(votazione: Votazione, fasi_legislatura: dict[str, Fase], per_numero: dict[str, str]) -> str | None:
    """La fase a cui si riferisce una votazione.

    Se la fonte dà l'oggetto della trattazione vale quello (anche quando è un ddl
    mai diventato legge: allora la votazione resta fuori); se manca, il numero
    del ddl scritto nell'etichetta, cercato fra le fasi del Senato.
    """
    if votazione.fasi_oggetto:
        return next((fase for fase in votazione.fasi_oggetto if fase in fasi_legislatura), None)
    numero = numero_ddl_da_etichetta(votazione.descrizione)
    return per_numero.get(numero) if numero else None


def _intero(valore: str | None) -> int | None:
    try:
        return int(valore) if valore not in (None, "") else None
    except ValueError:
        return None


def _data(valore: str | None) -> date | None:
    try:
        return date.fromisoformat(valore[:10]) if valore else None
    except ValueError:
        return None


# --- Estrazione -----------------------------------------------------------------


def scorri(sparql: Sparql, modello: str, chiave: str) -> Iterator[dict[str, str]]:
    """Tutte le righe di `modello` ordinate per `?chiave`, una pagina alla volta.

    `modello` contiene `%DOPO%`, dove va il filtro sulla chiave. Si ordina e si
    filtra sulla stessa forma testuale della chiave, così le pagine combaciano.
    Le righe con la stessa chiave non si spezzano fra due pagine: l'ultima
    chiave di una pagina piena si richiede da capo nella successiva.
    """
    ultima: str | None = None
    while True:
        filtro = f'FILTER(STR(?{chiave}) >= "{ultima}")' if ultima else ""
        righe = sparql.select(modello.replace("%DOPO%", filtro) + f"\nORDER BY STR(?{chiave})\nLIMIT {LIMITE_RIGHE}")
        if len(righe) < LIMITE_RIGHE:
            yield from righe
            return
        confine = righe[-1][chiave]
        complete = [r for r in righe if r[chiave] != confine]
        if not complete:
            raise RuntimeError(f"più di {LIMITE_RIGHE} righe per la chiave {confine}")
        yield from complete
        ultima = confine


ITER_DIVENTATI_LEGGE = "{{ SELECT DISTINCT ?id WHERE {{ ?x a osr:Ddl ; osr:legislatura {leg} ; osr:numeroLegge ?n ; osr:idDdl ?id }} }}"


def estrai_fasi(sparql: Sparql, leg: int) -> dict[str, Fase]:
    modello = f"""SELECT ?fase ?id ?progr ?ramo ?numero ?titolo ?natura ?pres ?stato ?dataStato WHERE {{
  ?fase a osr:Ddl ; osr:legislatura {leg} ; osr:idDdl ?id ; osr:progressivoIter ?progr ; osr:ramo ?ramo ;
    osr:numeroFase ?numero ; osr:titolo ?titolo ; osr:natura ?natura .
  {ITER_DIVENTATI_LEGGE.format(leg=leg)}
  OPTIONAL {{ ?fase osr:dataPresentazione ?pres }} OPTIONAL {{ ?fase osr:statoDdl ?stato }} OPTIONAL {{ ?fase osr:dataStatoDdl ?dataStato }}
  OPTIONAL {{ ?fase osr:testoPresentato ?testo }}
  %DOPO% }}"""
    fasi: dict[str, Fase] = {}
    for r in scorri(sparql, modello, "fase"):
        fase = fasi.setdefault(r["fase"], Fase(
            r["fase"], r["id"], _intero(r["progr"]) or 0, r["ramo"], r["numero"], r["titolo"], r["natura"],
            _data(r.get("pres")), r.get("stato"), _data(r.get("dataStato")),
        ))
        fase.testo_presentato = fase.testo_presentato or r.get("testo")
    oggi = date.today()
    modello = f"""SELECT ?fase ?n ?d WHERE {{ ?fase a osr:Ddl ; osr:legislatura {leg} ; osr:numeroLegge ?n .
  OPTIONAL {{ ?fase osr:dataLegge ?d }} %DOPO% }}"""
    for r in scorri(sparql, modello, "fase"):
        fase = fasi.get(r["fase"])
        if fase is None:
            continue
        numero, giorno = _intero(r.get("n")), _data(r.get("d"))
        if numero and numero not in fase.numeri_legge:
            fase.numeri_legge.append(numero)
        # La fonte usa 2100-01-01 come segnaposto: si scartano le date nel futuro.
        if giorno and giorno <= oggi and giorno not in fase.date_legge:
            fase.date_legge.append(giorno)
    return fasi


def estrai_iniziative(sparql: Sparql, leg: int) -> list[Iniziativa]:
    modello = f"""SELECT ?iniz ?fase ?tipo ?nome ?primo ?persona WHERE {{
  ?fase a osr:Ddl ; osr:legislatura {leg} ; osr:idDdl ?id ; osr:iniziativa ?iniz .
  {ITER_DIVENTATI_LEGGE.format(leg=leg)}
  OPTIONAL {{ ?iniz osr:tipoIniziativa ?tipo }} OPTIONAL {{ ?iniz osr:presentatore ?nome }} OPTIONAL {{ ?iniz osr:primoFirmatario ?primo }}
  OPTIONAL {{ ?iniz ?collegamento ?persona FILTER(STRSTARTS(STR(?persona), "{SENATORE}")) }}
  %DOPO% }}"""
    iniziative: dict[tuple[str, str], Iniziativa] = {}
    # Si scorre per fase: le iniziative possono essere nodi anonimi, senza un IRI da ordinare.
    for r in scorri(sparql, modello, "fase"):
        chiave = (r["iniz"], r["fase"])
        if chiave not in iniziative:
            iniziative[chiave] = Iniziativa(r["fase"], r.get("nome") or "", r.get("tipo"), r.get("primo") == "1", r.get("persona"))
        elif r.get("persona") and not iniziative[chiave].senatore:
            iniziative[chiave].senatore = r["persona"]
    return [i for i in iniziative.values() if i.nome]


def estrai_votazioni(sparql: Sparql, leg: int) -> dict[str, Votazione]:
    modello = f"""SELECT ?v ?etichetta ?tipo ?esito ?presenti ?votanti ?fav ?con ?ast ?magg ?data ?fase WHERE {{
  ?v a osr:Votazione ; osr:legislatura {leg} ; rdfs:label ?etichetta .
  OPTIONAL {{ ?v osr:tipoVotazione ?tipo }} OPTIONAL {{ ?v osr:esito ?esito }} OPTIONAL {{ ?v osr:presenti ?presenti }}
  OPTIONAL {{ ?v osr:votanti ?votanti }} OPTIONAL {{ ?v osr:favorevoli ?fav }} OPTIONAL {{ ?v osr:contrari ?con }}
  OPTIONAL {{ ?v osr:astenuti ?ast }} OPTIONAL {{ ?v osr:maggioranza ?magg }}
  OPTIONAL {{ ?v osr:seduta ?s . ?s osr:dataSeduta ?data }}
  OPTIONAL {{ ?v osr:oggetto ?o . ?o osr:relativoA ?fase }}
  %DOPO% }}"""
    votazioni: dict[str, Votazione] = {}
    for r in scorri(sparql, modello, "v"):
        v = votazioni.get(r["v"])
        if v is None:
            v = votazioni[r["v"]] = Votazione(
                r["v"], r["etichetta"], r.get("tipo"), r.get("esito") or None, _intero(r.get("presenti")),
                _intero(r.get("votanti")), _intero(r.get("fav")), _intero(r.get("con")), _intero(r.get("ast")),
                _intero(r.get("magg")), _data(r.get("data")),
            )
        if r.get("fase", "").startswith(DDL) and r["fase"] not in v.fasi_oggetto:
            v.fasi_oggetto.append(r["fase"])
    return votazioni


def estrai_voti(sparql: Sparql, votazioni: list[Votazione]) -> None:
    """Riempie `voti` di ogni votazione, a gruppi di VOTAZIONI_PER_RICHIESTA."""
    for inizio in range(0, len(votazioni), VOTAZIONI_PER_RICHIESTA):
        gruppo = {v.id: v for v in votazioni[inizio:inizio + VOTAZIONI_PER_RICHIESTA]}
        elenco = ", ".join(f"<{iri}>" for iri in gruppo)
        righe = sparql.select(f"""SELECT ?v ?p ?s WHERE {{ ?v ?p ?s FILTER(?v IN ({elenco}))
  FILTER(?p IN (osr:favorevole, osr:contrario, osr:astenuto)) }}""")
        if len(righe) >= LIMITE_RIGHE:
            raise RuntimeError(f"risposta troncata per le votazioni da {votazioni[inizio].id}")
        for r in righe:
            voto = VOTI[r["p"].rsplit("/", 1)[-1]]
            gruppo[r["v"]].voti.setdefault(voto, []).append(r["s"].removeprefix(SENATORE))
        if inizio and inizio % 1000 < VOTAZIONI_PER_RICHIESTA:
            logger.info("voti: %s votazioni su %s", inizio, len(votazioni))


def estrai_legislatura(sparql: Sparql, leg: int, voti: bool = True) -> Legislatura:
    fasi = estrai_fasi(sparql, leg)
    logger.info("legislatura %s: %s fasi degli iter diventati legge", leg, len(fasi))
    iniziative = estrai_iniziative(sparql, leg)
    if not voti:
        # Poche richieste invece di migliaia: basta per aggiornare iter e fasi (es. il testo presentato).
        return Legislatura(leg, list(fasi.values()), iniziative, [], con_voti=False)
    per_numero = {numero_senza_ramo(f.numero): f.id for f in fasi.values() if f.ramo == "S"}
    tutte = estrai_votazioni(sparql, leg)
    collegate: list[Votazione] = []
    scartate = 0
    for v in tutte.values():
        if (v.tipo_votazione or "").lower() == "verifica numero legale":
            continue
        fase = collega(v, fasi, per_numero)
        if fase is None:
            scartate += 1
            continue
        v.fasi_oggetto = [fase]
        collegate.append(v)
    logger.info("legislatura %s: %s votazioni sugli iter diventati legge, %s su altri ddl o non collegate", leg, len(collegate), scartate)
    estrai_voti(sparql, collegate)
    return Legislatura(leg, list(fasi.values()), iniziative, collegate, scartate)


def estrai_persone(sparql: Sparql) -> Persone:
    senatori = {
        r["s"]: Senatore(r["s"], r.get("nome"), r.get("cognome"))
        for r in scorri(sparql, """SELECT ?s ?nome ?cognome WHERE { ?s a osr:Senatore .
  OPTIONAL { ?s foaf:firstName ?nome } OPTIONAL { ?s foaf:lastName ?cognome } %DOPO% }""", "s")
    }
    adesioni = {}
    for r in scorri(sparql, f"""SELECT ?s ?g ?inizio ?fine ?carica WHERE {{ ?s a osr:Senatore ; ocd:aderisce ?a .
  ?a osr:gruppo ?g ; osr:inizio ?inizio . OPTIONAL {{ ?a osr:fine ?fine }} OPTIONAL {{ ?a osr:carica ?carica }}
  FILTER(STRSTARTS(STR(?g), "{GRUPPO}")) %DOPO% }}""", "s"):
        inizio = _data(r["inizio"])
        if inizio:
            adesioni[(r["s"], r["g"], inizio)] = Adesione(r["s"], r["g"], inizio, _data(r.get("fine")), r.get("carica"))
    denominazioni = {}
    for r in scorri(sparql, f"""SELECT ?g ?nome ?sigla ?inizio ?fine WHERE {{ ?g osr:denominazione ?d .
  ?d osr:titolo ?nome ; osr:inizio ?inizio . OPTIONAL {{ ?d osr:titoloBreve ?sigla }} OPTIONAL {{ ?d osr:fine ?fine }}
  FILTER(STRSTARTS(STR(?g), "{GRUPPO}")) %DOPO% }}""", "g"):
        inizio = _data(r["inizio"])
        if inizio:
            denominazioni[(r["g"], inizio)] = Denominazione(r["g"], inizio, _data(r.get("fine")), r["nome"], r.get("sigla"))
    return Persone(list(senatori.values()), list(adesioni.values()), list(denominazioni.values()))


def client() -> Sparql:
    return Sparql(ENDPOINT, PREFISSI)


# --- File intermedi ---------------------------------------------------------------


def _json(valore):
    if isinstance(valore, date):
        return valore.isoformat()
    raise TypeError(type(valore))


def scrivi(percorso: Path, oggetto) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(asdict(oggetto), default=_json, ensure_ascii=False), encoding="utf-8")


def _date(d: dict, *campi: str) -> dict:
    for campo in campi:
        if isinstance(d.get(campo), str):
            d[campo] = date.fromisoformat(d[campo])
    return d


def leggi_legislatura(percorso: Path) -> Legislatura:
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    fasi = []
    for f in dati["fasi"]:
        _date(f, "data_presentazione", "data_stato")
        f["date_legge"] = [date.fromisoformat(d) for d in f["date_legge"]]
        fasi.append(Fase(**f))
    return Legislatura(
        dati["numero"], fasi, [Iniziativa(**i) for i in dati["iniziative"]],
        [Votazione(**_date(v, "data")) for v in dati["votazioni"]], dati.get("votazioni_scartate", 0),
        dati.get("con_voti", True),
    )


def leggi_persone(percorso: Path) -> Persone:
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    return Persone(
        [Senatore(**s) for s in dati["senatori"]],
        [Adesione(**_date(a, "inizio", "fine")) for a in dati["adesioni"]],
        [Denominazione(**_date(d, "inizio", "fine")) for d in dati["denominazioni"]],
    )


def per_iter(fasi: list[Fase]) -> dict[str, list[Fase]]:
    gruppi: dict[str, list[Fase]] = defaultdict(list)
    for fase in fasi:
        gruppi[fase.id_ddl].append(fase)
    for elenco in gruppi.values():
        elenco.sort(key=lambda f: (f.progressivo, f.data_presentazione or date.min, f.id))
    return dict(gruppi)
