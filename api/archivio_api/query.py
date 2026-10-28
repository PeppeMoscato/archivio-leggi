"""Le query dell'API. Solo letture: le scritture le fanno le pipeline di `ingest/`."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import psycopg
from psycopg import sql

# Le colonne di `LeggeSintesi`, dalla vista legge_estesa (alias l).
COLONNE_SINTESI = sql.SQL(
    "l.urn, l.tipo, l.numero, l.data, l.titolo, l.stato, l.data_abrogazione, l.governo_id, "
    "l.link_normattiva, l.numero_modifiche, l.modificata"
)

# Ricerca full text sul titolo, con lo stemming italiano di Postgres ("amministrativo" trova "amministrativi").
# L'espressione è uguale a quella dell'indice legge_titolo_fts di schema.sql: se cambia una, cambia l'altra.
VETTORE_TITOLO = sql.SQL("to_tsvector('italian', l.titolo)")
QUERY_TESTO = sql.SQL("websearch_to_tsquery('italian', {})")

# Numero/anno scritto come si cita una legge: "3/2003", "L. 3/2003", "d.lgs. 81/2008".
NUMERO_ANNO = re.compile(r"\b(\d{1,5})\s*/\s*(\d{4})\b")
ABBREVIAZIONI = {
    "l": "legge",
    "legge": "legge",
    "lcost": "legge costituzionale",
    "leggecost": "legge costituzionale",
    "leggecostituzionale": "legge costituzionale",
    "dl": "decreto-legge",
    "decretolegge": "decreto-legge",
    "dlgs": "decreto legislativo",
    "dleg": "decreto legislativo",
    "dlegs": "decreto legislativo",
    "decretolegislativo": "decreto legislativo",
}


@dataclass(frozen=True)
class CampoRicerca:
    """Cosa c'è dentro il campo di ricerca libero."""

    parole: str | None = None
    urn: str | None = None
    tipo: str | None = None
    numero: str | None = None
    anno: int | None = None


def interpreta(q: str | None) -> CampoRicerca:
    """Un URN si cerca per URN, "L. 3/2003" per tipo, numero e anno, il resto nel titolo."""
    q = (q or "").strip()
    if not q:
        return CampoRicerca()
    if q.lower().startswith("urn:nir:"):
        return CampoRicerca(urn=q)
    trovato = NUMERO_ANNO.search(q)
    if not trovato:
        return CampoRicerca(parole=q)
    resto = (q[: trovato.start()] + " " + q[trovato.end() :]).strip()
    # "n." prima del numero non conta: "legge n. 3/2003".
    chiave = re.sub(r"\bn\b\.?|[\s.,\-]", "", resto.lower())
    tipo = ABBREVIAZIONI.get(chiave)
    parole = None if tipo or not chiave else resto
    return CampoRicerca(parole=parole, tipo=tipo, numero=trovato.group(1), anno=int(trovato.group(2)))


@dataclass(frozen=True)
class Filtri:
    q: str | None = None
    tipo: str | None = None
    stato: str | None = None
    governo: str | None = None
    anno: int | None = None
    numero: str | None = None
    dal: date | None = None
    al: date | None = None
    modificata: bool | None = None


def _condizioni(filtri: Filtri, testo: CampoRicerca) -> tuple[list[sql.Composable], list[object]]:
    condizioni: list[sql.Composable] = []
    parametri: list[object] = []

    def aggiungi(condizione: str | sql.Composable, *valori: object) -> None:
        condizioni.append(sql.SQL(condizione) if isinstance(condizione, str) else condizione)
        parametri.extend(valori)

    if testo.urn:
        aggiungi("l.urn = %s", testo.urn)
    if testo.parole:
        aggiungi(sql.SQL("{} @@ {}").format(VETTORE_TITOLO, QUERY_TESTO.format(sql.Placeholder())), testo.parole)
    for tipo in {testo.tipo, filtri.tipo} - {None}:
        aggiungi("l.tipo = %s", tipo)
    for numero in {testo.numero, filtri.numero} - {None}:
        aggiungi("l.numero = %s", numero)
    for anno in {testo.anno, filtri.anno} - {None}:
        aggiungi("l.data >= %s AND l.data < %s", date(anno, 1, 1), date(anno + 1, 1, 1))
    if filtri.stato:
        aggiungi("l.stato = %s", filtri.stato)
    if filtri.governo:
        aggiungi("l.governo_id = %s", filtri.governo)
    if filtri.dal:
        aggiungi("l.data >= %s", filtri.dal)
    if filtri.al:
        aggiungi("l.data <= %s", filtri.al)
    if filtri.modificata is not None:
        aggiungi("l.modificata = %s", filtri.modificata)
    return condizioni, parametri


def cerca_leggi(
    conn: psycopg.Connection, filtri: Filtri, ordine: str | None, pagina: int, per_pagina: int
) -> tuple[int, list[dict]]:
    testo = interpreta(filtri.q)
    condizioni, parametri = _condizioni(filtri, testo)
    dove = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(condizioni) if condizioni else sql.SQL("")

    ordine = ordine or ("rilevanza" if testo.parole else "data_desc")
    parametri_ordine: list[object] = []
    if ordine == "rilevanza" and testo.parole:
        ordina = sql.SQL("ts_rank({}, {}) DESC, l.data DESC, l.urn").format(
            VETTORE_TITOLO, QUERY_TESTO.format(sql.Placeholder())
        )
        parametri_ordine.append(testo.parole)
    elif ordine == "data_asc":
        ordina = sql.SQL("l.data, l.urn")
    else:  # data_desc, o rilevanza senza parole da cercare
        ordina = sql.SQL("l.data DESC, l.urn DESC")

    with conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT count(*) AS totale FROM legge_estesa l") + dove, parametri)
        totale = cur.fetchone()["totale"]
        cur.execute(
            sql.SQL("SELECT {} FROM legge_estesa l{} ORDER BY {} LIMIT %s OFFSET %s").format(
                COLONNE_SINTESI, dove, ordina
            ),
            [*parametri, *parametri_ordine, per_pagina, (pagina - 1) * per_pagina],
        )
        return totale, cur.fetchall()


def legge(conn: psycopg.Connection, urn: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM legge_estesa WHERE urn = %s", (urn,))
        riga = cur.fetchone()
        if riga is None:
            return None
        riga["governo"] = None
        if riga["governo_id"]:
            cur.execute("SELECT id, nome, presidente, inizio, fine, fonte_url FROM governo WHERE id = %s", (riga["governo_id"],))
            riga["governo"] = cur.fetchone()
        cur.execute(
            """
            SELECT 'ricevute' AS verso, tipo, count(*) AS numero FROM relazione_normativa WHERE urn_destinazione = %(urn)s GROUP BY tipo
            UNION ALL
            SELECT 'disposte', tipo, count(*) FROM relazione_normativa WHERE urn_origine = %(urn)s GROUP BY tipo
            """,
            {"urn": urn},
        )
        conteggi: dict = {"ricevute": {}, "disposte": {}}
        for conteggio in cur.fetchall():
            conteggi[conteggio["verso"]][conteggio["tipo"]] = conteggio["numero"]
        cur.execute(
            """
            SELECT (SELECT count(*) FROM pronuncia_costituzionale WHERE urn_legge = %(urn)s) AS pronunce,
                   (SELECT count(*) FROM iter WHERE urn = %(urn)s) AS iter
            """,
            {"urn": urn},
        )
        conteggi.update(cur.fetchone())
        riga["conteggi"] = conteggi
        return riga


def esiste(conn: psycopg.Connection, urn: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM legge WHERE urn = %s", (urn,))
        return cur.fetchone() is not None


def relazioni(
    conn: psycopg.Connection, urn: str, verso: str, tipo: str | None, pagina: int, per_pagina: int
) -> tuple[int, list[dict]]:
    """Le relazioni in ordine di data (la timeline), con l'altro atto se è nell'archivio."""
    lato, altro = ("urn_destinazione", "urn_origine") if verso == "ricevute" else ("urn_origine", "urn_destinazione")
    dove = sql.SQL("r.{} = %s").format(sql.Identifier(lato))
    parametri: list[object] = [urn]
    if tipo:
        dove += sql.SQL(" AND r.tipo = %s")
        parametri.append(tipo)
    with conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT count(*) AS totale FROM relazione_normativa r WHERE ") + dove, parametri)
        totale = cur.fetchone()["totale"]
        cur.execute(
            sql.SQL(
                """
                SELECT r.id, r.tipo, r.data, r.urn_origine, r.urn_destinazione, r.articolo_origine,
                       r.articolo_destinazione, r.nota, r.origine_gazzetta_codice, r.origine_gazzetta_data,
                       CASE WHEN a.urn IS NULL THEN NULL
                            ELSE json_build_object('urn', a.urn, 'tipo', a.tipo, 'numero', a.numero, 'data', a.data, 'titolo', a.titolo)
                       END AS atto_collegato
                FROM relazione_normativa r
                LEFT JOIN legge a ON a.urn = r.{altro}
                WHERE {dove}
                ORDER BY r.data NULLS LAST, r.id
                LIMIT %s OFFSET %s
                """
            ).format(altro=sql.Identifier(altro), dove=dove),
            [*parametri, per_pagina, (pagina - 1) * per_pagina],
        )
        return totale, cur.fetchall()


def pronunce(conn: psycopg.Connection, urn: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, articolo, numero_sentenza, anno, data_gazzetta, gazzetta_codice, nota
            FROM pronuncia_costituzionale WHERE urn_legge = %s ORDER BY data_gazzetta NULLS LAST, id
            """,
            (urn,),
        )
        return cur.fetchall()


def iter_parlamentari(conn: psycopg.Connection, urn: str) -> list[dict]:
    """Gli iter della legge con le fasi (letture) e i firmatari di ogni fase."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT i.id, i.legislatura, i.natura, i.titolo, i.iniziativa, i.data_presentazione,
                   i.data_approvazione, i.fonte_url,
                   coalesce(json_agg(json_build_object(
                       'id', f.id, 'progressivo', f.progressivo, 'ramo', f.ramo, 'numero', f.numero,
                       'titolo', f.titolo, 'data_presentazione', f.data_presentazione, 'stato', f.stato,
                       'data_stato', f.data_stato, 'fonte_url', f.fonte_url,
                       'numero_votazioni', (SELECT count(*) FROM votazione v WHERE v.fase_id = f.id),
                       'firmatari', (
                           SELECT coalesce(json_agg(json_build_object(
                               'nome', s.nome, 'tipo', s.tipo, 'primo_firmatario', s.primo_firmatario,
                               'parlamentare_id', s.parlamentare_id
                           ) ORDER BY s.primo_firmatario DESC, s.id), '[]')
                           FROM firmatario s WHERE s.fase_id = f.id
                       )
                   ) ORDER BY f.progressivo) FILTER (WHERE f.id IS NOT NULL), '[]') AS fasi
            FROM iter i
            LEFT JOIN fase_iter f ON f.iter_id = i.id
            WHERE i.urn = %s
            GROUP BY i.id
            ORDER BY i.data_presentazione NULLS LAST, i.id
            """,
            (urn,),
        )
        return cur.fetchall()


def votazioni(
    conn: psycopg.Connection, urn: str, tipo: str | None, pagina: int, per_pagina: int
) -> tuple[int, list[dict]]:
    """Le votazioni d'Aula sulle fasi degli iter della legge, in ordine di data."""
    dove = sql.SQL("i.urn = %s")
    parametri: list[object] = [urn]
    if tipo:
        dove += sql.SQL(" AND v.tipo = %s")
        parametri.append(tipo)
    da = sql.SQL("FROM votazione v JOIN fase_iter f ON f.id = v.fase_id JOIN iter i ON i.id = f.iter_id WHERE ")
    with conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT count(*) AS totale ") + da + dove, parametri)
        totale = cur.fetchone()["totale"]
        cur.execute(
            sql.SQL(
                """
                SELECT v.id, v.fase_id, v.ramo, v.legislatura, v.data, v.tipo, v.descrizione, v.esito,
                       v.presenti, v.votanti, v.favorevoli, v.contrari, v.astenuti, v.maggioranza,
                       cardinality(v.voti_favorevoli) + cardinality(v.voti_contrari) + cardinality(v.voti_astenuti) > 0
                           AS nominale,
                       v.fonte_url
                """
            )
            + da
            + dove
            + sql.SQL(" ORDER BY v.data NULLS LAST, v.id LIMIT %s OFFSET %s"),
            [*parametri, per_pagina, (pagina - 1) * per_pagina],
        )
        return totale, cur.fetchall()


def governi(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT g.id, g.nome, g.presidente, g.inizio, g.fine, g.fonte_url,
                   (SELECT count(*) FROM legge l WHERE l.governo_id = g.id) AS numero_atti,
                   (SELECT coalesce(json_agg(json_build_object('partito', p.partito, 'ruolo', p.ruolo, 'fonte_url', p.fonte_url)
                                    ORDER BY p.ruolo, p.partito), '[]')
                    FROM governo_partito p WHERE p.governo_id = g.id) AS partiti
            FROM governo g
            ORDER BY g.inizio
            """
        )
        return cur.fetchall()
