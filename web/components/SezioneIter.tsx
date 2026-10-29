import Avviso from "@/components/Avviso";
import { iter as leggiIter } from "@/lib/api";
import { dataBreve, nomeRamo, romano } from "@/lib/formato";
import type { Fase, Firmatario } from "@/lib/tipi";

const FIRMATARI_VISIBILI = 6;

export default async function SezioneIter({ urn }: { urn: string }) {
  let elenco;
  try {
    elenco = await leggiIter(urn);
  } catch (errore) {
    return <Avviso errore={errore} />;
  }
  if (elenco.length === 0) return <p className="sintesi">Nessun iter parlamentare registrato.</p>;
  return (
    <>
      {elenco.map((i) => (
        <div key={i.id} className="blocco">
          <h3>{i.titolo}</h3>
          <div className="meta">
            <span>{romano(i.legislatura)} legislatura</span>
            {i.natura && <span>Natura: {i.natura}</span>}
            {i.iniziativa && <span>Iniziativa {i.iniziativa}</span>}
            {i.data_presentazione && <span>Presentato il {dataBreve(i.data_presentazione)}</span>}
            {i.data_approvazione && <span>Approvato il {dataBreve(i.data_approvazione)}</span>}
            <a href={i.fonte_url}>Fonte</a>
          </div>
          {i.fasi.length > 0 && (
            <ol className="fasi">
              {i.fasi.map((f) => (
                <VoceFase key={f.id} fase={f} />
              ))}
            </ol>
          )}
        </div>
      ))}
    </>
  );
}

function VoceFase({ fase }: { fase: Fase }) {
  return (
    <li className="fase">
      <div className="evento-testa">
        <span className="evento-titolo">
          {nomeRamo(fase.ramo)} · {fase.numero}
        </span>
        {fase.stato && (
          <span className="evento-data">
            {fase.stato}
            {fase.data_stato && ` il ${dataBreve(fase.data_stato)}`}
          </span>
        )}
      </div>
      <div className="meta">
        {fase.data_presentazione && <span>Presentato il {dataBreve(fase.data_presentazione)}</span>}
        {fase.numero_votazioni > 0 && (
          <span>
            {fase.numero_votazioni.toLocaleString("it-IT")} {fase.numero_votazioni === 1 ? "votazione" : "votazioni"}
          </span>
        )}
        <a href={fase.fonte_url}>Fonte</a>
      </div>
      {fase.firmatari.length > 0 && <Firmatari firmatari={fase.firmatari} />}
    </li>
  );
}

function Firmatari({ firmatari }: { firmatari: Firmatario[] }) {
  const nome = (f: Firmatario) => (f.primo_firmatario ? <b key={f.nome}>{f.nome}</b> : <span key={f.nome}>{f.nome}</span>);
  const separati = (elenco: Firmatario[]) => elenco.flatMap((f, i) => (i ? [", ", nome(f)] : [nome(f)]));
  const visibili = firmatari.slice(0, FIRMATARI_VISIBILI);
  const altri = firmatari.slice(FIRMATARI_VISIBILI);
  return (
    <div className="firmatari">
      {firmatari.length === 1 ? "Firmatario: " : "Firmatari: "}
      {separati(visibili)}
      {altri.length > 0 && (
        <details>
          <summary>e altri {altri.length.toLocaleString("it-IT")}</summary>
          {separati(altri)}
        </details>
      )}
    </div>
  );
}
