import { describe, expect, it } from "vitest";
import {
  citazioneBreve,
  citazioneEstesa,
  dataLunga,
  nomeRelazione,
  nomeStato,
  percorsoLegge,
  quanteRelazioni,
  romano,
  urnDaParametro,
} from "./formato";

const sirchia = { tipo: "legge", numero: "3", data: "2003-01-16" } as const;

describe("formato", () => {
  it("scrive le date in italiano senza spostamenti di fuso", () => {
    expect(dataLunga("2003-01-16")).toBe("16 gennaio 2003");
    expect(dataLunga("1990-08-01")).toBe("1 agosto 1990");
  });

  it("cita gli atti come in Gazzetta e in forma breve", () => {
    expect(citazioneEstesa(sirchia)).toBe("Legge 16 gennaio 2003, n. 3");
    expect(citazioneBreve(sirchia)).toBe("L. 3/2003");
    expect(citazioneBreve({ tipo: "decreto legislativo", numero: "81", data: "2008-04-09" })).toBe("D.Lgs. 81/2008");
  });

  it("accorda stato e relazioni al genere dell'atto", () => {
    expect(nomeStato("abrogata", "legge")).toBe("abrogata");
    expect(nomeStato("decaduta", "decreto-legge")).toBe("decaduto");
    expect(nomeRelazione("abroga_parziale", "ricevute", "decreto legislativo")).toBe("Abrogato in parte");
    expect(nomeRelazione("modifica", "ricevute", "legge")).toBe("Modificata");
    expect(nomeRelazione("modifica", "disposte", "decreto-legge")).toBe("Modifica");
  });

  it("conta al singolare e al plurale", () => {
    expect(quanteRelazioni("modifica", 1)).toBe("1 modifica");
    expect(quanteRelazioni("abroga_parziale", 12000)).toBe("12.000 abrogazioni parziali");
  });

  it("scrive le legislature in numeri romani", () => {
    expect(romano(13)).toBe("XIII");
    expect(romano(19)).toBe("XIX");
  });

  it("tiene leggibile l'URN nel percorso e lo rilegge anche codificato", () => {
    const urn = "urn:nir:stato:legge:2003-01-16;3";
    expect(percorsoLegge(urn)).toBe("/legge/urn:nir:stato:legge:2003-01-16;3");
    expect(urnDaParametro(encodeURIComponent(urn))).toBe(urn);
    expect(urnDaParametro(urn)).toBe(urn);
  });
});
