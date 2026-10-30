"""Forma delle risposte. I nomi dei campi sono quelli di `docs/01_schema_dati.md`."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Tipo(StrEnum):
    legge = "legge"
    legge_costituzionale = "legge costituzionale"
    decreto_legge = "decreto-legge"
    decreto_legislativo = "decreto legislativo"


class Stato(StrEnum):
    vigente = "vigente"
    abrogata = "abrogata"
    decaduta = "decaduta"


class TipoRelazione(StrEnum):
    modifica = "modifica"
    abroga = "abroga"
    abroga_parziale = "abroga_parziale"
    converte = "converte"
    attua = "attua"
    proroga = "proroga"
    delega = "delega"


class Verso(StrEnum):
    ricevute = "ricevute"  # la legge subisce: urn_destinazione = la legge
    disposte = "disposte"  # la legge dispone: urn_origine = la legge


class Ordine(StrEnum):
    rilevanza = "rilevanza"
    data_desc = "data_desc"
    data_asc = "data_asc"


class Pagina(BaseModel, Generic[T]):
    totale: int
    pagina: int
    per_pagina: int
    risultati: list[T]


class LeggeSintesi(BaseModel):
    urn: str
    tipo: str
    numero: str
    data: date
    titolo: str
    stato: str
    data_abrogazione: date | None
    governo_id: str | None
    link_normattiva: str
    numero_modifiche: int
    modificata: bool


class Governo(BaseModel):
    id: str
    nome: str
    presidente: str
    inizio: date
    fine: date | None
    fonte_url: str


class PartitoGoverno(BaseModel):
    partito: str
    ruolo: str
    fonte_url: str


class GovernoConAtti(Governo):
    numero_atti: int
    partiti: list[PartitoGoverno]


class Conteggi(BaseModel):
    """Quante relazioni la legge riceve e dispone, per tipo; pronunce e iter parlamentari."""

    ricevute: dict[str, int]
    disposte: dict[str, int]
    pronunce: int
    iter: int


class Premessa(BaseModel):
    """Le premesse del testo originale di un decreto-legge o di un decreto legislativo, così come sono scritte."""

    motivazioni: list[str] = Field(description='Le frasi "Ritenuta la straordinaria necessità ed urgenza di...", in ordine')
    citazioni: list[str] = Field(description='Le frasi "Visto..." e "Acquisito il parere...": basi giuridiche, delega, pareri')
    proposta: str | None = Field(description='"Sulla proposta del Presidente del Consiglio dei ministri ..."')
    fonte_url: str


class LeggeDettaglio(LeggeSintesi):
    materia: str | None
    data_entrata_vigore: date | None
    gazzetta_data: date | None
    gazzetta_numero: int | None
    gazzetta_codice: str | None
    aggiornato_il: datetime
    governo: Governo | None
    premessa: Premessa | None = Field(description="Solo decreti-legge e decreti legislativi; le leggi non hanno premesse")
    conteggi: Conteggi


class AttoCollegato(BaseModel):
    """L'altro atto della relazione, se è nell'archivio."""

    urn: str
    tipo: str
    numero: str
    data: date
    titolo: str


class Relazione(BaseModel):
    id: int
    tipo: str
    data: date | None
    urn_origine: str | None
    urn_destinazione: str
    articolo_origine: str | None
    articolo_destinazione: str | None
    nota: str
    origine_gazzetta_codice: str | None
    origine_gazzetta_data: date | None
    atto_collegato: AttoCollegato | None


class Pronuncia(BaseModel):
    id: int
    articolo: str | None
    numero_sentenza: str | None
    anno: int | None
    data_gazzetta: date | None
    gazzetta_codice: str | None
    nota: str


class Firmatario(BaseModel):
    nome: str
    tipo: str | None
    primo_firmatario: bool
    parlamentare_id: int | None


class Fase(BaseModel):
    id: str
    progressivo: int
    ramo: str
    numero: str
    titolo: str | None
    data_presentazione: date | None
    stato: str | None
    data_stato: date | None
    fonte_url: str
    testo_presentato: str | None = Field(
        default=None, description="Il testo presentato, con la relazione illustrativa, come lo identifica la fonte (URN del Senato)"
    )
    numero_votazioni: int
    firmatari: list[Firmatario]


class Iter(BaseModel):
    id: str
    legislatura: int
    natura: str
    titolo: str
    iniziativa: str | None
    data_presentazione: date | None
    data_approvazione: date | None
    fonte_url: str
    fasi: list[Fase]


class VotoGruppo(BaseModel):
    """Come ha votato un gruppo parlamentare: ogni parlamentare conta nel gruppo a cui aderiva il giorno del voto."""

    gruppo_id: str | None = Field(description="Vuoto per chi quel giorno non risulta iscritto a un gruppo")
    nome: str | None = Field(description="La denominazione del gruppo valida alla data del voto")
    sigla: str | None
    favorevoli: int
    contrari: int
    astenuti: int


class Votazione(BaseModel):
    """Totali di una votazione d'Aula. Gli elenchi dei voti dei singoli non sono qui."""

    id: str
    fase_id: str
    ramo: str
    legislatura: int
    data: date | None
    tipo: str
    descrizione: str
    esito: str | None
    presenti: int | None
    votanti: int | None
    favorevoli: int | None
    contrari: int | None
    astenuti: int | None
    maggioranza: int | None
    nominale: bool
    fonte_url: str
    gruppi: list[VotoGruppo] | None = Field(
        None, description="Voto per gruppo, solo se richiesto (gruppi=true); vuoto se il voto non è nominale"
    )


class VotazioneDettaglio(Votazione):
    urn: str | None = Field(description="La legge a cui porta l'iter, se è nell'archivio")
    fase_numero: str = Field(description="Il ddl votato, come lo scrive la fonte (S.795, C.2122-BIS)")
    gruppi: list[VotoGruppo]
