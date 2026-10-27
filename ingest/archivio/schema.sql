-- Schema dati v1.1, parte "archivio" (docs/01_schema_dati.md).
-- Idempotente: si può eseguire più volte. Le tabelle delle schede arrivano in Fase 2.

CREATE TABLE IF NOT EXISTS governo (
    id          text PRIMARY KEY,
    nome        text NOT NULL,
    presidente  text NOT NULL,
    inizio      date NOT NULL,
    fine        date,
    fonte_url   text NOT NULL,
    CHECK (fine IS NULL OR fine > inizio)
);

CREATE TABLE IF NOT EXISTS legge (
    urn                  text PRIMARY KEY,
    tipo                 text NOT NULL CHECK (tipo IN ('legge', 'legge costituzionale', 'decreto-legge', 'decreto legislativo')),
    numero               text NOT NULL,
    data                 date NOT NULL,
    titolo               text NOT NULL,
    materia              text,
    link_normattiva      text NOT NULL,
    stato                text NOT NULL CHECK (stato IN ('vigente', 'abrogata', 'decaduta')),
    data_abrogazione     date,
    data_entrata_vigore  date,
    gazzetta_data        date,
    gazzetta_numero      integer,
    gazzetta_codice      text,
    governo_id           text REFERENCES governo (id),
    aggiornato_il        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS legge_tipo_data ON legge (tipo, data);
CREATE INDEX IF NOT EXISTS legge_governo ON legge (governo_id);
CREATE INDEX IF NOT EXISTS legge_gazzetta ON legge (gazzetta_codice, gazzetta_data);

CREATE TABLE IF NOT EXISTS relazione_normativa (
    id                       bigserial PRIMARY KEY,
    urn_origine              text,
    urn_destinazione         text NOT NULL REFERENCES legge (urn) ON DELETE CASCADE,
    tipo                     text NOT NULL CHECK (tipo IN ('modifica', 'abroga', 'abroga_parziale', 'converte', 'attua', 'proroga', 'delega')),
    data                     date,
    articolo_origine         text,
    articolo_destinazione    text,
    nota                     text NOT NULL,
    origine_gazzetta_codice  text,
    origine_gazzetta_data    date
);

CREATE INDEX IF NOT EXISTS relazione_destinazione ON relazione_normativa (urn_destinazione);
CREATE INDEX IF NOT EXISTS relazione_origine ON relazione_normativa (urn_origine);

CREATE TABLE IF NOT EXISTS pronuncia_costituzionale (
    id               bigserial PRIMARY KEY,
    urn_legge        text NOT NULL REFERENCES legge (urn) ON DELETE CASCADE,
    articolo         text,
    numero_sentenza  text,
    anno             integer,
    data_gazzetta    date,
    gazzetta_codice  text,
    nota             text NOT NULL
);

CREATE INDEX IF NOT EXISTS pronuncia_legge ON pronuncia_costituzionale (urn_legge);

-- Tabella tecnica: cache della risoluzione Gazzetta → URN.
CREATE TABLE IF NOT EXISTS gazzetta_urn (
    codice_redazionale  text NOT NULL,
    data_gazzetta       date NOT NULL,
    urn                 text,
    tipo                text,
    risolto_il          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (codice_redazionale, data_gazzetta)
);

CREATE OR REPLACE VIEW legge_estesa AS
SELECT
    l.*,
    coalesce(m.numero_modifiche, 0) AS numero_modifiche,
    coalesce(m.numero_modifiche, 0) > 0 AS modificata
FROM legge l
LEFT JOIN (
    SELECT urn_destinazione, count(*) AS numero_modifiche
    FROM relazione_normativa
    WHERE tipo IN ('modifica', 'abroga_parziale', 'proroga')
    GROUP BY urn_destinazione
) m ON m.urn_destinazione = l.urn;
