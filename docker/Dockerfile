# ─────────────────────────────────────────────
# EcoRecon AI — Multi-Stage Production Dockerfile
# ─────────────────────────────────────────────
# Stage 1: dependency resolution via uv
# Stage 2: lean runtime image
# ─────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────
FROM python:3.11-slim AS builder

# Install uv — fast Python package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Copy dependency manifests first (maximise layer caching)
COPY pyproject.toml .

# Install dependencies into an isolated venv
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python -r pyproject.toml --extra dev


# ── Stage 2: Runtime ──────────────────────────
FROM python:3.11-slim AS runtime

# Security: run as non-root user
RUN groupadd --gid 1001 ecorecon && \
    useradd --uid 1001 --gid ecorecon --shell /bin/bash --create-home ecorecon

WORKDIR /app

# Copy installed virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source
COPY app/ ./app/
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY .env.example .env.example
COPY pyproject.toml .

# Ensure the venv is on PATH
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

# Create data directories with correct ownership
RUN mkdir -p data/chroma_db data/erp data/compliance_docs && \
    chown -R ecorecon:ecorecon /app

USER ecorecon

EXPOSE 8000

# Healthcheck baked into the image
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Production-grade uvicorn startup
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--access-log"]
