-- Local development and test provisioning only. Run as a PostgreSQL administrator:
--   psql -d postgres -f scripts/provision_postgresql_application_role.sql
-- Then assign the prompted password separately:
--   psql -d postgres -c '\password space_corp_app'
-- This script requires the schema to have been migrated first. It rejects an
-- application role with inherited role memberships or incorrect table ownership.

\set ON_ERROR_STOP on

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
BEGIN;
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
          AND relation.relname IN (
              'workspaces',
              'facilities',
              'catalog_releases',
              'equipment_models',
              'equipment_units'
          )
          AND relation.relkind = 'r'
          AND owner.rolname <> 'space_corp'
    ) THEN
        RAISE EXCEPTION
            'workspace, Facility, and equipment tables must be owned by the space_corp migration role';
    END IF;
END
$$;
-- Remove grants installed by older versions, including migration-table access.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM space_corp_app;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM space_corp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public
    REVOKE ALL PRIVILEGES ON TABLES FROM space_corp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public
    REVOKE ALL PRIVILEGES ON SEQUENCES FROM space_corp_app;
GRANT USAGE ON SCHEMA public TO space_corp_app;
GRANT SELECT, INSERT ON TABLE public.facilities TO space_corp_app;
GRANT UPDATE (name, location, operational_status, updated_at)
    ON TABLE public.facilities TO space_corp_app;
GRANT SELECT ON TABLE public.catalog_releases, public.equipment_models
    TO space_corp_app;
GRANT SELECT, INSERT ON TABLE public.equipment_units TO space_corp_app;
GRANT UPDATE (operational_status, updated_at)
    ON TABLE public.equipment_units TO space_corp_app;
COMMIT;

\connect space_corp_test
BEGIN;
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
          AND relation.relname IN (
              'workspaces',
              'facilities',
              'catalog_releases',
              'equipment_models',
              'equipment_units'
          )
          AND relation.relkind = 'r'
          AND owner.rolname <> 'space_corp'
    ) THEN
        RAISE EXCEPTION
            'workspace, Facility, and equipment tables must be owned by the space_corp migration role';
    END IF;
END
$$;
-- Remove grants installed by older versions, including migration-table access.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM space_corp_app;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM space_corp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public
    REVOKE ALL PRIVILEGES ON TABLES FROM space_corp_app;
ALTER DEFAULT PRIVILEGES FOR ROLE space_corp IN SCHEMA public
    REVOKE ALL PRIVILEGES ON SEQUENCES FROM space_corp_app;
GRANT USAGE ON SCHEMA public TO space_corp_app;
GRANT SELECT, INSERT ON TABLE public.facilities TO space_corp_app;
GRANT UPDATE (name, location, operational_status, updated_at)
    ON TABLE public.facilities TO space_corp_app;
GRANT SELECT ON TABLE public.catalog_releases, public.equipment_models
    TO space_corp_app;
GRANT SELECT, INSERT ON TABLE public.equipment_units TO space_corp_app;
GRANT UPDATE (operational_status, updated_at)
    ON TABLE public.equipment_units TO space_corp_app;
COMMIT;
