// Come si scrivono date, citazioni ed etichette nelle pagine.

import type { StatoAtto, TipoAtto, TipoRelazione, TipoVotazione, Verso } from "./tipi";

const DATA_LUNGA = new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const DATA_BREVE = new Intl.DateTimeFormat("it-IT", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" });

// "2003-01-16" o "2003-01-16T10:00:00+00:00" → Date in UTC, senza spostamenti di fuso orario.
function comeData(iso: string): Date {
  return new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
}

/** "16 gennaio 2003". */
export const dataLunga = (iso: string) => DATA_LUNGA.format(comeData(iso));

/** "16/01/2003". */
export const dataBreve = (iso: string) => DATA_BREVE.format(comeData(iso));

export const anno = (iso: string) => Number(iso.slice(0, 4));

const NOME_TIPO: Record<TipoAtto, string> = {
  legge: "Legge",
  "legge costituzionale": "Legge costituzionale",
  "decreto-legge": "Decreto-legge",
  "decreto legislativo": "Decreto legislativo",
};

const SIGLA_TIPO: Record<TipoAtto, string> = {
  legge: "L.",
  "legge costituzionale": "L. cost.",
  "decreto-legge": "D.L.",
  "decreto legislativo": "D.Lgs.",
};

/** "Legge 16 gennaio 2003, n. 3": la citazione per esteso, come in Gazzetta Ufficiale. */
export const citazioneEstesa = (atto: { tipo: TipoAtto; numero: string; data: string }) =>
  `${NOME_TIPO[atto.tipo] ?? atto.tipo} ${dataLunga(atto.data)}, n. ${atto.numero}`;

/** "L. 3/2003". */
export const citazioneBreve = (atto: { tipo: TipoAtto; numero: string; data: string }) =>
  `${SIGLA_TIPO[atto.tipo] ?? atto.tipo} ${atto.numero}/${anno(atto.data)}`;

export const nomeTipo = (tipo: TipoAtto) => NOME_TIPO[tipo] ?? tipo;

const STATO_MASCHILE: Record<StatoAtto, string> = { vigente: "vigente", abrogata: "abrogato", decaduta: "decaduto" };

/** "abrogata", ma "abrogato" per un decreto. */
export function nomeStato(stato: StatoAtto, tipo: TipoAtto): string {
  return tipo.startsWith("decreto") ? STATO_MASCHILE[stato] : stato;
}

// Come si legge una relazione dal punto di vista della legge della pagina.
const RELAZIONE_RICEVUTA: Record<TipoRelazione, string> = {
  modifica: "Modificata",
  abroga: "Abrogata",
  abroga_parziale: "Abrogata in parte",
  converte: "Convertito in legge",
  attua: "Attuata",
  proroga: "Prorogata",
  delega: "Adottato su delega",
};

const RELAZIONE_DISPOSTA: Record<TipoRelazione, string> = {
  modifica: "Modifica",
  abroga: "Abroga",
  abroga_parziale: "Abroga in parte",
  converte: "Converte in legge",
  attua: "Attua",
  proroga: "Proroga",
  delega: "Delega",
};

/** "Modificata", "Abroga in parte"; per un decreto che riceve la relazione, "Modificato". */
export function nomeRelazione(tipo: TipoRelazione, verso: Verso, tipoAtto?: TipoAtto): string {
  const nome = (verso === "ricevute" ? RELAZIONE_RICEVUTA : RELAZIONE_DISPOSTA)[tipo] ?? tipo;
  if (verso === "ricevute" && tipoAtto?.startsWith("decreto")) return nome.replace(/^(\p{L}+)a\b/u, "$1o");
  return nome;
}

const RELAZIONE_PLURALE: Record<TipoRelazione, [string, string]> = {
  modifica: ["modifica", "modifiche"],
  abroga: ["abrogazione", "abrogazioni"],
  abroga_parziale: ["abrogazione parziale", "abrogazioni parziali"],
  converte: ["conversione", "conversioni"],
  attua: ["atto di attuazione", "atti di attuazione"],
  proroga: ["proroga", "proroghe"],
  delega: ["delega", "deleghe"],
};

/** "12 modifiche", "1 abrogazione parziale". */
export function quanteRelazioni(tipo: TipoRelazione, numero: number): string {
  const [uno, tanti] = RELAZIONE_PLURALE[tipo] ?? [tipo, tipo];
  return `${numero.toLocaleString("it-IT")} ${numero === 1 ? uno : tanti}`;
}

export const NOMI_VOTAZIONE: Record<TipoVotazione, string> = {
  finale: "Voto finale",
  fiducia: "Fiducia",
  articolo: "Articolo",
  emendamento: "Emendamento",
  pregiudiziale: "Pregiudiziale",
  altro: "Altro",
};

export const nomeRamo = (ramo: "camera" | "senato") => (ramo === "camera" ? "Camera" : "Senato");

/** I numeri romani delle legislature (XIII, XIX). */
export function romano(n: number): string {
  const cifre: [number, string][] = [
    [1000, "M"], [900, "CM"], [500, "D"], [400, "CD"], [100, "C"], [90, "XC"],
    [50, "L"], [40, "XL"], [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"],
  ];
  let resto = n;
  let testo = "";
  for (const [valore, simbolo] of cifre) {
    while (resto >= valore) {
      testo += simbolo;
      resto -= valore;
    }
  }
  return testo;
}

/** Il percorso della pagina di una legge. L'URN resta leggibile: ":" e ";" sono ammessi nei percorsi. */
export const percorsoLegge = (urn: string) =>
  `/legge/${encodeURIComponent(urn).replace(/%3A/gi, ":").replace(/%3B/gi, ";")}`;

/** Il parametro della rotta /legge/[urn], che Next.js può passare ancora codificato. */
export function urnDaParametro(parametro: string): string {
  try {
    return decodeURIComponent(parametro);
  } catch {
    return parametro;
  }
}
