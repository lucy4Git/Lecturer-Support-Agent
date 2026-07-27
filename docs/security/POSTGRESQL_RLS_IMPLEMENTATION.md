# PostgreSQL Row-Level Security Implementation

## Security objective

Private records from one institution must never be returned or written while a
request is executing in another institution's context.

## Enforcement layers

1. **Identity validation:** a future production identity provider supplies trusted tenant and user claims.
2. **Transaction context:** `set_config(..., true)` writes tenant, user, role, and correlation identifiers for the current transaction only.
3. **RLS:** every table containing `tenant_id` has RLS enabled and forced.
4. **Permission service:** explicit role permissions and scope assignments narrow authorised actions.
5. **Domain checks:** module, programme, and descendant organisational scopes are resolved through physical relationships.
6. **Vector filter:** Qdrant filters always include the trusted tenant ID.
7. **Object namespace:** object keys begin with the trusted tenant ID.

## Policy

The baseline policy is fail-closed:

```sql
USING (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
)
```

If the setting is missing, no tenant row matches. The application role does not
have `BYPASSRLS`, superuser, database-creation, or role-creation privileges.

## Trust boundary

Custom PostgreSQL settings are not authentication. The database credential must
remain server-side and unavailable to users. Raw user-controlled SQL must never
be executed. The production API must derive context from verified identity
claims, not request headers.

## Test requirement

The integration test sets a tenant context, confirms only that tenant's
memberships are visible, confirms an explicit cross-tenant query returns zero,
and confirms a cross-tenant insert is rejected.
