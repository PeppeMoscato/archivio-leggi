import { describe, expect, it } from "vitest";
import { cambiPartiti, dimissionario, maggioranzaAlla } from "./partiti";
import type { GovernoConPartiti } from "./tipi";

const fonte = "https://it.wikipedia.org/wiki/Governo_Prodi_II";
const prodi2: GovernoConPartiti = {
  id: "prodi-2",
  nome: "Prodi II",
  presidente: "Romano Prodi",
  inizio: "2006-05-17",
  fine: "2008-05-08",
  fonte_url: fonte,
  dimissioni: "2008-01-24",
  partiti: [
    { partito: "Democratici di Sinistra (DS)", ruolo: "governo", fonte_url: fonte, inizio: "2006-05-17", fine: "2007-10-14" },
    { partito: "Partito Democratico (PD)", ruolo: "governo", fonte_url: fonte, inizio: "2007-10-14", nota: "Nasce dalla fusione" },
    { partito: "Unione Democratici per l'Europa (UDEUR)", ruolo: "governo", fonte_url: fonte, inizio: "2006-05-17", fine: "2008-01-17" },
    { partito: "Unione Democratici per l'Europa (UDEUR)", ruolo: "appoggio esterno", fonte_url: fonte, inizio: "2008-01-17", fine: "2008-01-21" },
  ],
};

describe("partiti del governo", () => {
  it("elenca ingressi, uscite e passaggi all'appoggio esterno in ordine di data", () => {
    expect(cambiPartiti(prodi2).map((c) => [c.data, c.verso, c.partito])).toEqual([
      ["2007-10-14", "esce", "Democratici di Sinistra (DS)"],
      ["2007-10-14", "entra", "Partito Democratico (PD)"],
      ["2008-01-17", "passa", "Unione Democratici per l'Europa (UDEUR)"],
      ["2008-01-21", "esce", "Unione Democratici per l'Europa (UDEUR)"],
    ]);
  });

  it("conta il giorno di inizio dentro e il giorno di fine fuori", () => {
    const sigle = (giorno: string) => maggioranzaAlla(prodi2.partiti, giorno).map((p) => `${p.partito}:${p.ruolo}`);
    expect(sigle("2007-10-13")).toContain("Democratici di Sinistra (DS):governo");
    expect(sigle("2007-10-14")).not.toContain("Democratici di Sinistra (DS):governo");
    expect(sigle("2008-01-17")).toContain("Unione Democratici per l'Europa (UDEUR):appoggio esterno");
    expect(sigle("2008-01-21").some((s) => s.includes("UDEUR"))).toBe(false);
  });

  it("riconosce gli atti del governo dimissionario", () => {
    expect(dimissionario(prodi2, "2008-01-23")).toBe(false);
    expect(dimissionario(prodi2, "2008-01-24")).toBe(true);
    expect(dimissionario({ ...prodi2, dimissioni: null }, "2008-03-01")).toBe(false);
  });
});
