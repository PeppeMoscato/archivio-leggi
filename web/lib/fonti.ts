// Le attribuzioni delle fonti, per il footer e per la pagina /fonti (testi in docs/03_fonti.md).

export interface Fonte {
  nome: string;
  url: string;
  cosa: string;
  licenza: string;
  attribuzione?: string;
}

export const ATTRIBUZIONE_NORMATTIVA =
  "Fonte: Normattiva (https://www.normattiva.it), Istituto Poligrafico e Zecca dello Stato, in licenza CC BY 4.0. " +
  "Testo non autentico e gratuito: l'unico testo ufficiale è quello pubblicato sulla Gazzetta Ufficiale a mezzo stampa.";

export const FONTI: Fonte[] = [
  {
    nome: "Normattiva",
    url: "https://www.normattiva.it",
    cosa: "Atti, stato, modifiche, abrogazioni e pronunce della Corte costituzionale",
    licenza: "CC BY 4.0",
    attribuzione: ATTRIBUZIONE_NORMATTIVA,
  },
  {
    nome: "Senato della Repubblica",
    url: "https://dati.senato.it",
    cosa: "Iter dei disegni di legge, firmatari, votazioni d'Aula",
    licenza: "Linked open data",
  },
  {
    nome: "Camera dei deputati",
    url: "https://dati.camera.it",
    cosa: "Iter dei progetti di legge e votazioni d'Aula",
    licenza: "CC BY-SA 4.0",
    attribuzione:
      "Fonte: Camera dei deputati (https://dati.camera.it), in licenza CC BY-SA 4.0. " +
      "I dati della Camera, anche rielaborati, si riusano con la stessa licenza.",
  },
  {
    nome: "Wikipedia",
    url: "https://en.wikipedia.org",
    cosa: "Partiti dei governi: ogni governo rimanda alla sua pagina",
    licenza: "CC BY-SA 4.0",
  },
];

export const REPOSITORY = "https://github.com/PeppeMoscato/archivio-leggi";
