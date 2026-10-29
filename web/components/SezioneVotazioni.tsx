import Link from "next/link";
import Avviso from "@/components/Avviso";
import Paginazione from "@/components/Paginazione";
import { votazioni } from "@/lib/api";
import { dataLunga, NOMI_VOTAZIONE, nomeRamo } from "@/lib/formato";
import type { TipoVotazione, Votazione, VotoGruppo } from "@/lib/tipi";

const PER_PAGINA = 20;
const TIPI: TipoVotazione[] = ["finale", "fiducia", "articolo", "emendamento", "pregiudiziale", "altro"];

export const tipoVotazione = (valore: string | undefined): TipoVotazione | undefined =>
  TIPI.find((t) => t === valore);

export default async function SezioneVotazioni({
  urn,
  tipo,
  pagina,
  href,
}: {
  urn: string;
  tipo: TipoVotazione | undefined;
  pagina: number;
  href: (tipo: TipoVotazione | undefined, pagina: number) => string;
}) {
  let dati;
  try {
    dati = await votazioni(urn, tipo, pagina, PER_PAGINA);
  } catch (errore) {
    return <Avviso errore={errore} riprova={href(tipo, pagina)} />;
  }
  return (
    <>
      <nav className="filtro-voti" aria-label="Tipo di votazione">
        <Link href={href(undefined, 1)} aria-current={tipo === undefined}>
          Tutte
        </Link>
        {TIPI.map((t) => (
          <Link key={t} href={href(t, 1)} aria-current={tipo === t}>
            {NOMI_VOTAZIONE[t]}
          </Link>
        ))}
      </nav>
      {dati.totale === 0 ? (
        <p className="sintesi">
          {tipo ? "Nessuna votazione di questo tipo." : "Nessuna votazione d'Aula registrata per questo atto."}
        </p>
      ) : (
        <p className="conteggio">
          {dati.totale.toLocaleString("it-IT")} {dati.totale === 1 ? "votazione" : "votazioni"}
        </p>
      )}
      {dati.risultati.map((v) => (
        <VoceVotazione key={v.id} v={v} />
      ))}
      <Paginazione pagina={pagina} totale={dati.totale} perPagina={PER_PAGINA} href={(p) => href(tipo, p)} />
    </>
  );
}

function VoceVotazione({ v }: { v: Votazione }) {
  const si = v.favorevoli ?? 0;
  const no = v.contrari ?? 0;
  const ast = v.astenuti ?? 0;
  const tot = si + no + ast;
  const quota = (n: number) => `${tot ? (n / tot) * 100 : 0}%`;
  return (
    <div className="blocco voto">
      <div className="evento-testa">
        {v.data && (
          <time className="evento-data" dateTime={v.data}>
            {dataLunga(v.data)}
          </time>
        )}
        <span className="etichetta">{nomeRamo(v.ramo)}</span>
        <span className="etichetta">{NOMI_VOTAZIONE[v.tipo] ?? v.tipo}</span>
        {v.esito && <span className="evento-titolo">{v.esito}</span>}
      </div>
      <p>{v.descrizione}</p>
      {tot > 0 && (
        <>
          <div
            className="barra"
            role="img"
            aria-label={`${si} favorevoli, ${no} contrari, ${ast} astenuti`}
          >
            <span className="si" style={{ width: quota(si) }} />
            <span className="no" style={{ width: quota(no) }} />
            <span className="ast" style={{ width: quota(ast) }} />
          </div>
          <div className="legenda">
            <span>
              Favorevoli <b>{si}</b>
            </span>
            <span>
              Contrari <b>{no}</b>
            </span>
            <span>
              Astenuti <b>{ast}</b>
            </span>
            {v.presenti !== null && <span>Presenti {v.presenti}</span>}
            {v.maggioranza !== null && <span>Maggioranza {v.maggioranza}</span>}
          </div>
        </>
      )}
      {v.gruppi && v.gruppi.length > 0 && <VotoPerGruppo gruppi={v.gruppi} />}
      <div className="meta">
        {!v.nominale && <span>Voto non nominale: niente dettaglio per gruppo</span>}
        <a href={v.fonte_url}>Fonte</a>
      </div>
    </div>
  );
}

function VotoPerGruppo({ gruppi }: { gruppi: VotoGruppo[] }) {
  return (
    <details>
      <summary>Voto per gruppo parlamentare</summary>
      <div className="tabella-scorre">
        <table>
          <thead>
            <tr>
              <th scope="col">Gruppo</th>
              <th scope="col" className="numero">
                Favorevoli
              </th>
              <th scope="col" className="numero">
                Contrari
              </th>
              <th scope="col" className="numero">
                Astenuti
              </th>
            </tr>
          </thead>
          <tbody>
            {gruppi.map((g) => (
              <tr key={g.gruppo_id ?? "senza-gruppo"}>
                <td>{g.gruppo_id ? (g.nome ?? g.sigla ?? g.gruppo_id) : "Senza gruppo alla data del voto"}</td>
                <td className="numero">{g.favorevoli}</td>
                <td className="numero">{g.contrari}</td>
                <td className="numero">{g.astenuti}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="nota">Ogni parlamentare conta nel gruppo a cui aderiva il giorno del voto.</p>
    </details>
  );
}
