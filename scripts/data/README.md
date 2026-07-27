# Controlled dataset acquisition

`acquire_approved_dataset.py` downloads exactly one HTTPS resource only when its
manifest has an explicit approved status, named approver, approval timestamp,
rights information, size ceiling, and no confidential-data flag. Downloads land
in the ignored `data/quarantine/` zone and are never automatically extracted,
indexed, trained on, or moved into an authorised dataset zone.
