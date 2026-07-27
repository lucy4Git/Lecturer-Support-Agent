-- Fail-closed tenant row-level security for every table with tenant_id.
-- This file is one PostgreSQL DO statement so Alembic can execute it safely.
DO $policy$
DECLARE
    item record;
BEGIN
    FOR item IN
        SELECT c.table_schema, c.table_name
        FROM information_schema.columns c
        WHERE c.column_name = 'tenant_id'
          AND c.table_schema IN (
            'tenant','iam','academic','ingestion','content','conversation',
            'ai','source','review','audit','privacy','governance','analytics','operations'
          )
        GROUP BY c.table_schema, c.table_name
    LOOP
        EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY', item.table_schema, item.table_name);
        EXECUTE format('ALTER TABLE %I.%I FORCE ROW LEVEL SECURITY', item.table_schema, item.table_name);

        IF EXISTS (
            SELECT 1 FROM pg_policies p
            WHERE p.schemaname = item.table_schema
              AND p.tablename = item.table_name
              AND p.policyname = 'tenant_isolation'
        ) THEN
            EXECUTE format(
                'ALTER POLICY tenant_isolation ON %I.%I '
                'TO lsa_app, lsa_auth, lsa_worker '
                'USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid) '
                'WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid)',
                item.table_schema,
                item.table_name
            );
        ELSE
            EXECUTE format(
                'CREATE POLICY tenant_isolation ON %I.%I '
                'FOR ALL TO lsa_app, lsa_auth, lsa_worker '
                'USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid) '
                'WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid)',
                item.table_schema,
                item.table_name
            );
        END IF;
    END LOOP;

    -- Global identity tables are not exposed directly. These views reveal only
    -- the current institution and users with a membership in that tenant.
    EXECUTE $view$
        CREATE OR REPLACE VIEW tenant.current_institution
        WITH (security_barrier = true)
        AS
        SELECT i.*
        FROM tenant.institutions i
        WHERE i.id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    $view$;

    EXECUTE $view$
        CREATE OR REPLACE VIEW iam.current_tenant_users
        WITH (security_barrier = true)
        AS
        SELECT u.id AS user_id, u.email, u.given_name, u.family_name, u.display_name,
               u.identity_provider, u.external_subject, u.is_active,
               u.last_login_at, u.profile, u.created_at, u.updated_at,
               m.id AS membership_id, m.institutional_identifier, m.position_title,
               m.status AS membership_status
        FROM iam.users u
        JOIN iam.memberships m ON m.user_id = u.id
        WHERE m.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    $view$;

    EXECUTE 'REVOKE INSERT, UPDATE, DELETE ON iam.roles, iam.permissions, iam.role_permissions FROM lsa_app';
    EXECUTE 'REVOKE ALL ON tenant.institutions, iam.users, iam.password_credentials FROM lsa_app';
    EXECUTE 'GRANT SELECT ON tenant.current_institution, iam.current_tenant_users TO lsa_app';
END
$policy$;
