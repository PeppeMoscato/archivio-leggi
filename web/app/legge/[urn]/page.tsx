import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import AttesaRisveglio from "@/components/AttesaRisveglio";
import Avviso from "@/components/Avviso";
import EtichettaStato from "@/components/EtichettaStato";
import SezioneIter from "@/components/SezioneIter";
import SezioneVotazioni, { tipoVotazione } from "@/components/SezioneVotazioni";
import Timeline from "@/components/Timeline";
import { dettaglioLegge, ErroreApi, parametri, pronunce as leggiPronunce } from "@/lib/api";
import {
  citazioneBreve,
  citazioneEstesa,
  dataLunga,
  nomeTipo,
  percorsoLegge,
  quanteRelazioni,
  urnDaParametro,
} from "@/lib/formato";
import type { LeggeDettaglio, TipoRelazione, TipoVotazione, Verso } from "@/lib/tipi";

// Il risveglio di Render può durare un minuto: la funzione deve poter aspettare.
export const maxDuration = 120;

type Parametri = Record<string, string | string[] | undefined>;
type Props = { params: Promise<{ urn: string }>; searchParams: Promise<Parametri> };

const primo = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
const numeroPagina = (v: string | string[] | undefined) => {
  const n = Number(primo(v));
  return Number.isInteger(n) && n > 1 ? n : 1;
};

async function caricaLegge(urn: string): Promise<LeggeDettaglio> {
  try {
    return await dettaglioLegge(urn);
  } catch (errore) {
    if (errore instanceof ErroreApi && errore.status === 404) notFound();
    throw errore;
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const urn = urnDaParametro((await params).urn);
  try {
    const legge = await dettaglioLegge(urn);
    return { title: `${citazioneBreve(legge)}: ${legge.titolo}`, description: `${citazioneEstesa(legge)}. ${legge.titolo}` };
  } catch {
    return { title: "Legge" };
  }
}

export default async function PaginaLegge({ params, searchParams }: Props) {
  const urn = urnDaParametro((await params).urn);
  const sp = await searchParams;
  const legge = await caricaLegge(urn);

  const verso: Verso = primo(sp.verso) === "disposte" ? "disposte" : "ricevute";
  const pagina = numeroPagina(sp.pagina);
  const vtipo = tipoVotazione(primo(sp.vtipo));
  const vpagina = numeroPagina(sp.vpagina);

  // Gli indirizzi delle sezioni tengono lo stato delle altre.
  const stato = { verso, pagina, vtipo, vpagina };
  const indirizzo = (s: typeof stato, ancora: string) =>
    `${percorsoLegge(urn)}${parametri({
      verso: s.verso === "ricevute" ? undefined : s.verso,
      pagina: s.pagina > 1 ? s.pagina : undefined,
      vtipo: s.vtipo,
      vpagina: s.vpagina > 1 ? s.vpagina : undefined,
    })}#${ancora}`;
  const hrefTimeline = (v: Verso, p: number) => indirizzo({ ...stato, verso: v, pagina: p }, "storia");
  const hrefVotazioni = (t: TipoVotazione | undefined, p: number) =>
    indirizzo({ ...stato, vtipo: t, vpagina: p }, "votazioni");

  const ricevute = somma(legge.conteggi.ricevute);
  const disposte = somma(legge.conteggi.disposte);
  const conIter = legge.conteggi.iter > 0;

  return (
    <article>
      <nav className="briciole" aria-label="Percorso">
        <Link href="/cerca">Cerca</Link> › {nomeTipo(legge.tipo)}
      </nav>
      <p className="citazione">{citazioneEstesa(legge)}</p>
      <h1 className="titolo-legge">{legge.titolo}</h1>

      <dl className="scheda">
        <div>
          <dt>Stato</dt>
          <dd>
            <EtichettaStato stato={legge.stato} tipo={legge.tipo} />
            {legge.data_abrogazione && legge.stato !== "vigente" && <> dal {dataLunga(legge.data_abrogazione)}</>}
          </dd>
        </div>
        <div>
          <dt>Governo</dt>
          <dd>
            {legge.governo ? (
              <>
                <Link href={`/cerca${parametri({ governo: legge.governo.id })}`}>{legge.governo.nome}</Link> (
                {legge.governo.presidente})
              </>
            ) : (
              "Dato non disponibile"
            )}
          </dd>
        </div>
        <div>
          <dt>Gazzetta Ufficiale</dt>
          <dd>
            {legge.gazzetta_data
              ? `${legge.gazzetta_numero ? `n. ${legge.gazzetta_numero} del ` : ""}${dataLunga(legge.gazzetta_data)}`
              : "Dato non disponibile"}
          </dd>
        </div>
        <div>
          <dt>Entrata in vigore</dt>
          <dd>{legge.data_entrata_vigore ? dataLunga(legge.data_entrata_vigore) : "Dato non disponibile"}</dd>
        </div>
        {legge.materia && (
          <div>
            <dt>Materia</dt>
            <dd>{legge.materia}</dd>
          </div>
        )}
      </dl>

      <div className="azioni">
        <a className="bottone" href={legge.link_normattiva}>
          Leggi il testo su Normattiva
        </a>
        <span className="nota">Aggiornato il {dataLunga(legge.aggiornato_il)}</span>
      </div>

      <ul className="indice" aria-label="Sezioni">
        <li>
          <a href="#storia">Storia</a>
        </li>
        {conIter && (
          <>
            <li>
              <a href="#iter">Iter parlamentare</a>
            </li>
            <li>
              <a href="#votazioni">Votazioni</a>
            </li>
          </>
        )}
        {legge.conteggi.pronunce > 0 && (
          <li>
            <a href="#consulta">Corte costituzionale</a>
          </li>
        )}
      </ul>

      <section aria-labelledby="storia">
        <h2 id="storia">Storia dell&apos;atto</h2>
        <p className="sintesi">{sintesi(legge)}</p>
        {disposte > 0 && (
          <nav className="schede-verso" aria-label="Verso delle modifiche">
            <Link href={hrefTimeline("ricevute", 1)} aria-current={verso === "ricevute"}>
              Modifiche ricevute ({ricevute.toLocaleString("it-IT")})
            </Link>
            <Link href={hrefTimeline("disposte", 1)} aria-current={verso === "disposte"}>
              Atti modificati da questo ({disposte.toLocaleString("it-IT")})
            </Link>
          </nav>
        )}
        <Suspense key={`${verso}-${pagina}`} fallback={<AttesaRisveglio cosa="Caricamento della storia" />}>
          <Timeline legge={legge} verso={verso} pagina={pagina} href={hrefTimeline} />
        </Suspense>
      </section>

      {conIter && (
        <>
          <section aria-labelledby="iter">
            <h2 id="iter">Iter parlamentare</h2>
            <Suspense fallback={<AttesaRisveglio cosa="Caricamento dell'iter" />}>
              <SezioneIter urn={urn} />
            </Suspense>
          </section>
          <section aria-labelledby="votazioni">
            <h2 id="votazioni">Votazioni in Aula</h2>
            <Suspense key={`${vtipo}-${vpagina}`} fallback={<AttesaRisveglio cosa="Caricamento delle votazioni" />}>
              <SezioneVotazioni urn={urn} tipo={vtipo} pagina={vpagina} href={hrefVotazioni} />
            </Suspense>
          </section>
        </>
      )}

      {legge.conteggi.pronunce > 0 && (
        <section aria-labelledby="consulta">
          <h2 id="consulta">Corte costituzionale</h2>
          <Suspense fallback={<AttesaRisveglio cosa="Caricamento delle pronunce" />}>
            <Pronunce urn={urn} />
          </Suspense>
        </section>
      )}
    </article>
  );
}

function somma(conteggi: Partial<Record<TipoRelazione, number>>): number {
  return Object.values(conteggi).reduce((a, b) => a + (b ?? 0), 0);
}

function sintesi(legge: LeggeDettaglio): string {
  const voci = (Object.entries(legge.conteggi.ricevute) as [TipoRelazione, number][])
    .filter(([tipo, n]) => n > 0 && tipo !== "converte")
    .sort((a, b) => b[1] - a[1])
    .map(([tipo, n]) => quanteRelazioni(tipo, n));
  const disposte = somma(legge.conteggi.disposte);
  const parti = [voci.length ? `Ha ricevuto ${elenco(voci)}.` : "Non risultano modifiche ricevute."];
  if (legge.conteggi.ricevute.converte) parti.unshift("È stato convertito in legge.");
  if (disposte > 0) parti.push(`A sua volta interviene su altri atti ${disposte.toLocaleString("it-IT")} volte.`);
  return parti.join(" ");
}

function elenco(voci: string[]): string {
  return voci.length > 1 ? `${voci.slice(0, -1).join(", ")} e ${voci.at(-1)}` : voci[0];
}

async function Pronunce({ urn }: { urn: string }) {
  let elencoPronunce;
  try {
    elencoPronunce = await leggiPronunce(urn);
  } catch (errore) {
    return <Avviso errore={errore} />;
  }
  return (
    <>
      <p className="sintesi">Sentenze che hanno dichiarato illegittime, in tutto o in parte, disposizioni dell&apos;atto.</p>
      {elencoPronunce.map((p) => (
        <div key={p.id} className="blocco">
          <div className="evento-testa">
            <span className="evento-titolo">
              {p.numero_sentenza ? `Sentenza n. ${p.numero_sentenza}` : "Sentenza"}
              {p.anno && ` del ${p.anno}`}
            </span>
            {p.articolo && <span className="etichetta">{p.articolo}</span>}
            {p.data_gazzetta && <span className="evento-data">Gazzetta Ufficiale del {dataLunga(p.data_gazzetta)}</span>}
          </div>
          <p className="nota">{p.nota}</p>
        </div>
      ))}
    </>
  );
}
