# GitHub and deployment security

- Keep the repository private until legal and security approval permits otherwise.
- Protect `main`; require pull requests, status checks, and reviewed production deployments.
- Enable GitHub secret scanning, push protection, CodeQL, Dependabot and dependency review.
- Store secrets in GitHub Environments, Render, Vercel, Neon, AWS, Qdrant, and SMTP secret stores—not source files.
- Never upload `.env`, database dumps, raw validation evidence, API keys, session cookies, invitation/reset tokens, seed credentials, private keys, or model binaries.
- Build immutable container images from the accepted commit; promote the same digest from staging to production where image-based deployment is used.
- Require manual production approval and retain deployment evidence.
- Rotate any credential exposed in a terminal, screenshot, chat, log, or Git history.
- Run `scripts/deployment/create_safe_release.py` before sharing a ZIP.
- Production demo seeding is blocked in both settings validation and the seed command.
