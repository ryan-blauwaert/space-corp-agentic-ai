-- Local development and test provisioning only. Run as a PostgreSQL administrator:
--   psql -d postgres -f scripts/provision_postgresql_application_role.sql
-- Then assign the prompted password separately:
--   psql -d postgres -c '\password space_corp_app'

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'space_corp_app') THEN
        CREATE ROLE space_corp_app LOGIN;
    END IF;
END
$$;

ALTER ROLE space_corp_app
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS;

GRANT CONNECT ON DATABASE space_corp TO space_corp_app;
GRANT CONNECT ON DATABASE space_corp_test TO space_corp_app;

\connect space_corp
GRANT USAGE ON SCHEMA public TO space_corp_app;
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES
    ON ALL TABLES IN SCHEMA public TO space_corp_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO space_corp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON TABLES TO space_corp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO space_corp_app;

\connect space_corp_test
GRANT USAGE ON SCHEMA public TO space_corp_app;
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES
    ON ALL TABLES IN SCHEMA public TO space_corp_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO space_corp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON TABLES TO space_corp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO space_corp_app;
