# Official Astral UV Python 3.12 image (ARM64 / AMD64 multi-arch)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Use copy instead of hardlinks inside container
ENV UV_LINK_MODE=copy
# Ensure uploads and temporary dirs exist
ENV PYTHONUNBUFFERED=1

# Install curl for container healthcheck and create unprivileged system user/group (UID/GID 10001)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install project dependencies without development packages
RUN uv sync --frozen --no-install-project --no-dev

# Copy application source code, data and migrations
COPY src/ src/
COPY data/ data/
COPY alembic.ini ./
COPY src/infrastructure/db/alembic/ src/infrastructure/db/alembic/
COPY entrypoint.sh ./

# Sync project itself
RUN uv sync --frozen --no-dev

# Create uploads & audit logs directories and grant ownership of /app (including .venv) to appuser
RUN mkdir -p uploads/images uploads/documents logs && \
    chmod +x entrypoint.sh && \
    chown -R appuser:appgroup /app

EXPOSE 8000

USER appuser

ENTRYPOINT ["/app/entrypoint.sh"]
