import type { Metadata } from "next";
import { FONTI, REPOSITORY } from "@/lib/fonti";

export const metadata: Metadata = { title: "Fonti" };

export default function Fonti() {
  return (
    <>
      <h1>Fonti e licenze</h1>
      <p>
        Archivio Leggi è un progetto gratuito e non commerciale. Tutti i dati vengono da fonti pubbliche e aperte; ogni
        pagina rimanda alla fonte originale.
      </p>
      <div className="tabella-scorre">
        <table>
          <thead>
            <tr>
              <th scope="col">Fonte</th>
              <th scope="col">Cosa ne usiamo</th>
              <th scope="col">Licenza</th>
            </tr>
          </thead>
          <tbody>
            {FONTI.map((f) => (
              <tr key={f.nome}>
                <td>
                  <a href={f.url}>{f.nome}</a>
                </td>
                <td>{f.cosa}</td>
                <td>{f.licenza}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {FONTI.filter((f) => f.attribuzione).map((f) => (
        <p key={f.nome} className="nota" style={{ marginTop: "1rem" }}>
          {f.attribuzione}
        </p>
      ))}
      <h2>Dati personali</h2>
      <p>
        I nomi dei parlamentari, i firmatari e i voti nominali sono pubblicati dalla Camera e dal Senato per
        trasparenza e sono riportati così come li danno le fonti. Per una correzione o una segnalazione apri una
        segnalazione sul <a href={`${REPOSITORY}/issues`}>repository del progetto</a>.
      </p>
      <h2>Aggiornamento</h2>
      <p>
        I dati si aggiornano quando girano le pipeline di raccolta: possono esserci giorni di ritardo rispetto alla
        Gazzetta Ufficiale. Il testo ufficiale delle leggi resta quello pubblicato sulla Gazzetta Ufficiale.
      </p>
    </>
  );
}
