# Local data services

The v1.3 local stack includes PostgreSQL, Redis, MinIO, and Qdrant. It is started
only when the developer runs the supplied PowerShell command; no script launches
Docker Desktop automatically.

- PostgreSQL is the transactional source of truth and enforces tenant RLS.
- MinIO stores immutable object versions.
- Qdrant stores scoped vector representations.
- Redis stores temporary operational state.
