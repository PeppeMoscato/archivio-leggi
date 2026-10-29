import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import AttesaRisveglio from "@/components/AttesaRisveglio";
import Avviso from "@/components/Avviso";
import EtichettaStato from "@/components/EtichettaStato";
import ModuloRicerca from "@/components/ModuloRicerca";
import Paginazione from "@/components/Paginazione";
import { cercaLeggi, governi as elencoGoverni, parametri, type FiltriRicerca } from "@/lib/api";
import { citazioneBreve, citazioneEstesa, percorsoLegge } from "@/lib/formato";

// Il risveglio di Render può durare un minuto: la funzione deve poter aspettare.
export const maxDuration = 120;

const PER_PAGINA = 20;
const CHIAVI = ["q", "tipo", "stato", "governo", "anno", "modificata", "ordine"] as const;

type Parametri = Record<string, string | string[] | undefined>;

function leggiFiltri(sp: Parametri): FiltriRicerca {
  const filtri: FiltriRicerca = {};
  for (const chiave of CHIAVI) {
    const valore = sp[chiave];
    const testo = (Array.isArray(valore) ? valore[0] : valore)?.trim();
    if (testo) filtri[chiave] = testo.slice(0, 200);
  }
  const pagina = Number(Array.isArray(sp.pagina) ? sp.pagina[0] : sp.pagina);
  if (Number.isInteger(pagina) && pagina > 1) filtri.pagina = pagina;
  return filtri;
}

export async function generateMetadata({ searchParams }: { searchParams: Promise<Parametri> }): Promise<Metadata> {
  const { q } = leggiFiltri(await searchParams);
  return { title: q ? `Ricerca: ${q}` : "Cerca", robots: { index: false } };
}

export default async function Cerca({ searchParams }: { searchParams: Promise<Parametri> }) {
  const filtri = leggiFiltri(await searchParams);
  return (
    <>
      <h1>Cerca una legge</h1>
      <Suspense
        key={parametri({ ...filtri })}
        fallback={
          <>
            <ModuloRicerca filtri={filtri} />
            <AttesaRisveglio cosa="Ricerca in corso" />
          </>
        }
      >
        <Risultati filtri={filtri} />
      </Suspense>
    </>
  );
}

async function Risultati({ filtri }: { filtri: FiltriRicerca }) {
  let dati;
  try {
    const [governi, risultati] = await Promise.all([elencoGoverni(), cercaLeggi(filtri, PER_PAGINA)]);
    dati = { governi, risultati };
  } catch (errore) {
    return (
      <>
        <ModuloRicerca filtri={filtri} />
        <Avviso errore={errore} riprova={`/cerca${parametri({ ...filtri })}`} />
      </>
    );
  }
  const { governi, risultati } = dati;
  const nomiGoverni = new Map(governi.map((g) => [g.id, g.nome]));
  const pagina = filtri.pagina ?? 1;

  return (
    <>
      <ModuloRicerca filtri={filtri} governi={governi} />
      <p className="conteggio" aria-live="polite">
        {risultati.totale === 0
          ? "Nessun atto trovato."
          : `${risultati.totale.toLocaleString("it-IT")} ${risultati.totale === 1 ? "atto trovato" : "atti trovati"}`}
      </p>
      {risultati.totale === 0 && filtri.q && (
        <p className="nota">
          Prova con meno parole o con una citazione come &quot;L. 241/1990&quot;. Le parole con l&apos;accento a volte
          sono scritte con l&apos;apostrofo nei titoli (&quot;pubblicita&apos;&quot;).
        </p>
      )}
      <ol className="risultati">
        {risultati.risultati.map((l) => (
          <li key={l.urn} className="risultato">
            <Link className="titolo-risultato" href={percorsoLegge(l.urn)}>
              {citazioneEstesa(l)}
            </Link>
            <p>{l.titolo}</p>
            <div className="meta">
              <EtichettaStato stato={l.stato} tipo={l.tipo} />
              <span>{citazioneBreve(l)}</span>
              {l.governo_id && <span>Governo {nomiGoverni.get(l.governo_id) ?? l.governo_id}</span>}
              {l.numero_modifiche > 0 && (
                <span>
                  {l.numero_modifiche.toLocaleString("it-IT")} {l.numero_modifiche === 1 ? "modifica" : "modifiche"}
                </span>
              )}
            </div>
          </li>
        ))}
      </ol>
      <Paginazione
        pagina={pagina}
        totale={risultati.totale}
        perPagina={PER_PAGINA}
        href={(p) => `/cerca${parametri({ ...filtri, pagina: p > 1 ? p : undefined })}`}
      />
    </>
  );
}
