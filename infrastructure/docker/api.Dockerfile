FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN addgroup --system lsa && adduser --system --ingroup lsa lsa
COPY pyproject.toml README.md LICENSE.md ./
COPY services ./services
COPY packages ./packages
COPY alembic.ini ./
RUN python -m pip install --upgrade pip && python -m pip install .
USER lsa
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
