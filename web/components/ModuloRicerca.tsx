import type { FiltriRicerca } from "@/lib/api";
import type { GovernoConAtti } from "@/lib/tipi";

const TIPI = ["legge", "decreto-legge", "decreto legislativo", "legge costituzionale"];
const STATI = ["vigente", "abrogata", "decaduta"];

// Un form GET verso /cerca: funziona anche senza JavaScript. I filtri compaiono solo se ci sono i governi.
export default function ModuloRicerca({
  filtri = {},
  governi,
  autofocus = false,
}: {
  filtri?: FiltriRicerca;
  governi?: GovernoConAtti[];
  autofocus?: boolean;
}) {
  return (
    <form action="/cerca" method="get" className="ricerca" role="search">
      <div className="ricerca-riga">
        <label htmlFor="q" className="salta">
          Cerca una legge
        </label>
        <input
          id="q"
          type="search"
          name="q"
          defaultValue={filtri.q}
          placeholder='Parole del titolo o una citazione, es. "L. 3/2003"'
          maxLength={200}
          autoFocus={autofocus}
          autoComplete="off"
        />
        <button type="submit" className="bottone">
          Cerca
        </button>
      </div>
      {governi && (
        <div className="filtri">
          <label>
            Tipo
            <select name="tipo" defaultValue={filtri.tipo ?? ""}>
              <option value="">Tutti</option>
              {TIPI.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label>
            Stato
            <select name="stato" defaultValue={filtri.stato ?? ""}>
              <option value="">Tutti</option>
              {STATI.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label>
            Governo
            <select name="governo" defaultValue={filtri.governo ?? ""}>
              <option value="">Tutti</option>
              {[...governi].reverse().map((g) => (
                <option key={g.id} value={g.id}>
                  {g.nome} ({g.inizio.slice(0, 4)})
                </option>
              ))}
            </select>
          </label>
          <label>
            Anno
            <select name="anno" defaultValue={filtri.anno ?? ""}>
              <option value="">Tutti</option>
              {anni().map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
          <label>
            Ordine
            <select name="ordine" defaultValue={filtri.ordine ?? ""}>
              <option value="">Più pertinenti</option>
              <option value="data_desc">Più recenti</option>
              <option value="data_asc">Più vecchie</option>
            </select>
          </label>
        </div>
      )}
    </form>
  );
}

function anni(): number[] {
  const ultimo = new Date().getUTCFullYear();
  return Array.from({ length: ultimo - 1990 + 1 }, (_, i) => ultimo - i);
}
