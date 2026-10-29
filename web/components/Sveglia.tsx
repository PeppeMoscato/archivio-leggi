"use client";

import { useEffect } from "react";

// Sulla home, che non chiama l'API, sveglia Render mentre l'utente scrive la ricerca. "/" non tocca il
// database, quindi non sveglia Neon; `no-cors` perché la risposta non serve e così non serve CORS.
export default function Sveglia({ url }: { url: string }) {
  useEffect(() => {
    fetch(`${url}/`, { mode: "no-cors", cache: "no-store" }).catch(() => {});
  }, [url]);
  return null;
}
