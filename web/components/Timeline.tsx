import Link from "next/link";
import Avviso from "@/components/Avviso";
import Paginazione from "@/components/Paginazione";
import { relazioni } from "@/lib/api";
import { citazioneBreve, dataBreve, dataLunga, nomeRelazione, percorsoLegge } from "@/lib/formato";
import { eventiTimeline, perAnno, type Evento } from "@/lib/timeline";
import type { LeggeDettaglio, Relazione, Verso } from "@/lib/tipi";

const PER_PAGINA = 50;

export default async function Timeline({
  legge,
  verso,
  pagina,
  href,
}: {
  legge: LeggeDettaglio;
  verso: Verso;
  pagina: number;
  href: (verso: Verso, pagina: number) => string;
}) {
  let dati;
  try {
    dati = await relazioni(legge.urn, verso, pagina, PER_PAGINA);
  } catch (errore) {
    return <Avviso errore={errore} riprova={href(verso, pagina)} />;
  }
  const ultima = Math.max(1, Math.ceil(dati.totale / PER_PAGINA));
  const eventi = eventiTimeline(legge, dati.risultati, {
    verso,
    primaPagina: pagina === 1,
    ultimaPagina: pagina >= ultima,
  });

  return (
    <>
      {dati.totale === 0 && verso === "disposte" && (
        <p className="sintesi">Nell&apos;archivio non risultano atti modificati da questo.</p>
      )}
      {eventi.length > 0 && (
        <ol className="timeline">
          {perAnno(eventi).map((gruppo) => (
            <li key={gruppo.anno + gruppo.eventi[0].chiave}>
              <div className="anno-timeline">{gruppo.anno}</div>
              <ol className="eventi">
                {gruppo.eventi.map((e) => (
                  <VoceEvento key={e.chiave} evento={e} legge={legge} verso={verso} />
                ))}
              </ol>
            </li>
          ))}
        </ol>
      )}
      <Paginazione pagina={pagina} totale={dati.totale} perPagina={PER_PAGINA} href={(p) => href(verso, p)} />
    </>
  );
}

function VoceEvento({ evento, legge, verso }: { evento: Evento; legge: LeggeDettaglio; verso: Verso }) {
  const r = evento.relazione;
  return (
    <li className={`evento ${evento.tono}`}>
      <div className="evento-testa">
        {evento.data && (
          <time className="evento-data" dateTime={evento.data}>
            {dataLunga(evento.data)}
          </time>
        )}
        <span className="evento-titolo">{r ? <TitoloRelazione r={r} legge={legge} verso={verso} /> : evento.titolo}</span>
      </div>
      {evento.testo && <p>{evento.testo}</p>}
      {r && <DettaglioRelazione r={r} verso={verso} />}
    </li>
  );
}

function TitoloRelazione({ r, legge, verso }: { r: Relazione; legge: LeggeDettaglio; verso: Verso }) {
  const nome = nomeRelazione(r.tipo, verso, legge.tipo);
  const atto = r.atto_collegato;
  if (atto) {
    return (
      <>
        {nome} {verso === "ricevute" ? "da " : ""}
        <Link href={percorsoLegge(atto.urn)} title={atto.titolo}>
          {citazioneBreve(atto)}
        </Link>
      </>
    );
  }
  if (verso === "ricevute" && r.origine_gazzetta_data) {
    return (
      <>
        {nome} da un atto pubblicato in Gazzetta il {dataBreve(r.origine_gazzetta_data)}
      </>
    );
  }
  return <>{nome}</>;
}

function DettaglioRelazione({ r, verso }: { r: Relazione; verso: Verso }) {
  // L'articolo della legge della pagina e quello dell'altro atto.
  const [qui, la] =
    verso === "ricevute" ? [r.articolo_destinazione, r.articolo_origine] : [r.articolo_origine, r.articolo_destinazione];
  const articoli = [
    qui && (verso === "ricevute" ? `Interessa: ${qui}` : `Con: ${qui}`),
    la && (verso === "ricevute" ? `disposta da: ${la}` : `su: ${la}`),
  ].filter(Boolean);
  const fuoriArchivio = !r.atto_collegato && (verso === "ricevute" ? r.urn_origine : r.urn_destinazione);
  return (
    <>
      {articoli.length > 0 && <p>{articoli.join(" · ")}</p>}
      <details>
        <summary>Dettagli</summary>
        {r.atto_collegato && <p className="nota">{r.atto_collegato.titolo}</p>}
        {fuoriArchivio && <p className="nota">Atto non presente nell&apos;archivio: {fuoriArchivio}</p>}
        <p className="nota">Nota di aggiornamento di Normattiva: {r.nota}</p>
      </details>
    </>
  );
}
