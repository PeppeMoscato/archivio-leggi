// Le risposte dell'API (api/archivio_api/modelli.py). Le date arrivano come stringhe "AAAA-MM-GG".

export type TipoAtto = "legge" | "legge costituzionale" | "decreto-legge" | "decreto legislativo";
export type StatoAtto = "vigente" | "abrogata" | "decaduta";
export type TipoRelazione = "modifica" | "abroga" | "abroga_parziale" | "converte" | "attua" | "proroga" | "delega";
export type Verso = "ricevute" | "disposte";
export type TipoVotazione = "finale" | "fiducia" | "articolo" | "emendamento" | "pregiudiziale" | "altro";

export interface Pagina<T> {
  totale: number;
  pagina: number;
  per_pagina: number;
  risultati: T[];
}

export interface LeggeSintesi {
  urn: string;
  tipo: TipoAtto;
  numero: string;
  data: string;
  titolo: string;
  stato: StatoAtto;
  data_abrogazione: string | null;
  governo_id: string | null;
  link_normattiva: string;
  numero_modifiche: number;
  modificata: boolean;
}

export interface Governo {
  id: string;
  nome: string;
  presidente: string;
  inizio: string;
  fine: string | null;
  fonte_url: string;
}

export interface GovernoConAtti extends Governo {
  numero_atti: number;
  partiti: { partito: string; ruolo: string; fonte_url: string }[];
}

export interface LeggeDettaglio extends LeggeSintesi {
  materia: string | null;
  data_entrata_vigore: string | null;
  gazzetta_data: string | null;
  gazzetta_numero: number | null;
  gazzetta_codice: string | null;
  aggiornato_il: string;
  governo: Governo | null;
  conteggi: {
    ricevute: Partial<Record<TipoRelazione, number>>;
    disposte: Partial<Record<TipoRelazione, number>>;
    pronunce: number;
    iter: number;
  };
}

export interface AttoCollegato {
  urn: string;
  tipo: TipoAtto;
  numero: string;
  data: string;
  titolo: string;
}

export interface Relazione {
  id: number;
  tipo: TipoRelazione;
  data: string | null;
  urn_origine: string | null;
  urn_destinazione: string;
  articolo_origine: string | null;
  articolo_destinazione: string | null;
  nota: string;
  origine_gazzetta_codice: string | null;
  origine_gazzetta_data: string | null;
  atto_collegato: AttoCollegato | null;
}

export interface Pronuncia {
  id: number;
  articolo: string | null;
  numero_sentenza: string | null;
  anno: number | null;
  data_gazzetta: string | null;
  gazzetta_codice: string | null;
  nota: string;
}

export interface Firmatario {
  nome: string;
  tipo: string | null;
  primo_firmatario: boolean;
  parlamentare_id: number | null;
}

export interface Fase {
  id: string;
  progressivo: number;
  ramo: "camera" | "senato";
  numero: string;
  titolo: string | null;
  data_presentazione: string | null;
  stato: string | null;
  data_stato: string | null;
  fonte_url: string;
  numero_votazioni: number;
  firmatari: Firmatario[];
}

export interface Iter {
  id: string;
  legislatura: number;
  natura: string;
  titolo: string;
  iniziativa: string | null;
  data_presentazione: string | null;
  data_approvazione: string | null;
  fonte_url: string;
  fasi: Fase[];
}

export interface VotoGruppo {
  gruppo_id: string | null;
  nome: string | null;
  sigla: string | null;
  favorevoli: number;
  contrari: number;
  astenuti: number;
}

export interface Votazione {
  id: string;
  fase_id: string;
  ramo: "camera" | "senato";
  legislatura: number;
  data: string | null;
  tipo: TipoVotazione;
  descrizione: string;
  esito: string | null;
  presenti: number | null;
  votanti: number | null;
  favorevoli: number | null;
  contrari: number | null;
  astenuti: number | null;
  maggioranza: number | null;
  nominale: boolean;
  fonte_url: string;
  gruppi: VotoGruppo[] | null;
}
