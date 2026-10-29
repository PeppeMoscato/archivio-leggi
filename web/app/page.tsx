import Link from "next/link";
import ModuloRicerca from "@/components/ModuloRicerca";
import Sveglia from "@/components/Sveglia";
import { API_URL } from "@/lib/api";

const ESEMPI = [
  { q: "L. 3/2003", testo: "L. 3/2003" },
  { q: "fumo", testo: "fumo" },
  { q: "d.lgs. 81/2008", testo: "d.lgs. 81/2008" },
  { q: "procedimento amministrativo", testo: "procedimento amministrativo" },
];

// La home non chiama l'API: si apre subito anche quando il server è spento, e intanto lo sveglia.
export default function Home() {
  return (
    <>
      <Sveglia url={API_URL} />
      <section className="introduzione">
        <h1>Le leggi italiane, e cosa ne è stato</h1>
        <p>
          Leggi, decreti-legge, decreti legislativi e leggi costituzionali dal 1990: se sono ancora in vigore, chi
          le ha modificate o abrogate, quale governo le ha fatte e come ha votato il Parlamento.
        </p>
      </section>
      <ModuloRicerca autofocus />
      <p className="esempi">
        Prova con:{" "}
        {ESEMPI.map((e) => (
          <Link key={e.q} href={`/cerca?q=${encodeURIComponent(e.q)}`}>
            {e.testo}
          </Link>
        ))}
      </p>
      <div className="riquadri">
        <div className="riquadro">
          <h3>Stato e storia</h3>
          <p>Per ogni atto: vigente, abrogato o decaduto, e la timeline delle modifiche ricevute nel tempo.</p>
        </div>
        <div className="riquadro">
          <h3>Parlamento</h3>
          <p>Iter, firmatari e votazioni d&apos;Aula, con il voto di ogni gruppo parlamentare.</p>
        </div>
        <div className="riquadro">
          <h3>Ha funzionato?</h3>
          <p>In arrivo: schede che misurano, a distanza di anni, se una legge ha raggiunto i suoi obiettivi.</p>
        </div>
      </div>
    </>
  );
}
