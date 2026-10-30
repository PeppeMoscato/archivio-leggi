import Link from "next/link";
import { Suspense } from "react";
import AttesaRisveglio from "@/components/AttesaRisveglio";
import Avviso from "@/components/Avviso";
import { iter as leggiIter, relazioni } from "@/lib/api";
import { citazioneBreve, percorsoLegge } from "@/lib/formato";
import type { LeggeDettaglio } from "@/lib/tipi";

/**
 * Perché è nata: solo fatti con fonte. Per decreti-legge e decreti legislativi le premesse del testo originale
 * ("Ritenuta la straordinaria necessità ed urgenza di..."), per i decreti legislativi la legge delega; per le leggi,
 * dove si legge la relazione illustrativa. Il giudizio sui motivi sta solo nelle schede approvate.
 */
export default function SezionePerche({ legge }: { legge: LeggeDettaglio }) {
  const decreto = legge.tipo === "decreto-legge" || legge.tipo === "decreto legislativo";
  const conIter = legge.conteggi.iter > 0;
  const decretiDelegati = legge.conteggi.disposte.delega ?? 0;
  return (
    <>
      {decreto ? <Premessa legge={legge} /> : <Relazione legge={legge} conIter={conIter} />}
      {legge.tipo === "decreto legislativo" && (legge.conteggi.ricevute.delega ?? 0) > 0 && (
        <Suspense fallback={<AttesaRisveglio cosa="Caricamento della legge delega" />}>
          <LeggeDelega urn={legge.urn} />
        </Suspense>
      )}
      {decretiDelegati > 0 && (
        <p className="sintesi">
          Questa legge ha delegato il governo: {decretiDelegati.toLocaleString("it-IT")}{" "}
          {decretiDelegati === 1 ? "decreto legislativo adottato" : "decreti legislativi adottati"} su questa delega
          (sono nella storia, tra gli atti collegati a questo).
        </p>
      )}
      <p className="nota">
        {legge.tipo === "decreto-legge" && legge.conteggi.ricevute.converte
          ? "Come è stato approvato: il Parlamento lo ha convertito in legge; iter e voti sono quelli della legge di conversione."
          : conIter
            ? "Come è stata approvata: chi l'ha proposta e come si è votato sono nelle sezioni Iter parlamentare e Votazioni."
            : legge.tipo === "decreto legislativo"
              ? "Un decreto legislativo non passa da un voto finale del Parlamento: lo adotta il governo, entro i limiti della delega."
              : null}
      </p>
    </>
  );
}

function Premessa({ legge }: { legge: LeggeDettaglio }) {
  const premessa = legge.premessa;
  if (!premessa) {
    return (
      <p className="sintesi">
        Le premesse del decreto non sono ancora nell&apos;archivio: si leggono all&apos;inizio del{" "}
        <a href={legge.link_normattiva}>testo su Normattiva</a>.
      </p>
    );
  }
  return (
    <>
      <p className="sintesi">
        {premessa.motivazioni.length > 0
          ? "Le ragioni dichiarate dal governo nelle premesse del testo originale, parola per parola:"
          : "Le premesse del testo originale non riportano motivazioni: solo le basi giuridiche citate."}
      </p>
      {premessa.motivazioni.map((m, i) => (
        <blockquote key={i} className="premessa">
          {m}
        </blockquote>
      ))}
      {premessa.proposta && <p className="nota">{premessa.proposta}</p>}
      {premessa.citazioni.length > 0 && (
        <details>
          <summary>
            Basi giuridiche, deleghe e pareri citati ({premessa.citazioni.length.toLocaleString("it-IT")})
          </summary>
          <ul className="citazioni">
            {premessa.citazioni.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </details>
      )}
      <p className="nota">
        Fonte: <a href={premessa.fonte_url}>testo originale su Normattiva</a>. Sono le parole dell&apos;atto, non una
        valutazione.
      </p>
    </>
  );
}

async function LeggeDelega({ urn }: { urn: string }) {
  let elenco;
  try {
    elenco = (await relazioni(urn, "ricevute", 1, 10, "delega")).risultati;
  } catch (errore) {
    return <Avviso errore={errore} />;
  }
  if (elenco.length === 0) return null;
  return (
    <p className="sintesi">
      Adottato su delega di{" "}
      {elenco.map((r, i) => (
        <span key={r.id}>
          {i > 0 && (i === elenco.length - 1 ? " e " : ", ")}
          {r.atto_collegato ? (
            <Link href={percorsoLegge(r.atto_collegato.urn)}>{citazioneBreve(r.atto_collegato)}</Link>
          ) : (
            (r.urn_origine ?? "legge non identificata")
          )}
          {r.articolo_origine && ` (art. ${r.articolo_origine})`}
        </span>
      ))}
      : i principi e i limiti della delega sono in quella legge.
    </p>
  );
}

function Relazione({ legge, conIter }: { legge: LeggeDettaglio; conIter: boolean }) {
  return (
    <>
      <p className="sintesi">
        Una legge non dichiara i suoi motivi nel testo: li spiega la relazione illustrativa che accompagna il disegno di
        legge quando viene presentato in Parlamento.
      </p>
      {conIter ? (
        <Suspense fallback={<AttesaRisveglio cosa="Caricamento dell'iter" />}>
          <SchedaDdl urn={legge.urn} />
        </Suspense>
      ) : (
        <p className="nota">Relazione illustrativa: dato non disponibile nell&apos;archivio.</p>
      )}
    </>
  );
}

async function SchedaDdl({ urn }: { urn: string }) {
  let elenco;
  try {
    elenco = await leggiIter(urn);
  } catch (errore) {
    return <Avviso errore={errore} />;
  }
  const primo = elenco[0];
  if (!primo) return <p className="nota">Relazione illustrativa: dato non disponibile nell&apos;archivio.</p>;
  const presentata = primo.fasi.find((f) => f.testo_presentato) ?? primo.fasi[0];
  return (
    <p className="nota">
      Il testo presentato{presentata ? ` (${presentata.numero})` : ""}, con la relazione, è nella{" "}
      <a href={primo.fonte_url}>scheda del disegno di legge</a>
      {primo.iniziativa ? `, di iniziativa ${primo.iniziativa}` : ""}.
    </p>
  );
}
