// Mentre una pagina aspetta l'API. Se l'attesa dura più di qualche secondo è quasi sempre il risveglio di
// Render (piano Free, si spegne dopo 15 minuti senza visite): lo si dice, così nessuno pensa a un guasto.
// Il messaggio lungo compare dopo 3 secondi con una regola CSS: i fallback di Suspense ancora in attesa non
// vengono idratati da React, quindi un timer in JavaScript non partirebbe.
export default function AttesaRisveglio({ cosa = "Caricamento" }: { cosa?: string }) {
  return (
    <div className="attesa" role="status" aria-live="polite">
      <span className="rotella" aria-hidden="true" />
      <div>
        <p>{cosa}…</p>
        <p className="piccolo ritardato">
          L&apos;archivio si sta svegliando. Il server gratuito si spegne dopo un quarto d&apos;ora senza visite e la
          prima richiesta può richiedere fino a un minuto. Le pagine successive saranno veloci.
        </p>
      </div>
    </div>
  );
}
