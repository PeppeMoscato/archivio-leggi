import Link from "next/link";

export default function NonTrovata() {
  return (
    <>
      <h1>Pagina non trovata</h1>
      <p>L&apos;atto o la pagina che cerchi non è nell&apos;archivio.</p>
      <p>
        <Link href="/cerca">Cerca una legge</Link>
      </p>
    </>
  );
}
