# The conductor (this repo). Python 3.12, served by uvicorn via the app factory.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install deps first (better layer caching), then the package.
COPY pyproject.toml README.md ./
COPY jarvis ./jarvis
RUN pip install .

# SQLite store lives on a mounted volume by default (Postgres-ready via
# JARVIS_STORE_URL). Never bake ANTHROPIC_API_KEY in (README §8).
ENV JARVIS_STORE_URL=sqlite+aiosqlite:////data/jarvis.db
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

CMD ["uvicorn", "jarvis.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
