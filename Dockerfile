# syntax=docker/dockerfile:1
#
# Multi-stage build for the Apex Operations API.
#
# Stage 1 (builder) compiles dependencies and is discarded.
# Stage 2 (runtime) contains only the application and its runtime deps,
# running as a dedicated non-root user.

# --------------------------------------------------------------------------
# Stage 1: builder
# --------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# build-essential is needed to compile psycopg/bcrypt style wheels on arm64.
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements first so the dependency layer is cached across code changes.
COPY requirements.txt .

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# --------------------------------------------------------------------------
# Stage 2: runtime
# --------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="Apex Operations API" \
      org.opencontainers.image.description="Operations tracking API" \
      org.opencontainers.image.source="https://github.com/<org>/apex-ops-api"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production \
    PORT=8000

# Run as a dedicated non-root user. No shell tools are installed in this stage,
# which shrinks the attack surface of a compromised container.
RUN groupadd --system --gid 1001 apex \
    && useradd --system --uid 1001 --gid apex --home-dir /app --shell /usr/sbin/nologin apex

WORKDIR /app

# Copy the virtualenv from the builder stage.
COPY --from=builder /opt/venv /opt/venv

# Copy application code as root, then hand ownership to the non-root user.
COPY --chown=apex:apex app/ ./app/

USER apex

EXPOSE 8000

# Container-level health check, so `docker ps` reports health without extra tooling.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
