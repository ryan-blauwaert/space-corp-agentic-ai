-- Local development and test provisioning only. Run as a PostgreSQL administrator:
--   psql -d postgres -f scripts/provision_postgresql_application_role.sql
-- Then assign the prompted password separately:
--   psql -d postgres -c '\password space_corp_app'
-- This script requires the schema to have been migrated first. It rejects an
-- application role with inherited role memberships or incorrect table ownership.

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
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_auth_members AS membership
        JOIN pg_roles AS member ON member.oid = membership.member
        WHERE member.rolname = 'space_corp_app'
    ) THEN
        RAISE EXCEPTION
            'space_corp_app must not be a member of another PostgreSQL role';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_class AS relation
        JOIN pg_namespace AS schema ON schema.oid = relation.relnamespace
        JOIN pg_roles AS owner ON owner.oid = relation.relowner
        WHERE schema.nspname = 'public'
          AND relation.relname IN ('workspaces', 'facilities')
          AND relation.relkind = 'r'
          AND owner.rolname <> 'space_corp'
    ) THEN
        RAISE EXCEPTION
            'workspaces and facilities must be owned by the space_corp migration role';
    END IF;
END
$$;
GRANT USAGE ON SCHEMA public TO space_corp_app;
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES
    ON ALL TABLES IN SCHEMA public TO space_corp_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO space_corp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON TABLES TO space_corp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO space_corp_app;

\connect space_corp_test
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_auth_members AS membership
        JOIN pg_roles AS member ON member.oid = membership.member
        WHERE member.rolname = 'space_corp_app'
    ) THEN
        RAISE EXCEPTION
            'space_corp_app must not be a member of another PostgreSQL role';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_class AS relation
        JOIN pg_namespace AS schema ON schema.oid = relation.relnamespace
        JOIN pg_roles AS owner ON owner.oid = relation.relowner
        WHERE schema.nspname = 'public'
          AND relation.relname IN ('workspaces', 'facilities')
          AND relation.relkind = 'r'
          AND owner.rolname <> 'space_corp'
    ) THEN
        RAISE EXCEPTION
            'workspaces and facilities must be owned by the space_corp migration role';
    END IF;
END
$$;
GRANT USAGE ON SCHEMA public TO space_corp_app;
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES
    ON ALL TABLES IN SCHEMA public TO space_corp_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO space_corp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON TABLES TO space_corp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO space_corp_app;
