-- Schema dati v1.2, parte "archivio" (docs/01_schema_dati.md).
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
-- Ricerca full text sul titolo (API, GET /leggi?q=): l'espressione deve essere uguale a quella delle query.
CREATE INDEX IF NOT EXISTS legge_titolo_fts ON legge USING gin (to_tsvector('italian', titolo));

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

-- Parlamento e governi (Task 1.2): dati.senato.it, poi dati.camera.it.

CREATE TABLE IF NOT EXISTS governo_partito (
    governo_id  text NOT NULL REFERENCES governo (id) ON DELETE CASCADE,
    partito     text NOT NULL,
    ruolo       text NOT NULL CHECK (ruolo IN ('governo', 'appoggio esterno')),
    fonte_url   text NOT NULL,
    PRIMARY KEY (governo_id, partito)
);

CREATE TABLE IF NOT EXISTS iter (
    id                  text PRIMARY KEY,
    urn                 text REFERENCES legge (urn) ON DELETE SET NULL,
    legislatura         integer NOT NULL,
    natura              text NOT NULL,
    titolo              text NOT NULL,
    iniziativa          text,
    data_presentazione  date,
    data_approvazione   date,
    numero_legge        integer,
    data_legge          date,
    fonte_url           text NOT NULL
);

CREATE INDEX IF NOT EXISTS iter_urn ON iter (urn);

CREATE TABLE IF NOT EXISTS fase_iter (
    id                  text PRIMARY KEY,
    iter_id             text NOT NULL REFERENCES iter (id) ON DELETE CASCADE,
    progressivo         integer NOT NULL,
    ramo                text NOT NULL CHECK (ramo IN ('camera', 'senato')),
    numero              text NOT NULL,
    titolo              text,
    data_presentazione  date,
    stato               text,
    data_stato          date,
    fonte_url           text NOT NULL
);

CREATE INDEX IF NOT EXISTS fase_iter_iter ON fase_iter (iter_id);

CREATE TABLE IF NOT EXISTS parlamentare (
    id         serial PRIMARY KEY,
    codice     text NOT NULL UNIQUE,
    ramo       text NOT NULL CHECK (ramo IN ('camera', 'senato')),
    nome       text,
    cognome    text,
    fonte_url  text NOT NULL
);

CREATE TABLE IF NOT EXISTS firmatario (
    id                bigserial PRIMARY KEY,
    fase_id           text NOT NULL REFERENCES fase_iter (id) ON DELETE CASCADE,
    nome              text NOT NULL,
    tipo              text,
    primo_firmatario  boolean NOT NULL DEFAULT false,
    parlamentare_id   integer REFERENCES parlamentare (id)
);

CREATE INDEX IF NOT EXISTS firmatario_fase ON firmatario (fase_id);

CREATE TABLE IF NOT EXISTS gruppo (
    id     text PRIMARY KEY,
    ramo   text NOT NULL CHECK (ramo IN ('camera', 'senato')),
    nome   text NOT NULL,
    sigla  text
);

CREATE TABLE IF NOT EXISTS denominazione_gruppo (
    gruppo_id  text NOT NULL REFERENCES gruppo (id) ON DELETE CASCADE,
    inizio     date NOT NULL,
    fine       date,
    nome       text NOT NULL,
    sigla      text,
    PRIMARY KEY (gruppo_id, inizio)
);

CREATE TABLE IF NOT EXISTS adesione_gruppo (
    parlamentare_id  integer NOT NULL REFERENCES parlamentare (id) ON DELETE CASCADE,
    gruppo_id        text NOT NULL REFERENCES gruppo (id) ON DELETE CASCADE,
    inizio           date NOT NULL,
    fine             date,
    carica           text,
    PRIMARY KEY (parlamentare_id, gruppo_id, inizio)
);

CREATE TABLE IF NOT EXISTS votazione (
    id               text PRIMARY KEY,
    fase_id          text NOT NULL REFERENCES fase_iter (id) ON DELETE CASCADE,
    ramo             text NOT NULL CHECK (ramo IN ('camera', 'senato')),
    legislatura      integer NOT NULL,
    data             date,
    tipo             text NOT NULL CHECK (tipo IN ('finale', 'fiducia', 'articolo', 'emendamento', 'pregiudiziale', 'altro')),
    descrizione      text NOT NULL,
    esito            text,
    presenti         integer,
    votanti          integer,
    favorevoli       integer,
    contrari         integer,
    astenuti         integer,
    maggioranza      integer,
    voti_favorevoli  integer[] NOT NULL DEFAULT '{}',
    voti_contrari    integer[] NOT NULL DEFAULT '{}',
    voti_astenuti    integer[] NOT NULL DEFAULT '{}',
    fonte_url        text NOT NULL
);

CREATE INDEX IF NOT EXISTS votazione_fase ON votazione (fase_id);

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

-- Voto per gruppo: ogni parlamentare conta nel gruppo a cui aderiva il giorno della votazione.
-- Se quel giorno chiude un'adesione e ne apre un'altra, vale la più recente.
CREATE OR REPLACE VIEW voto_gruppo AS
WITH voti AS (
    SELECT v.id AS votazione_id, v.data, unnest(v.voti_favorevoli) AS parlamentare_id, 'favorevole' AS voto FROM votazione v
    UNION ALL
    SELECT v.id, v.data, unnest(v.voti_contrari), 'contrario' FROM votazione v
    UNION ALL
    SELECT v.id, v.data, unnest(v.voti_astenuti), 'astenuto' FROM votazione v
)
SELECT
    voti.votazione_id,
    a.gruppo_id,
    count(*) FILTER (WHERE voti.voto = 'favorevole') AS favorevoli,
    count(*) FILTER (WHERE voti.voto = 'contrario') AS contrari,
    count(*) FILTER (WHERE voti.voto = 'astenuto') AS astenuti
FROM voti
LEFT JOIN LATERAL (
    SELECT gruppo_id FROM adesione_gruppo
    WHERE parlamentare_id = voti.parlamentare_id AND inizio <= voti.data AND (fine IS NULL OR voti.data <= fine)
    ORDER BY inizio DESC
    LIMIT 1
) a ON true
GROUP BY voti.votazione_id, a.gruppo_id;
