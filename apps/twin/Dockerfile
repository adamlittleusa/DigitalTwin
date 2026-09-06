# Build from the repo root:  docker build -f apps/twin/Dockerfile -t twin-api .
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    KNOWLEDGE_DIR=/app/knowledge \
    PORT=8080

WORKDIR /app/apps/twin

# Dependencies first, for layer caching.
COPY apps/twin/pyproject.toml apps/twin/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# The package itself.
COPY apps/twin/twin ./twin
RUN uv sync --frozen --no-dev --no-editable

# Only the reviewed knowledge; never knowledge/raw.
COPY knowledge/*.md /app/knowledge/
COPY knowledge/roles /app/knowledge/roles
COPY knowledge/topics /app/knowledge/topics
COPY knowledge/projects /app/knowledge/projects

RUN useradd --create-home twin && chown -R twin /app
USER twin

ENV PATH="/app/apps/twin/.venv/bin:$PATH"
EXPOSE 8080
CMD ["twin-api"]
