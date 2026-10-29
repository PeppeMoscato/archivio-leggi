-- Ruolo di sola lettura per l'API (docs/deploy_api.md).
--
-- Da eseguire una volta nel SQL Editor di Neon, sul database dell'archivio,
-- come il ruolo che usano le pipeline (quello del secret DATABASE_URL, di
-- solito neondb_owner): le tabelle sono sue, e i privilegi predefiniti in fondo
-- valgono per le tabelle che quel ruolo creerà in futuro (Fase 2).
--
-- Prima sostituisci SOSTITUISCI_CON_UNA_PASSWORD con una password lunga e
-- casuale, per esempio:  python -c "import secrets; print(secrets.token_urlsafe(24))"
-- Neon rifiuta le password deboli (servono almeno 60 bit di entropia).
-- Rieseguire il file non fa danni: se il ruolo esiste già la password non cambia
-- (per cambiarla: ALTER ROLE api_lettura PASSWORD '...') e i GRANT si ripetono.

DO $$
DECLARE
    parola text := 'SOSTITUISCI_CON_UNA_PASSWORD';
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'api_lettura') THEN
        IF parola LIKE 'SOSTITUISCI%' THEN
            RAISE EXCEPTION 'Metti una password vera al posto di SOSTITUISCI_CON_UNA_PASSWORD';
        END IF;
        EXECUTE format('CREATE ROLE api_lettura WITH LOGIN PASSWORD %L CONNECTION LIMIT 10', parola);
    END IF;
END
$$;

-- Le scritture le bloccano i privilegi (solo SELECT, qui sotto); questa è una seconda barriera,
-- come il READ ONLY che l'API mette su ogni transazione.
ALTER ROLE api_lettura SET default_transaction_read_only = on;
-- Una query sfuggita di mano non tiene sveglio il compute (100 CU-ore al mese sul piano Free).
ALTER ROLE api_lettura SET statement_timeout = '15s';
ALTER ROLE api_lettura SET idle_in_transaction_session_timeout = '30s';

DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO api_lettura', current_database());
END
$$;
GRANT USAGE ON SCHEMA public TO api_lettura;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO api_lettura;  -- comprende le viste (legge_estesa, voto_gruppo)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO api_lettura;
