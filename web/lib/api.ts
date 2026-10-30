// Client dell'API FastAPI. Gira solo sul server (componenti server di Next.js): il browser non chiama mai
// l'API, quindi non serve CORS e le risposte finiscono nella cache dei dati di Next.js.

import type {
  GovernoConAtti,
  Iter,
  LeggeDettaglio,
  LeggeSintesi,
  Pagina,
  Pronuncia,
  Relazione,
  TipoRelazione,
  TipoVotazione,
  Verso,
  Votazione,
} from "./tipi";

export const API_URL = (process.env.API_URL ?? "https://archivio-leggi-api.onrender.com").replace(/\/+$/, "");

// I dati cambiano quando gira una pipeline (al massimo una volta a settimana): un'ora di cache basta e
// risparmia le ore di Render e le CU-ore di Neon.
const CACHE_SECONDI = 3600;

// Render Free si spegne dopo 15 minuti senza richieste e si riaccende in circa un minuto. Mentre si
// riaccende risponde 502/503 o non risponde: si riprova fino a ATTESA_MASSIMA_MS.
const ATTESA_MASSIMA_MS = 100_000;
const TIMEOUT_RICHIESTA_MS = 70_000;
const PAUSE_MS = [2_000, 4_000, 8_000, 15_000];
const DA_RIPROVARE = new Set([502, 503, 504]);

export class ErroreApi extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
    this.name = "ErroreApi";
  }
}

export interface Opzioni {
  fetch?: typeof fetch;
  attendi?: (ms: number) => Promise<void>;
  adesso?: () => number;
  cacheSecondi?: number;
}

const attendiDavvero = (ms: number) => new Promise<void>((risolvi) => setTimeout(risolvi, ms));

/** GET sull'API, con i tentativi durante il risveglio. 404 → ErroreApi con status 404. */
export async function chiama<T>(percorso: string, opzioni: Opzioni = {}): Promise<T> {
  const {
    fetch: f = fetch,
    attendi = attendiDavvero,
    adesso = Date.now,
    cacheSecondi = CACHE_SECONDI,
  } = opzioni;
  const inizio = adesso();
  for (let tentativo = 0; ; tentativo++) {
    let errore: ErroreApi;
    try {
      const risposta = await f(API_URL + percorso, {
        headers: { accept: "application/json" },
        signal: AbortSignal.timeout(TIMEOUT_RICHIESTA_MS),
        next: { revalidate: cacheSecondi },
      });
      if (risposta.ok) return (await risposta.json()) as T;
      errore = new ErroreApi(`L'API ha risposto ${risposta.status} a ${percorso}`, risposta.status);
      if (!DA_RIPROVARE.has(risposta.status)) throw errore;
    } catch (e) {
      if (e instanceof ErroreApi && !DA_RIPROVARE.has(e.status ?? 0)) throw e;
      errore = e instanceof ErroreApi ? e : new ErroreApi(`L'API non risponde (${percorso}): ${e}`, null);
    }
    const pausa = PAUSE_MS[Math.min(tentativo, PAUSE_MS.length - 1)];
    if (adesso() - inizio + pausa > ATTESA_MASSIMA_MS) throw errore;
    await attendi(pausa);
  }
}

/** Una query string senza i parametri vuoti. */
export function parametri(valori: Record<string, string | number | boolean | null | undefined>): string {
  const p = new URLSearchParams();
  for (const [chiave, valore] of Object.entries(valori)) {
    if (valore !== null && valore !== undefined && valore !== "") p.set(chiave, String(valore));
  }
  const testo = p.toString();
  return testo ? `?${testo}` : "";
}

const legge = (urn: string) => `/leggi/${encodeURIComponent(urn)}`;

export interface FiltriRicerca {
  q?: string;
  tipo?: string;
  stato?: string;
  governo?: string;
  anno?: string;
  modificata?: string;
  ordine?: string;
  pagina?: number;
}

export const cercaLeggi = (filtri: FiltriRicerca, perPagina = 20) =>
  chiama<Pagina<LeggeSintesi>>(`/leggi${parametri({ ...filtri, per_pagina: perPagina })}`);

export const dettaglioLegge = (urn: string) => chiama<LeggeDettaglio>(legge(urn));

export const relazioni = (urn: string, verso: Verso, pagina: number, perPagina = 50, tipo?: TipoRelazione) =>
  chiama<Pagina<Relazione>>(`${legge(urn)}/relazioni${parametri({ verso, tipo, pagina, per_pagina: perPagina })}`);

export const pronunce = (urn: string) => chiama<Pronuncia[]>(`${legge(urn)}/pronunce`);

export const iter = (urn: string) => chiama<Iter[]>(`${legge(urn)}/iter`);

export const votazioni = (urn: string, tipo: TipoVotazione | undefined, pagina: number, perPagina = 20) =>
  chiama<Pagina<Votazione>>(
    `${legge(urn)}/votazioni${parametri({ tipo, gruppi: true, pagina, per_pagina: perPagina })}`,
  );

export const governi = () => chiama<GovernoConAtti[]>("/governi", { cacheSecondi: 86_400 });
