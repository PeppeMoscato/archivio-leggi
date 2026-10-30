// Gli eventi della timeline di una legge: nascita (emanazione, Gazzetta, entrata in vigore), le relazioni
// dell'API in ordine di data e, se c'è, la fine della vigenza.

import { dataLunga, nomeStato } from "./formato";
import type { LeggeDettaglio, Relazione, Verso } from "./tipi";

export type Tono = "nascita" | "modifica" | "abrogazione" | "conversione" | "fine";

export interface Evento {
  chiave: string;
  data: string | null;
  tono: Tono;
  titolo: string;
  testo?: string;
  /** Le relazioni dell'evento: più di una quando lo stesso atto, lo stesso giorno, tocca più articoli. */
  relazioni?: Relazione[];
}

const TONO: Record<Relazione["tipo"], Tono> = {
  modifica: "modifica",
  proroga: "modifica",
  attua: "modifica",
  delega: "modifica",
  abroga_parziale: "abrogazione",
  abroga: "abrogazione",
  converte: "conversione",
};

/**
 * La stessa conversione può arrivare da più note e dal titolo della legge di conversione (vedi "Relazioni
 * converte doppie" in docs/05_stato_e_decisioni.md): nella timeline se ne mostra una sola per atto.
 */
export function senzaConversioniDoppie(relazioni: Relazione[]): Relazione[] {
  const viste = new Set<string>();
  return relazioni.filter((r) => {
    if (r.tipo !== "converte") return true;
    const chiave = [r.urn_origine ?? r.origine_gazzetta_codice ?? r.id, r.urn_destinazione].join(" → ");
    if (viste.has(chiave)) return false;
    viste.add(chiave);
    return true;
  });
}

// Relazioni consecutive dello stesso tipo, dello stesso giorno e con lo stesso altro atto diventano un evento solo:
// una legge che modifica dieci articoli della 241/1990 è una riga nella timeline, non dieci.
function chiaveGruppo(r: Relazione, verso: Verso): string {
  const altro = (verso === "ricevute" ? r.urn_origine : r.urn_destinazione) ?? r.origine_gazzetta_codice;
  return altro ? [r.tipo, r.data, altro].join("|") : `r${r.id}`;
}

export function eventiTimeline(
  legge: LeggeDettaglio,
  relazioni: Relazione[],
  { verso, primaPagina, ultimaPagina }: { verso: Verso; primaPagina: boolean; ultimaPagina: boolean },
): Evento[] {
  const eventi: Evento[] = [];
  const dellaLegge = verso === "ricevute";

  if (dellaLegge && primaPagina) {
    eventi.push({ chiave: "emanazione", data: legge.data, tono: "nascita", titolo: "Emanazione" });
    if (legge.gazzetta_data) {
      eventi.push({
        chiave: "gazzetta",
        data: legge.gazzetta_data,
        tono: "nascita",
        titolo: "Pubblicazione in Gazzetta Ufficiale",
        testo: legge.gazzetta_numero ? `Gazzetta Ufficiale n. ${legge.gazzetta_numero}` : undefined,
      });
    }
    if (legge.data_entrata_vigore) {
      eventi.push({ chiave: "vigore", data: legge.data_entrata_vigore, tono: "nascita", titolo: "Entrata in vigore" });
    }
  }

  let ultima: { evento: Evento; chiave: string } | null = null;
  for (const relazione of senzaConversioniDoppie(relazioni)) {
    const chiave = chiaveGruppo(relazione, verso);
    if (ultima && ultima.chiave === chiave) {
      ultima.evento.relazioni!.push(relazione);
      continue;
    }
    const evento: Evento = {
      chiave: `r${relazione.id}`,
      data: relazione.data,
      tono: TONO[relazione.tipo] ?? "modifica",
      titolo: "",
      relazioni: [relazione],
    };
    eventi.push(evento);
    ultima = { evento, chiave };
  }

  if (dellaLegge && ultimaPagina && legge.stato !== "vigente" && legge.data_abrogazione) {
    eventi.push({
      chiave: "fine",
      data: legge.data_abrogazione,
      tono: "fine",
      titolo: legge.stato === "decaduta" ? "Decaduto per mancata conversione" : "Fine della vigenza",
      testo: `L'atto risulta ${nomeStato(legge.stato, legge.tipo)} dal ${dataLunga(legge.data_abrogazione)}.`,
    });
  }
  return eventi;
}

/** Gli eventi raggruppati per anno, nell'ordine in cui arrivano. Gli eventi senza data vanno in "Senza data". */
export function perAnno(eventi: Evento[]): { anno: string; eventi: Evento[] }[] {
  const gruppi: { anno: string; eventi: Evento[] }[] = [];
  for (const evento of eventi) {
    const anno = evento.data ? evento.data.slice(0, 4) : "Senza data";
    const ultimo = gruppi.at(-1);
    if (ultimo && ultimo.anno === anno) ultimo.eventi.push(evento);
    else gruppi.push({ anno, eventi: [evento] });
  }
  return gruppi;
}
