import { describe, expect, it, vi } from "vitest";
import { chiama, ErroreApi, parametri } from "./api";

function orologio() {
  let ora = 0;
  return { adesso: () => ora, attendi: async (ms: number) => void (ora += ms) };
}

const risposta = (status: number, corpo: unknown = {}) =>
  new Response(JSON.stringify(corpo), { status, headers: { "content-type": "application/json" } });

describe("chiama", () => {
  it("riprova mentre Render si sveglia", async () => {
    const f = vi
      .fn<typeof fetch>()
      .mockRejectedValueOnce(new TypeError("fetch failed"))
      .mockResolvedValueOnce(risposta(502))
      .mockResolvedValueOnce(risposta(200, { totale: 1 }));
    await expect(chiama("/leggi", { fetch: f, ...orologio() })).resolves.toEqual({ totale: 1 });
    expect(f).toHaveBeenCalledTimes(3);
  });

  it("non riprova un 404", async () => {
    const f = vi.fn<typeof fetch>().mockResolvedValue(risposta(404));
    const errore = await chiama<never>("/leggi/x", { fetch: f, ...orologio() }).catch((e: ErroreApi) => e);
    expect(errore).toBeInstanceOf(ErroreApi);
    expect(errore.status).toBe(404);
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("si arrende dopo l'attesa massima", async () => {
    const f = vi.fn<typeof fetch>().mockResolvedValue(risposta(503));
    const errore = await chiama<never>("/leggi", { fetch: f, ...orologio() }).catch((e: ErroreApi) => e);
    expect(errore.status).toBe(503);
    expect(f.mock.calls.length).toBeGreaterThan(3);
    expect(f.mock.calls.length).toBeLessThan(15);
  });
});

describe("parametri", () => {
  it("toglie i valori vuoti", () => {
    expect(parametri({ q: "fumo", tipo: "", pagina: undefined, gruppi: true })).toBe("?q=fumo&gruppi=true");
    expect(parametri({})).toBe("");
  });
});
