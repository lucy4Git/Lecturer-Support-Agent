# Bulk Ingestion Design

Components: upload session, chunk store, batch coordinator, malware scanner, metadata extractor, classifier, duplicate detector, confirmation queue, version service, indexer and batch reporting.

Reliability: idempotency keys, client/server checksums, resumable chunks, item-level transactions, outbox events, retries, dead letters and clear partial-success reports.

Inputs may include folders, ZIP archives, multiple files and CSV/JSON manifests. Video/audio can be stored and transcribed where authorised.
