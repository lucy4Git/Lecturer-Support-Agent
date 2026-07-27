# Redis responsibility boundary

Redis stores only temporary operational state:

- sessions and short-lived caches;
- rate limits;
- background-job progress;
- distributed locks;
- streaming response state; and
- temporary access-expiry scheduling hints.

PostgreSQL remains authoritative for identities, assignments, content versions,
external grants, audit records, and every academic record. Redis loss must not
remove authoritative evidence.
