"""Client minimo per gli endpoint SPARQL di Senato e Camera (Virtuoso).

Solo libreria standard: le query sono SELECT con risultati JSON. Gli endpoint
non pubblicano quote: si aspetta un po' fra una richiesta e l'altra e si
riprova sugli errori 5xx e di rete.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator

logger = logging.getLogger(__name__)

# Lo stesso per tutte le fonti: chi amministra i siti sa chi siamo e dove scriverci.
USER_AGENT = "archivio-leggi (progetto non commerciale; +https://github.com/PeppeMoscato/archivio-leggi)"
ATTESA_MASSIMA = 600  # secondi: oltre, un Retry-After non si aspetta per intero


def attesa_dopo_errore(errore: Exception, tentativo: int) -> float:
    """10, 20, 30... secondi, o di più se il server lo chiede con Retry-After (429 e 503)."""
    attesa = 10.0 * tentativo
    if isinstance(errore, urllib.error.HTTPError) and errore.headers is not None:
        try:
            attesa = max(attesa, float(errore.headers.get("Retry-After") or 0))
        except ValueError:  # Retry-After con una data: si resta sull'attesa crescente
            pass
    return min(attesa, ATTESA_MASSIMA)


class ErroreSparql(Exception):
    pass


class Sparql:
    def __init__(self, endpoint: str, prefissi: str = "", attesa: float = 0.5, tentativi: int = 4, timeout: float = 180.0):
        self.endpoint = endpoint
        self.prefissi = prefissi
        self.attesa = attesa
        self.tentativi = tentativi
        self.timeout = timeout

    def select(self, query: str) -> list[dict[str, str]]:
        """Esegue una SELECT e restituisce le righe come {variabile: valore}; le variabili non legate mancano."""
        parametri = urllib.parse.urlencode({"query": self.prefissi + query, "format": "application/sparql-results+json"})
        richiesta = urllib.request.Request(
            f"{self.endpoint}?{parametri}",
            headers={"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT},
        )
        for tentativo in range(1, self.tentativi + 1):
            time.sleep(self.attesa)
            try:
                with urllib.request.urlopen(richiesta, timeout=self.timeout) as risposta:
                    dati = json.load(risposta)
                return [{k: v["value"] for k, v in riga.items()} for riga in dati["results"]["bindings"]]
            except urllib.error.HTTPError as errore:
                # 404 su /sparql: l'endpoint della Camera a volte lo risponde per qualche istante (29/10/2026),
                # l'indirizzo non cambia mai. Un 400 (query sbagliata) invece non si riprova.
                if (errore.code < 500 and errore.code not in (404, 429)) or tentativo == self.tentativi:
                    dettaglio = errore.read().decode(errors="replace")[:300]
                    raise ErroreSparql(f"HTTP {errore.code}: {dettaglio}") from errore
                logger.warning("SPARQL HTTP %s, tentativo %s", errore.code, tentativo)
                time.sleep(attesa_dopo_errore(errore, tentativo))
                continue
            except (urllib.error.URLError, TimeoutError) as errore:
                if tentativo == self.tentativi:
                    raise ErroreSparql(str(errore)) from errore
                logger.warning("SPARQL %s, tentativo %s", errore, tentativo)
            time.sleep(10 * tentativo)
        raise AssertionError("non raggiungibile")

    def pagine(self, query: str, per_pagina: int = 10_000) -> Iterator[dict[str, str]]:
        """Tutte le righe di una SELECT con ORDER BY, una pagina alla volta (Virtuoso tronca le risposte grandi)."""
        scarto = 0
        while True:
            righe = self.select(f"{query}\nOFFSET {scarto} LIMIT {per_pagina}")
            yield from righe
            if len(righe) < per_pagina:
                return
            scarto += per_pagina
