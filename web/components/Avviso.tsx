import { ErroreApi } from "@/lib/api";

/** Il messaggio per un errore dell'API, senza dettagli tecnici. */
export function messaggioErrore(errore: unknown): string {
  if (errore instanceof ErroreApi && errore.status === 422) return "Alcuni filtri non sono validi: controllali e riprova.";
  if (errore instanceof ErroreApi && errore.status === null)
    return "L'archivio non risponde. Il server potrebbe essere ancora in fase di avvio: riprova tra qualche secondo.";
  return "Qualcosa non ha funzionato nel recuperare i dati. Riprova tra qualche secondo.";
}

export default function Avviso({ errore, riprova }: { errore: unknown; riprova?: string }) {
  return (
    <div className="avviso errore" role="alert">
      <p>{messaggioErrore(errore)}</p>
      {riprova && <a href={riprova}>Riprova</a>}
    </div>
  );
}
