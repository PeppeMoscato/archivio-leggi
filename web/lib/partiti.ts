// Ingressi e uscite dei partiti durante un governo (schema v1.6), dalle date di ogni riga.

import type { GovernoConPartiti, PartitoGoverno } from "./tipi";

export interface CambioPartito {
  data: string;
  partito: string;
  /** entra / esce dalla maggioranza; passa = resta, ma cambia ruolo (con ministri ↔ appoggio esterno). */
  verso: "entra" | "esce" | "passa";
  ruolo: PartitoGoverno["ruolo"];
  nota: string | null;
  fonte_url: string;
}

/** I cambi dopo il giuramento, in ordine di data: chi entra, chi esce e chi passa all'appoggio esterno o al governo. */
export function cambiPartiti(governo: GovernoConPartiti): CambioPartito[] {
  const cambi: CambioPartito[] = [];
  const fonte = (p: PartitoGoverno) => p.fonte_date_url ?? p.fonte_url;
  for (const p of governo.partiti) {
    if (p.inizio && p.inizio > governo.inizio) {
      const prima = governo.partiti.find((q) => q !== p && q.partito === p.partito && q.fine === p.inizio);
      cambi.push({ data: p.inizio, partito: p.partito, verso: prima ? "passa" : "entra", ruolo: p.ruolo, nota: p.nota ?? null, fonte_url: fonte(p) });
    }
    if (p.fine && (governo.fine === null || p.fine < governo.fine)) {
      const dopo = governo.partiti.some((q) => q !== p && q.partito === p.partito && q.inizio === p.fine);
      if (!dopo) cambi.push({ data: p.fine, partito: p.partito, verso: "esce", ruolo: p.ruolo, nota: p.nota ?? null, fonte_url: fonte(p) });
    }
  }
  return cambi.sort((a, b) => a.data.localeCompare(b.data) || a.partito.localeCompare(b.partito));
}

/** I partiti del governo in un giorno (lo stesso calcolo dell'API, per le risposte senza `maggioranza`). */
export function maggioranzaAlla(partiti: PartitoGoverno[], giorno: string): PartitoGoverno[] {
  return partiti.filter((p) => (!p.inizio || p.inizio <= giorno) && (!p.fine || giorno < p.fine));
}

/** Vero se l'atto è del governo già dimissionario (affari correnti). */
export const dimissionario = (governo: GovernoConPartiti, giorno: string) =>
  Boolean(governo.dimissioni && governo.dimissioni <= giorno);
