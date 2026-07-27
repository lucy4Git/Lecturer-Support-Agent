# Owner-machine validation configuration

`owner-machine-profile.example.json` is safe to commit and upload. It contains no credentials. It defines required services, model names, validation stages, evidence location, and browser viewports.

Copy it only when a machine-specific profile is needed. Do not add secrets to validation profiles; secrets belong in the local ignored `.env` file or a production secret manager.
