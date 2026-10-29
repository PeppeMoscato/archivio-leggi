"use client";

// Errori non gestiti nelle pagine: quasi sempre l'API che non si è svegliata in tempo.
export default function Errore({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="avviso errore" role="alert">
      <h1>L&apos;archivio non risponde</h1>
      <p>
        Il server potrebbe essere ancora in fase di avvio (il piano gratuito si spegne quando nessuno lo usa). Riprova
        tra qualche secondo.
      </p>
      <button type="button" className="bottone" onClick={() => reset()}>
        Riprova
      </button>
    </div>
  );
}
