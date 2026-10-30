import { siglaPartito } from "@/lib/formato";
import type { PartitoGoverno } from "@/lib/tipi";

function Elenco({ partiti }: { partiti: PartitoGoverno[] }) {
  return partiti.map((p, i) => (
    <span key={p.partito}>
      {i > 0 && ", "}
      <abbr title={p.partito}>{siglaPartito(p.partito)}</abbr>
    </span>
  ));
}

// Sotto il nome del governo: i partiti con ministri e quelli che lo sostenevano da fuori, con la fonte.
export default function PartitiGoverno({ partiti }: { partiti: PartitoGoverno[] }) {
  if (partiti.length === 0) return null;
  const governo = partiti.filter((p) => p.ruolo === "governo");
  const esterno = partiti.filter((p) => p.ruolo === "appoggio esterno");
  return (
    <span className="nota" style={{ display: "block" }}>
      {governo.length > 0 ? (
        <>
          Partiti: <Elenco partiti={governo} />
        </>
      ) : (
        "Governo tecnico"
      )}
      {esterno.length > 0 && (
        <>
          {"; appoggio esterno: "}
          <Elenco partiti={esterno} />
        </>
      )}{" "}
      (<a href={partiti[0].fonte_url}>fonte</a>)
    </span>
  );
}
