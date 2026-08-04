FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN addgroup --system lsa && adduser --system --ingroup lsa lsa
COPY pyproject.toml README.md LICENSE.md alembic.ini ./
COPY services ./services
COPY packages ./packages
COPY config ./config
COPY scripts ./scripts
COPY infrastructure/database ./infrastructure/database
RUN python -m pip install --upgrade pip && python -m pip install .
USER lsa
EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn services.api.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*' "]
