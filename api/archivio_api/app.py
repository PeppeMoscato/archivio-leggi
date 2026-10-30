"""L'applicazione FastAPI: ricerca e dettaglio delle leggi, in sola lettura.

    DATABASE_URL=... uvicorn archivio_api.app:app --reload

Variabili d'ambiente:
- `DATABASE_URL` (obbligatoria): il database Neon, meglio con un ruolo di sola lettura.
- `CORS_ORIGINI` (facoltativa): origini del frontend separate da virgole, es. `https://archivio-leggi.vercel.app`.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware

from archivio_api import query
from archivio_api.db import connessione, crea_pool
from archivio_api.modelli import (
    GovernoConAtti,
    Iter,
    LeggeDettaglio,
    LeggeSintesi,
    Ordine,
    Pagina,
    Pronuncia,
    Relazione,
    Stato,
    Tipo,
    TipoRelazione,
    Verso,
    Votazione,
    VotazioneDettaglio,
)

ATTRIBUZIONE = (
    "Fonte: Normattiva (https://www.normattiva.it), Istituto Poligrafico e Zecca dello Stato, in licenza CC BY 4.0. "
    "Testo non autentico e gratuito: l'unico testo ufficiale è quello pubblicato sulla Gazzetta Ufficiale a mezzo stampa. "
    "Iter e votazioni: Senato della Repubblica (https://dati.senato.it), licenza su "
    "https://dati.senato.it/sito/19?testo_generico=24; Camera dei deputati (https://dati.camera.it), "
    "in licenza CC BY-SA 4.0: i dati della Camera, anche rielaborati, si riusano con la stessa licenza."
)

Connessione = Annotated[psycopg.Connection, Depends(connessione)]
Urn = Annotated[str, Path(description="URN NIR di Normattiva, es. urn:nir:stato:legge:1990-08-07;241")]
NumeroPagina = Annotated[int, Query(ge=1, description="Pagina, da 1")]
PerPagina = Annotated[int, Query(ge=1, le=100, description="Risultati per pagina, al massimo 100")]


@asynccontextmanager
async def ciclo_di_vita(app: FastAPI):
    pool = crea_pool(os.environ["DATABASE_URL"])
    pool.open()
    app.state.pool = pool
    try:
        yield
    finally:
        pool.close()


app = FastAPI(
    title="Archivio Leggi",
    version="0.1.0",
    description="Le leggi statali italiane dal 1990: stato, modifiche, abrogazioni, iter e voti in Parlamento.\n\n"
    + ATTRIBUZIONE,
    lifespan=ciclo_di_vita,
)

if origini := [origine.strip() for origine in os.environ.get("CORS_ORIGINI", "").split(",") if origine.strip()]:
    app.add_middleware(CORSMiddleware, allow_origins=origini, allow_methods=["GET"])


def _legge_o_404(conn: psycopg.Connection, urn: str) -> None:
    if not query.esiste(conn, urn):
        raise HTTPException(404, f"Legge non trovata: {urn}")


@app.get("/", include_in_schema=False)
def radice() -> dict:
    return {"nome": "Archivio Leggi", "documentazione": "/docs", "fonti": ATTRIBUZIONE}


@app.get("/salute", summary="Il servizio e il database rispondono")
def salute(conn: Connessione) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) AS atti FROM legge")
        return {"stato": "ok", "atti": cur.fetchone()["atti"]}


@app.get("/leggi", summary="Cerca le leggi", response_model=Pagina[LeggeSintesi])
def cerca_leggi(
    conn: Connessione,
    q: Annotated[
        str | None,
        Query(
            max_length=200,
            description='Parole nel titolo ("fumo locali pubblici", "-abrogata" esclude, "frase esatta" fra virgolette), '
            'una citazione ("L. 3/2003", "d.lgs. 81/2008") o un URN',
        ),
    ] = None,
    tipo: Tipo | None = None,
    stato: Stato | None = None,
    governo: Annotated[str | None, Query(description="id del governo, es. berlusconi-2 (vedi /governi)")] = None,
    anno: Annotated[int | None, Query(ge=1800, le=2100, description="Anno di emanazione")] = None,
    numero: Annotated[str | None, Query(max_length=20)] = None,
    dal: Annotated[date | None, Query(description="Emanata dal (compreso)")] = None,
    al: Annotated[date | None, Query(description="Emanata fino al (compreso)")] = None,
    modificata: Annotated[bool | None, Query(description="Ha ricevuto modifiche, abrogazioni parziali o proroghe")] = None,
    ordine: Annotated[Ordine | None, Query(description="Predefinito: rilevanza se c'è del testo, altrimenti data_desc")] = None,
    pagina: NumeroPagina = 1,
    per_pagina: PerPagina = 20,
) -> dict:
    filtri = query.Filtri(q, tipo, stato, governo, anno, numero, dal, al, modificata)
    totale, risultati = query.cerca_leggi(conn, filtri, ordine, pagina, per_pagina)
    return {"totale": totale, "pagina": pagina, "per_pagina": per_pagina, "risultati": risultati}


@app.get("/leggi/{urn}", summary="Dettaglio di una legge", response_model=LeggeDettaglio)
def dettaglio_legge(conn: Connessione, urn: Urn) -> dict:
    if (riga := query.legge(conn, urn)) is None:
        raise HTTPException(404, f"Legge non trovata: {urn}")
    return riga


@app.get(
    "/leggi/{urn}/relazioni",
    summary="Modifiche, abrogazioni e conversioni ricevute o disposte dalla legge, in ordine di data",
    response_model=Pagina[Relazione],
)
def relazioni_legge(
    conn: Connessione,
    urn: Urn,
    verso: Annotated[Verso, Query(description="ricevute: la legge le subisce; disposte: la legge le dispone")] = Verso.ricevute,
    tipo: TipoRelazione | None = None,
    pagina: NumeroPagina = 1,
    per_pagina: PerPagina = 50,
) -> dict:
    _legge_o_404(conn, urn)
    totale, risultati = query.relazioni(conn, urn, verso, tipo, pagina, per_pagina)
    return {"totale": totale, "pagina": pagina, "per_pagina": per_pagina, "risultati": risultati}


@app.get("/leggi/{urn}/pronunce", summary="Sentenze di illegittimità della Corte costituzionale", response_model=list[Pronuncia])
def pronunce_legge(conn: Connessione, urn: Urn) -> list[dict]:
    _legge_o_404(conn, urn)
    return query.pronunce(conn, urn)


@app.get("/leggi/{urn}/iter", summary="Iter parlamentare: letture, firmatari", response_model=list[Iter])
def iter_legge(conn: Connessione, urn: Urn) -> list[dict]:
    _legge_o_404(conn, urn)
    return query.iter_parlamentari(conn, urn)


@app.get("/leggi/{urn}/votazioni", summary="Votazioni d'Aula sulla legge, in ordine di data", response_model=Pagina[Votazione])
def votazioni_legge(
    conn: Connessione,
    urn: Urn,
    tipo: Annotated[
        str | None, Query(pattern="^(finale|fiducia|articolo|emendamento|pregiudiziale|altro)$")
    ] = None,
    gruppi: Annotated[bool, Query(description="Aggiunge a ogni votazione il voto per gruppo parlamentare")] = False,
    pagina: NumeroPagina = 1,
    per_pagina: PerPagina = 50,
) -> dict:
    _legge_o_404(conn, urn)
    totale, risultati = query.votazioni(conn, urn, tipo, gruppi, pagina, per_pagina)
    return {"totale": totale, "pagina": pagina, "per_pagina": per_pagina, "risultati": risultati}


# `:path` perché gli id delle votazioni contengono "/" (senato:14/1).
@app.get(
    "/votazioni/{votazione_id:path}",
    summary="Una votazione d'Aula con il voto per gruppo parlamentare",
    response_model=VotazioneDettaglio,
)
def dettaglio_votazione(
    conn: Connessione,
    votazione_id: Annotated[str, Path(description="id della votazione, es. senato:14/1 (vedi /leggi/{urn}/votazioni)")],
) -> dict:
    if (riga := query.votazione(conn, votazione_id)) is None:
        raise HTTPException(404, f"Votazione non trovata: {votazione_id}")
    return riga


@app.get("/governi", summary="I governi dal 1989, con il numero di atti e i partiti", response_model=list[GovernoConAtti])
def elenco_governi(conn: Connessione) -> list[dict]:
    return query.governi(conn)
