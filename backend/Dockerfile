FROM python:3.12-slim
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=$GIT_COMMIT
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libpq-dev gcc \
    # WeasyPrint, the Handout PDF (ADR 048)
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
# uv run would otherwise re-sync at every start and pull in the dev group
ENV UV_NO_SYNC=1

COPY . .
RUN useradd -u 10001 -m app \
    && mkdir -p /data/documents \
    && chown -R app:app /app /data
USER app
EXPOSE 8000
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
