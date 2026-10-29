import type { Metadata } from "next";
import Link from "next/link";
import { ATTRIBUZIONE_NORMATTIVA, FONTI, REPOSITORY } from "@/lib/fonti";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Archivio Leggi", template: "%s · Archivio Leggi" },
  description:
    "Le leggi statali italiane dal 1990: stato, modifiche, abrogazioni, iter e voti in Parlamento. Progetto gratuito e non commerciale.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="it">
      <body>
        <a className="salta" href="#contenuto">
          Vai al contenuto
        </a>
        <header className="testata">
          <div className="contenitore">
            <Link href="/" className="marchio">
              <span className="marchio-segno" aria-hidden="true">
                §
              </span>
              Archivio Leggi
            </Link>
            <nav className="menu" aria-label="Principale">
              <Link href="/cerca">Cerca</Link>
              <Link href="/fonti">Fonti</Link>
            </nav>
          </div>
        </header>
        <main id="contenuto">
          <div className="contenitore">{children}</div>
        </main>
        <footer className="piede">
          <div className="contenitore">
            <p>{ATTRIBUZIONE_NORMATTIVA}</p>
            <p>
              Iter e votazioni:{" "}
              {FONTI.filter((f) => f.nome !== "Normattiva").map((f, i, tutte) => (
                <span key={f.nome}>
                  <a href={f.url}>{f.nome}</a> ({f.licenza}){i < tutte.length - 1 ? ", " : "."}
                </span>
              ))}{" "}
              Dettagli nella pagina <Link href="/fonti">Fonti</Link>.
            </p>
            <p>
              Progetto gratuito e non commerciale. Codice e segnalazioni su <a href={REPOSITORY}>GitHub</a>.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
