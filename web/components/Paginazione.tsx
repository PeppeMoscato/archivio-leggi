import Link from "next/link";

// "← Precedenti · Pagina 2 di 9 · Successivi →". `href` costruisce l'indirizzo di una pagina.
export default function Paginazione({
  pagina,
  totale,
  perPagina,
  href,
}: {
  pagina: number;
  totale: number;
  perPagina: number;
  href: (pagina: number) => string;
}) {
  const ultima = Math.max(1, Math.ceil(totale / perPagina));
  if (ultima <= 1) return null;
  return (
    <nav className="paginazione" aria-label="Pagine">
      {pagina > 1 ? (
        <Link href={href(pagina - 1)}>
          ← Precedenti
        </Link>
      ) : (
        <span className="vuoto">← Precedenti</span>
      )}
      <span>
        Pagina {pagina.toLocaleString("it-IT")} di {ultima.toLocaleString("it-IT")}
      </span>
      {pagina < ultima ? (
        <Link href={href(pagina + 1)}>
          Successivi →
        </Link>
      ) : (
        <span className="vuoto">Successivi →</span>
      )}
    </nav>
  );
}
