"""Riga di comando delle pipeline Normattiva, Senato e Camera → Postgres, e dell'aggiornamento settimanale.

    python -m archivio estrai --anni 2003 2004 --uscita dati/
    python -m archivio carica --da dati/            # DATABASE_URL nell'ambiente

    python -m archivio aggiorna-estrai --giorni 14 --uscita dati/   # atti nuovi e modificati di recente
    python -m archivio aggiorna-carica --da dati/   # dopo il caricamento completo; DATABASE_URL nell'ambiente

    python -m archivio premesse-estrai --anni 1990- --uscita dati/   # premesse di D.L. e D.Lgs.
    python -m archivio premesse-carica --da dati/   # dopo carica; DATABASE_URL nell'ambiente

    python -m archivio senato-estrai --legislature 13-19 --uscita dati/
    python -m archivio senato-persone --uscita dati/
    python -m archivio senato-carica --da dati/     # DATABASE_URL nell'ambiente

    python -m archivio camera-estrai --legislature 10-19 --uscita dati/
    python -m archivio camera-persone --uscita dati/
    python -m archivio camera-stima --legislature 13-19   # spazio delle votazioni, senza scaricare i voti
    python -m archivio camera-carica --da dati/     # dopo senato-carica; DATABASE_URL nell'ambiente

Il rapporto finisce su stdout e, su GitHub Actions, nel riepilogo del job.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from normattiva import Normattiva

from archivio import aggiornamento, camera, contesto, db, parlamento, senato
from archivio.pipeline import PERIMETRO, Rapporto, carica, estrai, leggi_atti
from archivio.sparql import USER_AGENT


def anni(testo: str) -> list[int]:
    """"2003", "1990-1995" o "1990-" (fino all'anno in corso)."""
    if "-" not in testo:
        return [int(testo)]
    inizio, _, fine = testo.partition("-")
    return list(range(int(inizio), int(fine or date.today().year) + 1))


def pubblica(titolo: str, testo: str) -> None:
    print(f"## {titolo}\n\n{testo}")
    if riepilogo := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(riepilogo, "a", encoding="utf-8") as file:
            file.write(f"## {titolo}\n\n{testo}\n")


def main(argomenti: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="archivio")
    comandi = parser.add_subparsers(dest="comando", required=True)
    p_estrai = comandi.add_parser("estrai", help="catalogo ed export da Normattiva in JSONL")
    p_estrai.add_argument("--anni", nargs="+", required=True, help="es. 2003, 1990-1995, 1990-")
    p_estrai.add_argument("--tipi", nargs="+", default=list(PERIMETRO), choices=PERIMETRO)
    p_estrai.add_argument("--uscita", type=Path, required=True)
    p_carica = comandi.add_parser("carica", help="dai JSONL al database")
    p_carica.add_argument("--da", type=Path, required=True)
    p_carica.add_argument("--senza-api", action="store_true", help="non chiamare Normattiva per i riferimenti")
    p_aggiorna = comandi.add_parser("aggiorna-estrai", help="atti nuovi e modificati di recente da Normattiva, in JSONL")
    p_aggiorna.add_argument("--giorni", type=int, default=aggiornamento.GIORNI, help="ampiezza della finestra, fino a --al")
    p_aggiorna.add_argument("--al", type=date.fromisoformat, default=None, help="ultimo giorno (AAAA-MM-GG), di default oggi")
    p_aggiorna.add_argument("--uscita", type=Path, required=True)
    p_aggiorna_carica = comandi.add_parser("aggiorna-carica", help="dai JSONL dell'aggiornamento al database")
    p_aggiorna_carica.add_argument("--da", type=Path, required=True)
    p_premesse = comandi.add_parser("premesse-estrai", help="premesse dei D.L. e dei D.Lgs. da Normattiva, un JSONL per anno")
    p_premesse.add_argument("--anni", nargs="+", required=True, help="es. 2006, 1990-1995, 1990-")
    p_premesse.add_argument("--uscita", type=Path, required=True)
    p_premesse_carica = comandi.add_parser("premesse-carica", help="dai JSONL delle premesse al database (dopo carica)")
    p_premesse_carica.add_argument("--da", type=Path, required=True)
    p_senato = comandi.add_parser("senato-estrai", help="iter e votazioni da dati.senato.it, un JSON per legislatura")
    p_senato.add_argument("--legislature", nargs="+", required=True, help="es. 15, 13-19")
    p_senato.add_argument("--uscita", type=Path, required=True)
    p_persone = comandi.add_parser("senato-persone", help="senatori, gruppi e adesioni da dati.senato.it")
    p_persone.add_argument("--uscita", type=Path, required=True)
    p_senato_carica = comandi.add_parser("senato-carica", help="dai JSON del Senato al database")
    p_senato_carica.add_argument("--da", type=Path, required=True)
    p_camera = comandi.add_parser("camera-estrai", help="votazioni (XIII-XIX) e iter (X-XII) da dati.camera.it, un JSON per legislatura")
    p_camera.add_argument("--legislature", nargs="+", required=True, help="es. 15, 10-19")
    p_camera.add_argument("--uscita", type=Path, required=True)
    p_deputati = comandi.add_parser("camera-persone", help="deputati, gruppi e adesioni da dati.camera.it")
    p_deputati.add_argument("--legislature", nargs="+", default=["10-19"])
    p_deputati.add_argument("--uscita", type=Path, required=True)
    p_stima = comandi.add_parser("camera-stima", help="quante votazioni e voti della Camera si caricherebbero")
    p_stima.add_argument("--legislature", nargs="+", default=["13-19"])
    p_camera_carica = comandi.add_parser("camera-carica", help="dai JSON della Camera al database (dopo il Senato)")
    p_camera_carica.add_argument("--da", type=Path, required=True)
    opzioni = parser.parse_args(argomenti)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if opzioni.comando == "estrai":
        elenco = sorted({anno for testo in opzioni.anni for anno in anni(testo)})
        with Normattiva(user_agent=USER_AGENT, timeout=300.0) as client:
            rapporto = estrai(client, elenco, opzioni.uscita, opzioni.tipi)
        pubblica(f"Estrazione {elenco[0]}–{elenco[-1]}", rapporto.testo())
        return 0
    if opzioni.comando == "aggiorna-estrai":
        dal, al = aggiornamento.finestra(opzioni.giorni, opzioni.al)
        with Normattiva(user_agent=USER_AGENT, timeout=300.0) as client:
            rapporto = aggiornamento.estrai_aggiornamento(client, dal, al, opzioni.uscita)
        pubblica("Aggiornamento da Normattiva", rapporto.testo())
        return 0
    if opzioni.comando == "premesse-estrai":
        elenco = sorted({anno for testo in opzioni.anni for anno in anni(testo)})
        with Normattiva(user_agent=USER_AGENT, timeout=120.0) as client:
            rapporto = contesto.estrai_premesse(client, elenco, opzioni.uscita)
        pubblica(f"Premesse {elenco[0]}–{elenco[-1]}", rapporto.testo())
        return 0
    if opzioni.comando == "senato-estrai":
        rapporto = Rapporto()
        client = senato.client()
        for leg in sorted({n for testo in opzioni.legislature for n in anni(testo)}):
            dati = senato.estrai_legislatura(client, leg)
            senato.scrivi(opzioni.uscita / f"senato_{leg}.json", dati)
            rapporto.aggiungi(
                f"Legislatura {leg}: {len(dati.fasi)} fasi, {len(dati.iniziative)} firmatari, {len(dati.votazioni)} votazioni "
                f"({sum(len(e) for v in dati.votazioni for e in v.voti.values())} voti individuali), "
                f"{dati.votazioni_scartate} su altri ddl o non collegate"
            )
        pubblica("Estrazione Senato", rapporto.testo())
        return 0
    if opzioni.comando == "senato-persone":
        persone = senato.estrai_persone(senato.client())
        senato.scrivi(opzioni.uscita / "senato_persone.json", persone)
        pubblica(
            "Senatori e gruppi",
            f"Senatori: {len(persone.senatori)}; adesioni: {len(persone.adesioni)}; denominazioni: {len(persone.denominazioni)}\n",
        )
        return 0

    if opzioni.comando == "camera-estrai":
        rapporto = Rapporto()
        client_camera, client_senato = camera.client(), senato.client()
        for leg in sorted({n for testo in opzioni.legislature for n in anni(testo)}):
            dati = camera.estrai_legislatura(client_camera, client_senato, leg, opzioni.uscita / "cache")
            camera.scrivi(opzioni.uscita / f"camera_{leg}.json", dati)
            rapporto.aggiungi(
                f"Legislatura {leg}: {len(dati.leggi)} leggi dal 1990, {len(dati.atti)} atti dei lavori preparatori, "
                f"{len(dati.votazioni)} votazioni ({sum(len(e) for v in dati.votazioni for e in v.voti.values())} voti individuali), "
                f"{dati.votazioni_scartate} su altri atti; fasi Camera negli iter del Senato: {len(dati.fasi_senato)}"
            )
        pubblica("Estrazione Camera", rapporto.testo())
        return 0
    if opzioni.comando == "camera-persone":
        legislature = sorted({n for testo in opzioni.legislature for n in anni(testo)})
        persone = camera.estrai_persone(camera.client(), legislature)
        camera.scrivi(opzioni.uscita / "camera_persone.json", persone)
        pubblica(
            "Deputati e gruppi",
            f"Deputati: {len(persone.deputati)}; adesioni: {len(persone.adesioni)}; gruppi: {len(persone.gruppi)}; "
            f"governi dal 1989: {len(persone.governi)}\n",
        )
        return 0
    if opzioni.comando == "camera-stima":
        righe = ["| Legislatura | Votazioni da caricare | Palesi | Voti individuali (totali della fonte) | Voti nell'endpoint |",
                 "|---|---|---|---|---|"]
        somma = [0, 0, 0]
        client_camera, client_senato = camera.client(), senato.client()
        for leg in sorted({n for testo in opzioni.legislature for n in anni(testo)}):
            conti = camera.stima_legislatura(client_camera, client_senato, leg)
            somma = [a + b for a, b in zip(somma, conti)]
            nell_endpoint = "sì" if leg >= camera.PRIMA_CON_VOTI_INDIVIDUALI else "no, solo nelle schede HTML"
            righe.append(f"| {leg} | {conti[0]} | {conti[1]} | {conti[2]} | {nell_endpoint} |")
        righe.append(f"| Totale | {somma[0]} | {somma[1]} | {somma[2]} | |")
        pubblica("Stima delle votazioni della Camera", "\n".join(righe) + "\n")
        return 0

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL non impostata", file=sys.stderr)
        return 2
    if opzioni.comando == "aggiorna-carica":
        with db.connetti(dsn) as conn, Normattiva(user_agent=USER_AGENT, timeout=120.0) as client:
            rapporto = aggiornamento.carica_aggiornamento(conn, opzioni.da, client)
        pubblica("Caricamento dell'aggiornamento", rapporto.testo())
        return 0
    if opzioni.comando == "premesse-carica":
        with db.connetti(dsn) as conn:
            rapporto = contesto.carica_premesse(conn, contesto.leggi_premesse(opzioni.da))
        pubblica("Caricamento premesse", rapporto.testo())
        return 0
    if opzioni.comando == "camera-carica":
        with db.connetti(dsn) as conn:
            rapporto = parlamento.carica_camera(conn, opzioni.da)
        pubblica("Caricamento Camera", rapporto.testo())
        return 0
    if opzioni.comando == "senato-carica":
        with db.connetti(dsn) as conn:
            rapporto = parlamento.carica_senato(conn, opzioni.da)
        pubblica("Caricamento Senato", rapporto.testo())
        return 0
    atti = leggi_atti(opzioni.da)
    with db.connetti(dsn) as conn:
        if opzioni.senza_api:
            rapporto = carica(conn, atti)
        else:
            with Normattiva(user_agent=USER_AGENT, timeout=120.0) as client:
                rapporto = carica(conn, atti, client)
    pubblica("Caricamento", rapporto.testo())
    return 0


if __name__ == "__main__":
    sys.exit(main())
