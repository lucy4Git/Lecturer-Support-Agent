# Model Download, Storage and Updates

## Download policy

Models are downloaded only from approved registries using recorded names and digests. A model pull is an infrastructure change and must be logged. Production deployments pin approved versions or digests where the runtime supports it.

## Storage

- Do not commit model binaries to Git.
- Do not place model binaries in the distributed project ZIP.
- Keep runtime inventory under `runtime/model-inventory/`; this path is ignored by Git.
- Ensure sufficient encrypted disk capacity and backups only where licence and recovery policy require them.
- Separate model storage from institutional document object storage.

## Update workflow

1. Detect a candidate update.
2. Review release notes, licence and provenance.
3. Pull into a non-production environment.
4. Record digest and metadata.
5. Run the full AI evaluation and security suite.
6. Compare against the approved baseline.
7. Obtain approval.
8. Roll out gradually with rollback capability.
9. Retain or remove the former model according to licence and rollback policy.

## Removal

Model deletion is explicit and never part of the pull script. Before removal, confirm no active routing alias, evaluation baseline, rollback requirement or legal hold depends on it.
