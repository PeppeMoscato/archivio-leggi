"""Caricamento di iter, votazioni, parlamentari e gruppi di Senato e Camera (Task 1.2).

Legge i file scritti da `senato.py` e `camera.py` e li porta nelle tabelle
della v1.2 (`docs/01_schema_dati.md`). Ogni legislatura si riscrive per intero,
così la pipeline si può rilanciare: al Senato si aggiornano iter e fasi e si
riscrivono firmatari e votazioni del Senato; alla Camera si riscrivono le sue
votazioni (e, per le legislature X-XII, i suoi iter).

Le votazioni della Camera dalla XIII legislatura stanno sulle fasi Camera degli
iter del Senato: si carica prima il Senato, poi la Camera. Gli id delle fasi del
Senato non cambiano fra un caricamento e l'altro, quindi ricaricare il Senato
non cancella le votazioni della Camera (a meno che la fase sparisca dalla fonte).

Gli iter si collegano alle leggi già caricate da Normattiva con tipo, numero e
data: se la legge non c'è (o il database è vuoto) `urn` resta vuoto.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import psycopg

from archivio import camera, db, governi
from archivio.camera import LegislaturaCamera, PersoneCamera
from archivio.pipeline import Rapporto
from archivio.senato import (
    DDL, GRUPPO, INIZIATIVE, SENATORE, VOTAZIONE, Fase, Iniziativa, Legislatura, Persone, Votazione, iniziativa,
    leggi_legislatura, leggi_persone, natura, numero_senza_ramo, per_iter, scheda_iter, tipo_votazione,
)

RAMI = {"C": "camera", "S": "senato"}
TABELLE = ("iter", "fase_iter", "firmatario", "votazione", "parlamentare", "gruppo", "denominazione_gruppo", "adesione_gruppo")


def codice(iri: str, prefisso: str) -> str:
    """L'identificativo nel database: il ramo davanti all'identificativo della fonte (`senato:274`)."""
    return "senato:" + iri.removeprefix(prefisso)


# --- Collegamento con le leggi di Normattiva -----------------------------------


@dataclass
class IndiceLeggi:
    esatte: dict[tuple[str, str, date], str]
    per_anno: dict[tuple[str, str, int], list[str]]

    @classmethod
    def da_righe(cls, righe) -> IndiceLeggi:
        esatte, per_anno = {}, defaultdict(list)
        for urn, tipo, numero, giorno in righe:
            esatte[(tipo, numero, giorno)] = urn
            per_anno[(tipo, numero, giorno.year)].append(urn)
        return cls(esatte, dict(per_anno))

    def __len__(self) -> int:
        return len(self.esatte)


def tipo_legge(natura_iter: str) -> str:
    return "legge costituzionale" if natura_iter == "costituzionale" else "legge"


def risolvi_urn(
    tipo: str, numeri: list[int], date_legge: list[date], approvazione: date | None, indice: IndiceLeggi
) -> tuple[str | None, int | None, date | None]:
    """URN, numero e data della legge di un iter.

    Prima numero e data come li dà la fonte; poi numero e anno della data;
    senza data, numero e anno dell'approvazione definitiva (o il successivo,
    per le leggi approvate a fine anno). Se più leggi combaciano, nessuna.
    """
    for numero in numeri:
        for giorno in date_legge:
            if urn := indice.esatte.get((tipo, str(numero), giorno)):
                return urn, numero, giorno
    anni = [(g.year, g) for g in date_legge] or (
        [(approvazione.year, None), (approvazione.year + 1, None)] if approvazione else []
    )
    for numero in numeri:
        for anno, giorno in anni:
            candidati = indice.per_anno.get((tipo, str(numero), anno), [])
            if len(candidati) == 1:
                return candidati[0], numero, giorno
    return None, (numeri[0] if numeri else None), (date_legge[0] if date_legge else None)


# --- Righe delle tabelle ---------------------------------------------------------


@dataclass
class RigaIter:
    id: str
    urn: str | None
    legislatura: int
    natura: str
    titolo: str
    iniziativa: str | None
    data_presentazione: date | None
    data_approvazione: date | None
    numero_legge: int | None
    data_legge: date | None
    fonte_url: str


def riga_iter(legislatura: int, fasi: list[Fase], iniziative: list[Iniziativa], indice: IndiceLeggi) -> RigaIter:
    """Un iter dalle sue fasi, già in ordine: titolo e natura dell'ultima lettura, iniziativa della prima."""
    prima, ultima = fasi[0], fasi[-1]
    finale = next((f for f in reversed(fasi) if f.numeri_legge), ultima)
    tipi_prima = [i.tipo for i in iniziative if i.fase_id == prima.id]
    natura_iter = natura(ultima.natura)
    urn, numero, giorno = risolvi_urn(tipo_legge(natura_iter), finale.numeri_legge, finale.date_legge, finale.data_stato, indice)
    return RigaIter(
        codice(prima.id_ddl, ""), urn, legislatura, natura_iter, ultima.titolo, iniziativa(tipi_prima),
        prima.data_presentazione, finale.data_stato, numero, giorno, scheda_iter(legislatura, prima.id_ddl),
    )


def elenchi_voti(votazione: Votazione, ids: dict[str, int]) -> tuple[list[int], list[int], list[int], int]:
    """I tre elenchi di `parlamentare.id` e quanti senatori non si trovano in `ids`."""
    mancanti = 0
    elenchi = []
    for chiave in ("favorevoli", "contrari", "astenuti"):
        elenco = []
        for senatore in votazione.voti.get(chiave, []):
            if (numero := ids.get(codice(senatore, SENATORE))) is None:
                mancanti += 1
            else:
                elenco.append(numero)
        elenchi.append(sorted(elenco))
    return elenchi[0], elenchi[1], elenchi[2], mancanti


# --- Scrittura ---------------------------------------------------------------------


def indice_leggi(conn: psycopg.Connection) -> IndiceLeggi:
    with conn.cursor() as cur:
        cur.execute("SELECT urn, tipo, numero, data FROM legge WHERE tipo IN ('legge', 'legge costituzionale')")
        return IndiceLeggi.da_righe(cur.fetchall())


def salva_parlamentari(conn: psycopg.Connection, ramo: str, righe: list[tuple[str, str | None, str | None, str]]) -> dict[str, int]:
    """Inserisce o aggiorna i parlamentari (codice, nome, cognome, fonte) e restituisce codice → id per tutto il ramo."""
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO parlamentare (codice, ramo, nome, cognome, fonte_url) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (codice) DO UPDATE SET nome = coalesce(EXCLUDED.nome, parlamentare.nome),
                cognome = coalesce(EXCLUDED.cognome, parlamentare.cognome)
            """,
            [(c, ramo, nome, cognome, fonte) for c, nome, cognome, fonte in righe],
        )
        cur.execute("SELECT codice, id FROM parlamentare WHERE ramo = %s", (ramo,))
        ids = dict(cur.fetchall())
    conn.commit()
    return ids


def salva_senatori(conn: psycopg.Connection, senatori: list[tuple[str, str | None, str | None]]) -> dict[str, int]:
    """Inserisce o aggiorna i senatori (codice, nome, cognome) e restituisce codice → id per tutto il Senato."""
    return salva_parlamentari(conn, "senato", [(c, nome, cognome, SENATORE + c.removeprefix("senato:")) for c, nome, cognome in senatori])


def salva_persone(conn: psycopg.Connection, persone: Persone, rapporto: Rapporto) -> dict[str, int]:
    ids = salva_senatori(conn, [(codice(s.id, SENATORE), s.nome, s.cognome) for s in persone.senatori])
    # Nome e sigla del gruppo: la denominazione più recente.
    gruppi: dict[str, tuple[str, str | None]] = {}
    for d in sorted(persone.denominazioni, key=lambda d: d.inizio):
        gruppi[d.gruppo] = (d.nome, d.sigla)
    for a in persone.adesioni:
        gruppi.setdefault(a.gruppo, (codice(a.gruppo, GRUPPO), None))
    if senza_scheda := {a.senatore for a in persone.adesioni} - {s.id for s in persone.senatori}:
        ids = salva_senatori(conn, [(codice(s, SENATORE), None, None) for s in sorted(senza_scheda)])
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO gruppo (id, ramo, nome, sigla) VALUES (%s, 'senato', %s, %s)
            ON CONFLICT (id) DO UPDATE SET nome = EXCLUDED.nome, sigla = EXCLUDED.sigla
            """,
            [(codice(g, GRUPPO), nome, sigla) for g, (nome, sigla) in gruppi.items()],
        )
        cur.execute("DELETE FROM denominazione_gruppo WHERE gruppo_id LIKE 'senato:%'")
        cur.executemany(
            "INSERT INTO denominazione_gruppo (gruppo_id, inizio, fine, nome, sigla) VALUES (%s, %s, %s, %s, %s)",
            [(codice(d.gruppo, GRUPPO), d.inizio, d.fine, d.nome, d.sigla) for d in persone.denominazioni],
        )
        cur.execute("DELETE FROM adesione_gruppo WHERE gruppo_id LIKE 'senato:%'")
        cur.executemany(
            "INSERT INTO adesione_gruppo (parlamentare_id, gruppo_id, inizio, fine, carica) VALUES (%s, %s, %s, %s, %s)",
            [(ids[codice(a.senatore, SENATORE)], codice(a.gruppo, GRUPPO), a.inizio, a.fine, a.carica) for a in persone.adesioni],
        )
    conn.commit()
    rapporto.aggiungi(
        f"Senatori: {len(persone.senatori)}; gruppi: {len(gruppi)} ({len(persone.denominazioni)} denominazioni); "
        f"adesioni: {len(persone.adesioni)}"
    )
    return ids


def salva_legislatura(
    conn: psycopg.Connection, leg: Legislatura, ids: dict[str, int], indice: IndiceLeggi, rapporto: Rapporto
) -> None:
    # Senatori citati da voti o firme ma assenti dall'elenco: si aggiungono senza nome.
    citati = {codice(s, SENATORE) for v in leg.votazioni for elenco in v.voti.values() for s in elenco}
    citati |= {codice(i.senatore, SENATORE) for i in leg.iniziative if i.senatore}
    if nuovi := citati - ids.keys():
        ids |= salva_senatori(conn, [(c, None, None) for c in sorted(nuovi)])

    iter_righe, fasi_righe = [], []
    iter_di_fase: dict[str, str] = {}
    for id_ddl, fasi in per_iter(leg.fasi).items():
        riga = riga_iter(leg.numero, fasi, leg.iniziative, indice)
        iter_righe.append(riga)
        for f in fasi:
            iter_di_fase[f.id] = riga.id
            fasi_righe.append((
                codice(f.id, DDL), riga.id, f.progressivo, RAMI.get(f.ramo.upper(), f.ramo.lower()), f.numero, f.titolo,
                f.data_presentazione, f.stato, f.data_stato, f.id,
            ))
    firmatari = [
        (codice(i.fase_id, DDL), i.nome, INIZIATIVE.get((i.tipo or "").strip().lower(), i.tipo), i.primo_firmatario,
         ids.get(codice(i.senatore, SENATORE)) if i.senatore else None)
        for i in leg.iniziative if i.fase_id in iter_di_fase
    ]
    tipi: Counter = Counter()
    voti_totali = mancanti_totali = discordanti = 0
    votazioni = []
    for v in leg.votazioni:
        favorevoli, contrari, astenuti, mancanti = elenchi_voti(v, ids)
        tipo = tipo_votazione(v.descrizione)
        tipi[tipo] += 1
        voti_totali += len(favorevoli) + len(contrari) + len(astenuti)
        mancanti_totali += mancanti
        nominale = favorevoli or contrari or astenuti
        if nominale and (len(favorevoli), len(contrari), len(astenuti)) != (v.favorevoli, v.contrari, v.astenuti):
            discordanti += 1
        votazioni.append((
            codice(v.id, VOTAZIONE), codice(v.fasi_oggetto[0], DDL), leg.numero, v.data, tipo, v.descrizione, v.esito,
            v.presenti, v.votanti, v.favorevoli, v.contrari, v.astenuti, v.maggioranza, favorevoli, contrari, astenuti, v.id,
        ))

    with conn.cursor() as cur:
        # Iter e fasi si aggiornano invece di cancellarli: sulle fasi Camera stanno le votazioni della Camera.
        cur.execute("DELETE FROM votazione WHERE id LIKE 'senato:%%' AND legislatura = %s", (leg.numero,))
        cur.execute(
            """
            DELETE FROM firmatario WHERE fase_id IN (
                SELECT f.id FROM fase_iter f JOIN iter i ON i.id = f.iter_id WHERE i.id LIKE 'senato:%%' AND i.legislatura = %s)
            """,
            (leg.numero,),
        )
        cur.executemany(
            """
            INSERT INTO iter (id, urn, legislatura, natura, titolo, iniziativa, data_presentazione, data_approvazione,
                numero_legge, data_legge, fonte_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET urn = EXCLUDED.urn, legislatura = EXCLUDED.legislatura, natura = EXCLUDED.natura,
                titolo = EXCLUDED.titolo, iniziativa = EXCLUDED.iniziativa, data_presentazione = EXCLUDED.data_presentazione,
                data_approvazione = EXCLUDED.data_approvazione, numero_legge = EXCLUDED.numero_legge,
                data_legge = EXCLUDED.data_legge, fonte_url = EXCLUDED.fonte_url
            """,
            [(r.id, r.urn, r.legislatura, r.natura, r.titolo, r.iniziativa, r.data_presentazione, r.data_approvazione,
              r.numero_legge, r.data_legge, r.fonte_url) for r in iter_righe],
        )
        cur.executemany(
            """
            INSERT INTO fase_iter (id, iter_id, progressivo, ramo, numero, titolo, data_presentazione, stato, data_stato, fonte_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET iter_id = EXCLUDED.iter_id, progressivo = EXCLUDED.progressivo, ramo = EXCLUDED.ramo,
                numero = EXCLUDED.numero, titolo = EXCLUDED.titolo, data_presentazione = EXCLUDED.data_presentazione,
                stato = EXCLUDED.stato, data_stato = EXCLUDED.data_stato, fonte_url = EXCLUDED.fonte_url
            """,
            fasi_righe,
        )
        # Iter e fasi della legislatura che la fonte non dà più.
        cur.execute(
            """
            DELETE FROM fase_iter WHERE iter_id IN (SELECT id FROM iter WHERE id LIKE 'senato:%%' AND legislatura = %s)
                AND NOT (id = ANY(%s))
            """,
            (leg.numero, [f[0] for f in fasi_righe]),
        )
        cur.execute(
            "DELETE FROM iter WHERE id LIKE 'senato:%%' AND legislatura = %s AND NOT (id = ANY(%s))",
            (leg.numero, [r.id for r in iter_righe]),
        )
        cur.executemany(
            "INSERT INTO firmatario (fase_id, nome, tipo, primo_firmatario, parlamentare_id) VALUES (%s, %s, %s, %s, %s)",
            firmatari,
        )
        cur.executemany(
            """
            INSERT INTO votazione (id, fase_id, ramo, legislatura, data, tipo, descrizione, esito, presenti, votanti,
                favorevoli, contrari, astenuti, maggioranza, voti_favorevoli, voti_contrari, voti_astenuti, fonte_url)
            VALUES (%s, %s, 'senato', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            votazioni,
        )
    conn.commit()

    con_urn = sum(1 for r in iter_righe if r.urn)
    con_finale = len({iter_di_fase[v.fasi_oggetto[0]] for v in leg.votazioni if tipo_votazione(v.descrizione) == "finale"})
    rapporto.aggiungi(f"Legislatura {leg.numero}: {len(iter_righe)} iter diventati legge, {len(fasi_righe)} fasi, {len(firmatari)} firmatari")
    rapporto.aggiungi(f"- collegati a una legge di Normattiva: {con_urn} (non trovati: {len(iter_righe) - con_urn})")
    rapporto.aggiungi(f"- con una votazione finale nominale al Senato: {con_finale}")
    rapporto.aggiungi(f"- votazioni: {len(votazioni)} ({', '.join(f'{t} {n}' for t, n in tipi.most_common())})")
    rapporto.aggiungi(f"- votazioni su altri ddl o non collegate (non caricate): {leg.votazioni_scartate}")
    rapporto.aggiungi(f"- voti individuali: {voti_totali}; senatori non trovati: {mancanti_totali}")
    rapporto.aggiungi(f"- votazioni nominali con elenchi diversi dai totali della fonte: {discordanti}")


def salva_partiti(conn: psycopg.Connection) -> int:
    partiti = governi.carica_partiti()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM governo_partito")
        cur.executemany(
            "INSERT INTO governo_partito (governo_id, partito, ruolo, fonte_url) VALUES (%s, %s, %s, %s)",
            [(p.governo_id, p.partito, p.ruolo, p.fonte_url) for p in partiti],
        )
    conn.commit()
    return len(partiti)


def dimensioni(conn: psycopg.Connection) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT relname, pg_total_relation_size(oid) FROM pg_class WHERE relname = ANY(%s) AND relkind = 'r' ORDER BY 2 DESC",
            (list(TABELLE),),
        )
        tabelle = cur.fetchall()
        cur.execute("SELECT pg_database_size(current_database())")
        (totale,) = cur.fetchone()
    mb = lambda byte: f"{byte / 1_048_576:.1f} MB"  # noqa: E731
    return [f"Spazio: database {mb(totale)}; " + ", ".join(f"{nome} {mb(byte)}" for nome, byte in tabelle)]


def carica_senato(conn: psycopg.Connection, cartella: Path) -> Rapporto:
    rapporto = Rapporto()
    db.crea_schema(conn)
    db.salva_governi(conn, governi.carica())
    rapporto.aggiungi(f"Partiti dei governi: {salva_partiti(conn)} righe")
    ids = salva_persone(conn, leggi_persone(cartella / "senato_persone.json"), rapporto)
    indice = indice_leggi(conn)
    rapporto.aggiungi(f"Leggi e leggi costituzionali nel database per il collegamento: {len(indice)}")
    for file in sorted(cartella.glob("senato_[0-9]*.json"), key=lambda f: int(f.stem.split("_")[1])):
        salva_legislatura(conn, leggi_legislatura(file), ids, indice, rapporto)
    for riga in dimensioni(conn):
        rapporto.aggiungi(riga)
    return rapporto


# --- Camera ---------------------------------------------------------------------------


def codice_camera(iri: str, prefisso: str) -> str:
    """Il ramo davanti all'identificativo della fonte: `camera:vs14_115_096`, `camera:gr139`, `camera:L1990_241`."""
    return "camera:" + iri.removeprefix(prefisso)


def deputato(persona: str) -> str:
    """Il codice di un deputato è la persona della Camera, uguale in tutte le legislature: `camera:305578`."""
    return "camera:" + persona


def denominazioni_camera(gruppo: camera.GruppoCamera) -> list[tuple[date, date | None, str, str | None]]:
    """(inizio, fine, nome, sigla) del gruppo nel tempo: i nomi precedenti ("gia' ... fino a") e poi quello attuale."""
    righe = []
    inizio = gruppo.inizio
    for nome, sigla, fine in sorted((p for p in gruppo.precedenti if p[2]), key=lambda p: p[2]):
        if fine < inizio:
            continue
        righe.append((inizio, fine, nome, sigla))
        inizio = date.fromordinal(fine.toordinal() + 1)
    righe.append((inizio, gruppo.fine, gruppo.nome, gruppo.sigla))
    return righe


def confronta_governi(camera_governi: list[camera.GovernoCamera]) -> list[str]:
    """Governi di `governi.csv` che non cominciano lo stesso giorno di un governo della Camera."""
    inizi = {g.inizio for g in camera_governi}
    return [f"{g.nome} ({g.inizio.isoformat()})" for g in governi.carica() if g.inizio not in inizi]


def salva_persone_camera(conn: psycopg.Connection, persone: PersoneCamera, rapporto: Rapporto) -> dict[str, int]:
    righe = {deputato(d.id): (d.nome, d.cognome) for d in persone.deputati}
    for a in persone.adesioni:
        righe.setdefault(deputato(a.deputato), (None, None))
    ids = salva_parlamentari(
        conn, "camera", [(c, nome, cognome, camera.PERSONA + c.removeprefix("camera:")) for c, (nome, cognome) in righe.items()]
    )
    gruppi = {g.id: g for g in persone.gruppi}
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO gruppo (id, ramo, nome, sigla) VALUES (%s, 'camera', %s, %s)
            ON CONFLICT (id) DO UPDATE SET nome = EXCLUDED.nome, sigla = EXCLUDED.sigla
            """,
            [(codice_camera(g.id, camera.GRUPPO), g.nome, g.sigla) for g in gruppi.values()]
            + [(codice_camera(a.gruppo, camera.GRUPPO), codice_camera(a.gruppo, camera.GRUPPO), None)
               for a in persone.adesioni if a.gruppo not in gruppi],
        )
        cur.execute("DELETE FROM denominazione_gruppo WHERE gruppo_id LIKE 'camera:%'")
        denominazioni = {
            (codice_camera(g.id, camera.GRUPPO), inizio): (fine, nome, sigla)
            for g in gruppi.values() for inizio, fine, nome, sigla in denominazioni_camera(g)
        }
        cur.executemany(
            "INSERT INTO denominazione_gruppo (gruppo_id, inizio, fine, nome, sigla) VALUES (%s, %s, %s, %s, %s)",
            [(gruppo_id, inizio, fine, nome, sigla) for (gruppo_id, inizio), (fine, nome, sigla) in denominazioni.items()],
        )
        cur.execute("DELETE FROM adesione_gruppo WHERE gruppo_id LIKE 'camera:%'")
        cur.executemany(
            "INSERT INTO adesione_gruppo (parlamentare_id, gruppo_id, inizio, fine) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            [(ids[deputato(a.deputato)], codice_camera(a.gruppo, camera.GRUPPO), a.inizio, a.fine) for a in persone.adesioni],
        )
    conn.commit()
    rapporto.aggiungi(
        f"Deputati: {len(persone.deputati)}; gruppi della Camera: {len(gruppi)} ({len(denominazioni)} denominazioni); "
        f"adesioni: {len(persone.adesioni)}"
    )
    diversi = confronta_governi(persone.governi)
    rapporto.aggiungi(
        f"Governi della Camera dal 1989: {len(persone.governi)}; in governi.csv con una data di giuramento diversa: "
        + (", ".join(diversi) if diversi else "nessuno")
    )
    return ids


def indice_fasi_camera(conn: psycopg.Connection) -> dict[tuple[int, str], str]:
    """(legislatura, numero senza ramo) → id delle fasi Camera negli iter del Senato."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT f.id, i.legislatura, f.numero FROM fase_iter f JOIN iter i ON i.id = f.iter_id
            WHERE f.ramo = 'camera' AND i.id LIKE 'senato:%'
            """
        )
        return {(leg, numero_senza_ramo(numero)): fase for fase, leg, numero in cur.fetchall()}


def iter_camera(leg: LegislaturaCamera, indice: IndiceLeggi, ids: dict[str, int]):
    """Iter, fasi e firmatari delle leggi X-XII dai lavori preparatori della Camera (il Senato non ha questi anni)."""
    urn_noti = set(indice.esatte.values())
    atti = {a.id: a for a in leg.atti}
    iter_righe, fasi_righe, firmatari = [], [], []
    viste: set[str] = set()  # un atto nei lavori preparatori di due leggi (es. uno stralcio) va solo nel primo iter
    for legge in leg.leggi:
        fasi = sorted((atti[a] for a in legge.atti if a in atti and a not in viste), key=lambda a: (a.data or date.max, a.id))
        viste.update(a.id for a in fasi)
        if not fasi:
            continue
        natura_iter = camera.natura(legge)
        urn = legge.urn if legge.urn in urn_noti else None
        if urn is None and legge.numero:
            urn = risolvi_urn(tipo_legge(natura_iter), [legge.numero], [legge.data] if legge.data else [], None, indice)[0]
        id_iter = codice_camera(legge.id, camera.LEGGE)
        iter_righe.append(RigaIter(
            id_iter, urn, leg.numero, natura_iter, legge.titolo, camera.iniziativa(fasi[0].iniziativa), fasi[0].data, None,
            legge.numero, legge.data, fasi[0].scheda or legge.id,
        ))
        for progressivo, atto in enumerate(fasi, start=1):
            fase_id = codice_camera(atto.id, camera.ATTO)
            fasi_righe.append((
                fase_id, id_iter, progressivo, "camera", f"C.{atto.numero}", atto.titolo, atto.data, None, None, atto.scheda or atto.id,
            ))
            tipo = camera.iniziativa(atto.iniziativa)
            # La persona del primo firmatario si collega solo se il nome è uno: con più nomi non si sa quale sia.
            primo = ids.get(deputato(atto.primo_firmatario)) if atto.primo_firmatario and len(atto.firmatari) == 1 else None
            firmatari += [(fase_id, nome, tipo, True, primo) for nome in atto.firmatari]
            firmatari += [(fase_id, nome, tipo, False, None) for nome in atto.altri_firmatari]
    return iter_righe, fasi_righe, firmatari


def salva_legislatura_camera(
    conn: psycopg.Connection, leg: LegislaturaCamera, ids: dict[str, int], indice: IndiceLeggi,
    fasi: dict[tuple[int, str], str], rapporto: Rapporto,
) -> None:
    if leg.numero < camera.PRIMA_CON_VOTI:
        iter_righe, fasi_righe, firmatari = iter_camera(leg, indice, ids)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM iter WHERE id LIKE 'camera:%%' AND legislatura = %s", (leg.numero,))
            cur.executemany(
                """
                INSERT INTO iter (id, urn, legislatura, natura, titolo, iniziativa, data_presentazione, data_approvazione,
                    numero_legge, data_legge, fonte_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [(r.id, r.urn, r.legislatura, r.natura, r.titolo, r.iniziativa, r.data_presentazione, r.data_approvazione,
                  r.numero_legge, r.data_legge, r.fonte_url) for r in iter_righe],
            )
            cur.executemany(
                """
                INSERT INTO fase_iter (id, iter_id, progressivo, ramo, numero, titolo, data_presentazione, stato, data_stato, fonte_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                fasi_righe,
            )
            cur.executemany(
                "INSERT INTO firmatario (fase_id, nome, tipo, primo_firmatario, parlamentare_id) VALUES (%s, %s, %s, %s, %s)",
                firmatari,
            )
        conn.commit()
        con_urn = sum(1 for r in iter_righe if r.urn)
        senza_lavori = sum(1 for legge in leg.leggi if not legge.atti)
        rapporto.aggiungi(
            f"Camera, legislatura {leg.numero}: {len(leg.leggi)} leggi dal 1990, {len(iter_righe)} iter dai lavori preparatori "
            f"({len(fasi_righe)} fasi, {len(firmatari)} firmatari); leggi senza lavori preparatori: {senza_lavori}"
        )
        rapporto.aggiungi(f"- collegati a una legge di Normattiva: {con_urn} (non trovati: {len(iter_righe) - con_urn})")
        return

    tipi: Counter = Counter()
    votazioni, senza_fase = [], Counter()
    voti_totali = mancanti_totali = discordanti = 0
    for v in leg.votazioni:
        fase = fasi.get((leg.numero, v.numero or ""))
        if fase is None:
            senza_fase[v.numero] += 1
            continue
        elenchi, mancanti = [], 0
        for chiave in ("favorevoli", "contrari", "astenuti"):
            elenco = sorted({ids[c] for c in (deputato(p) for p in v.voti.get(chiave, [])) if c in ids})
            mancanti += len(v.voti.get(chiave, [])) - len(elenco)
            elenchi.append(elenco)
        tipo = camera.tipo_votazione(v)
        tipi[tipo] += 1
        voti_totali += sum(len(e) for e in elenchi)
        mancanti_totali += mancanti
        if any(elenchi) and tuple(len(e) for e in elenchi) != (v.favorevoli, v.contrari, v.astenuti):
            discordanti += 1
        esito = None if v.approvato is None else ("approvato" if v.approvato else "respinto")
        descrizione = v.titolo if not v.descrizione else f"{v.titolo}. {v.descrizione}"
        votazioni.append((
            codice_camera(v.id, camera.VOTAZIONE), fase, leg.numero, v.data, tipo, descrizione, esito, v.presenti, v.votanti,
            v.favorevoli, v.contrari, v.astenuti, v.maggioranza, *elenchi, v.fonte_url or v.id,
        ))
    with conn.cursor() as cur:
        cur.execute("DELETE FROM votazione WHERE id LIKE 'camera:%%' AND legislatura = %s", (leg.numero,))
        cur.executemany(
            """
            INSERT INTO votazione (id, fase_id, ramo, legislatura, data, tipo, descrizione, esito, presenti, votanti,
                favorevoli, contrari, astenuti, maggioranza, voti_favorevoli, voti_contrari, voti_astenuti, fonte_url)
            VALUES (%s, %s, 'camera', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            votazioni,
        )
    conn.commit()

    fasi_con_finale = {r[1] for r in votazioni if r[4] == "finale"}
    numeri_senato = set(leg.fasi_senato)
    atti_leggi = {camera.numero_atto(a) for legge in leg.leggi for a in legge.atti} - {None}
    rapporto.aggiungi(f"Camera, legislatura {leg.numero}: {len(votazioni)} votazioni ({', '.join(f'{t} {n}' for t, n in tipi.most_common())})")
    rapporto.aggiungi(f"- fasi Camera degli iter del Senato: {len(numeri_senato)}, con una votazione finale nominale: {len(fasi_con_finale)}")
    rapporto.aggiungi(
        f"- votazioni su fasi che non sono nel database (Senato non caricato o fase diversa): {sum(senza_fase.values())}"
        + (f" (es. {', '.join(n or '?' for n, _ in senza_fase.most_common(5))})" if senza_fase else "")
    )
    rapporto.aggiungi(f"- votazioni su altri atti (non caricate): {leg.votazioni_scartate}")
    rapporto.aggiungi(f"- voti individuali: {voti_totali}; deputati non trovati: {mancanti_totali}")
    rapporto.aggiungi(f"- votazioni nominali con elenchi diversi dai totali della fonte: {discordanti}")
    rapporto.aggiungi(
        f"- atti dei lavori preparatori della Camera che non sono fasi Camera negli iter del Senato: "
        f"{len(atti_leggi - numeri_senato)} su {len(atti_leggi)}"
    )


def carica_camera(conn: psycopg.Connection, cartella: Path) -> Rapporto:
    rapporto = Rapporto()
    db.crea_schema(conn)
    db.salva_governi(conn, governi.carica())
    ids = salva_persone_camera(conn, camera.leggi_persone(cartella / "camera_persone.json"), rapporto)
    indice = indice_leggi(conn)
    fasi = indice_fasi_camera(conn)
    rapporto.aggiungi(f"Leggi nel database per il collegamento: {len(indice)}; fasi Camera negli iter del Senato: {len(fasi)}")
    for file in sorted(cartella.glob("camera_[0-9]*.json"), key=lambda f: int(f.stem.split("_")[1])):
        salva_legislatura_camera(conn, camera.leggi_legislatura(file), ids, indice, fasi, rapporto)
    for riga in dimensioni(conn):
        rapporto.aggiungi(riga)
    return rapporto
