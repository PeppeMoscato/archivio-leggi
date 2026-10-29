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
  const elenco = evento.relazioni;
  return (
    <li className={`evento ${evento.tono}`}>
      <div className="evento-testa">
        {evento.data && (
          <time className="evento-data" dateTime={evento.data}>
            {dataLunga(evento.data)}
          </time>
        )}
        <span className="evento-titolo">
          {elenco ? <TitoloRelazione r={elenco[0]} legge={legge} verso={verso} /> : evento.titolo}
        </span>
      </div>
      {evento.testo && <p>{evento.testo}</p>}
      {elenco && <DettaglioRelazioni relazioni={elenco} verso={verso} />}
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

const senzaDoppi = (valori: (string | null)[]) => [...new Set(valori.filter((v): v is string => !!v))];

function DettaglioRelazioni({ relazioni, verso }: { relazioni: Relazione[]; verso: Verso }) {
  // Gli articoli della legge della pagina e quelli dell'altro atto.
  const ricevute = verso === "ricevute";
  const qui = senzaDoppi(relazioni.map((r) => (ricevute ? r.articolo_destinazione : r.articolo_origine)));
  const la = senzaDoppi(relazioni.map((r) => (ricevute ? r.articolo_origine : r.articolo_destinazione)));
  const articoli = [
    qui.length > 0 && (ricevute ? `Interessa: ${qui.join(", ")}` : `Con: ${qui.join(", ")}`),
    la.length > 0 && (ricevute ? `disposta da: ${la.join(", ")}` : `su: ${la.join(", ")}`),
  ].filter(Boolean);
  const primo = relazioni[0];
  const fuoriArchivio = !primo.atto_collegato && (ricevute ? primo.urn_origine : primo.urn_destinazione);
  const note = senzaDoppi(relazioni.map((r) => r.nota));
  return (
    <>
      {articoli.length > 0 && <p>{articoli.join(" · ")}</p>}
      <details>
        <summary>{note.length > 1 ? `Dettagli (${note.length} note)` : "Dettagli"}</summary>
        {primo.atto_collegato && <p className="nota">{primo.atto_collegato.titolo}</p>}
        {fuoriArchivio && <p className="nota">Atto non presente nell&apos;archivio: {fuoriArchivio}</p>}
        {note.map((nota) => (
          <p key={nota} className="nota">
            Nota di aggiornamento di Normattiva: {nota}
          </p>
        ))}
      </details>
    </>
  );
}
