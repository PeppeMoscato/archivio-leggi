import { nomeStato } from "@/lib/formato";
import type { StatoAtto, TipoAtto } from "@/lib/tipi";

export default function EtichettaStato({ stato, tipo }: { stato: StatoAtto; tipo: TipoAtto }) {
  return <span className={`etichetta ${stato}`}>{nomeStato(stato, tipo)}</span>;
}
