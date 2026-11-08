import { dataLunga, siglaPartito } from "@/lib/formato";
import { cambiPartiti, dimissionario, maggioranzaAlla, type CambioPartito } from "@/lib/partiti";
import type { GovernoConPartiti, PartitoGoverno } from "@/lib/tipi";

function Elenco({ partiti }: { partiti: PartitoGoverno[] }) {
  return partiti.map((p, i) => (
    <span key={`${p.partito}-${p.inizio ?? ""}`}>
      {i > 0 && ", "}
      <abbr title={p.partito}>{siglaPartito(p.partito)}</abbr>
    </span>
  ));
}

function Sigla({ cambio }: { cambio: CambioPartito }) {
  return (
    <abbr title={cambio.nota ? `${cambio.partito}. ${cambio.nota}` : cambio.partito}>{siglaPartito(cambio.partito)}</abbr>
  );
}

function elenca(voci: React.ReactNode[], ultima = " e ") {
  return voci.map((voce, i) => (
    <span key={i}>
      {i > 0 && (i === voci.length - 1 ? ultima : ", ")}
      {voce}
    </span>
  ));
}

// Un giorno di cambi, senza verbi che diano un motivo: "dal 14 ottobre 2007 PD; non più DS e DL".
function Giorno({ data, cambi }: { data: string; cambi: CambioPartito[] }) {
  const dentro = cambi.filter((c) => c.verso !== "esce");
  const fuori = cambi.filter((c) => c.verso === "esce");
  const fonti = [...new Set(cambi.map((c) => c.fonte_url))];
  return (
    <>
      dal {dataLunga(data)}{" "}
      {elenca(
        dentro.map((c) => (
          <>
            <Sigla cambio={c} />
            {c.ruolo === "appoggio esterno" ? " in appoggio esterno" : c.verso === "passa" ? " con ministri" : ""}
          </>
        )),
      )}
      {dentro.length > 0 && fuori.length > 0 && ", "}
      {fuori.length > 0 && <>non più {elenca(fuori.map((c) => <Sigla cambio={c} />))}</>}{" "}
      (
      {fonti.map((url, i) => (
        <span key={url}>
          {i > 0 && ", "}
          <a href={url}>{i === 0 ? "fonte" : `fonte ${i + 1}`}</a>
        </span>
      ))}
      )
    </>
  );
}

// Sotto il nome del governo: i partiti della maggioranza alla data dell'atto (con ministri e appoggio esterno),
// poi ingressi e uscite durante il governo, ognuno con la sua fonte; la nota della fonte nel tooltip.
export default function PartitiGoverno({
  governo,
  data,
  maggioranza,
}: {
  governo: GovernoConPartiti;
  data: string;
  maggioranza?: PartitoGoverno[];
}) {
  const partiti = governo.partiti ?? [];
  if (partiti.length === 0) return null;
  const allaData = maggioranza ?? maggioranzaAlla(partiti, data);
  const cambi = cambiPartiti(governo);
  const conMinistri = allaData.filter((p) => p.ruolo === "governo");
  const esterno = allaData.filter((p) => p.ruolo === "appoggio esterno");
  return (
    <>
      <span className="nota" style={{ display: "block" }}>
        {conMinistri.length > 0 ? (
          <>
            {cambi.length > 0 ? "Partiti alla data dell'atto: " : "Partiti: "}
            <Elenco partiti={conMinistri} />
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
      {cambi.length > 0 && (
        <span className="nota" style={{ display: "block" }}>
          {"Cambi durante il governo: "}
          {[...new Set(cambi.map((c) => c.data))].map((giorno, i) => (
            <span key={giorno}>
              {i > 0 && "; "}
              <Giorno data={giorno} cambi={cambi.filter((c) => c.data === giorno)} />
            </span>
          ))}
        </span>
      )}
      {governo.dimissioni && dimissionario(governo, data) && (
        <span className="nota" style={{ display: "block" }}>
          Atto del governo dimissionario: dimissioni il {dataLunga(governo.dimissioni)}
          {governo.dimissioni_fonte_url && (
            <>
              {" "}
              (<a href={governo.dimissioni_fonte_url}>fonte</a>)
            </>
          )}
          , in carica per gli affari correnti fino al giuramento del successivo.
        </span>
      )}
    </>
  );
}
