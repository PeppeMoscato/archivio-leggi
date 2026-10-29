import { describe, expect, it } from "vitest";
import { eventiTimeline, perAnno, senzaConversioniDoppie } from "./timeline";
import type { LeggeDettaglio, Relazione } from "./tipi";

const decreto: LeggeDettaglio = {
  urn: "urn:nir:stato:decreto.legge:2003-01-02;1",
  tipo: "decreto-legge",
  numero: "1",
  data: "2003-01-02",
  titolo: "Decreto di prova",
  stato: "decaduta",
  data_abrogazione: "2003-03-04",
  governo_id: null,
  link_normattiva: "https://www.normattiva.it/",
  numero_modifiche: 0,
  modificata: false,
  materia: null,
  data_entrata_vigore: "2003-01-03",
  gazzetta_data: "2003-01-02",
  gazzetta_numero: 1,
  gazzetta_codice: "003G0001",
  aggiornato_il: "2026-10-27T10:00:00+00:00",
  governo: null,
  conteggi: { ricevute: {}, disposte: {}, pronunce: 0, iter: 0 },
};

function relazione(id: number, tipo: Relazione["tipo"], data: string, urnOrigine: string | null): Relazione {
  return {
    id,
    tipo,
    data,
    urn_origine: urnOrigine,
    urn_destinazione: decreto.urn,
    articolo_origine: null,
    articolo_destinazione: null,
    nota: "nota",
    origine_gazzetta_codice: null,
    origine_gazzetta_data: null,
    atto_collegato: null,
  };
}

describe("timeline", () => {
  it("mostra una sola volta la stessa conversione", () => {
    const legge = "urn:nir:stato:legge:2003-03-01;30";
    const relazioni = [
      relazione(1, "converte", "2003-03-01", legge),
      relazione(2, "converte", "2003-03-01", legge),
      relazione(3, "modifica", "2003-03-01", legge),
      relazione(4, "modifica", "2003-03-01", legge),
    ];
    expect(senzaConversioniDoppie(relazioni).map((r) => r.id)).toEqual([1, 3, 4]);
  });

  it("apre con la nascita dell'atto e chiude con la fine della vigenza", () => {
    const eventi = eventiTimeline(decreto, [relazione(1, "modifica", "2003-02-01", null)], {
      verso: "ricevute",
      primaPagina: true,
      ultimaPagina: true,
    });
    expect(eventi.map((e) => e.chiave)).toEqual(["emanazione", "gazzetta", "vigore", "r1", "fine"]);
    expect(eventi.at(-1)?.titolo).toBe("Decaduto per mancata conversione");
  });

  it("non ripete nascita e fine sulle pagine intermedie né tra gli atti modificati", () => {
    const opzioni = { primaPagina: false, ultimaPagina: false } as const;
    expect(eventiTimeline(decreto, [], { ...opzioni, verso: "ricevute" })).toEqual([]);
    expect(eventiTimeline(decreto, [], { primaPagina: true, ultimaPagina: true, verso: "disposte" })).toEqual([]);
  });

  it("raggruppa per anno", () => {
    const eventi = eventiTimeline(decreto, [relazione(1, "modifica", "2005-01-01", null)], {
      verso: "ricevute",
      primaPagina: true,
      ultimaPagina: false,
    });
    expect(perAnno(eventi).map((g) => [g.anno, g.eventi.length])).toEqual([
      ["2003", 3],
      ["2005", 1],
    ]);
  });
});
