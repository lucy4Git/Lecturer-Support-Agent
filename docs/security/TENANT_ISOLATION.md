# Tenant Isolation

Resolve tenant from authenticated context and verified host/session mapping. Include tenant keys in constraints/indexes; use row-level security or equivalent repository enforcement where appropriate; namespace object storage, search/vector indexes, cache keys, queues, metrics and logs; never treat a resource identifier as authorization; continuously test cross-tenant access.
