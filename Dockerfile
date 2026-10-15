# ArchitectureScope API (apps/api) — the container Cloud Run runs.
# Built from the repository root because the API uses the shared
# packages/domain and packages/integrations. See the deployment guide.
#
#   gcloud run deploy archscope-api --source . ...
#
# On start it applies database migrations, then serves on $PORT (Cloud Run
# sets it; 8080 otherwise).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
RUN pip install --no-cache-dir "uv==0.12.22"

# Only what the API needs: the workspace definition, the lockfile, and the three packages.
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps/api ./apps/api
RUN uv sync --frozen --no-dev --package archscope-api

# Production defaults: library files in the database (Cloud Run's disk is wiped on restart).
ENV PATH="/app/.venv/bin:$PATH" \
    ARCHSCOPE_ENVIRONMENT=production \
    ARCHSCOPE_BLOB_STORE=database

EXPOSE 8080
CMD ["sh", "-c", "python -m archscope_api.cli migrate && exec uvicorn archscope_api.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
