# Official Astral UV Python 3.12 image (ARM64 / AMD64 multi-arch)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Use copy instead of hardlinks inside container
ENV UV_LINK_MODE=copy
# Ensure uploads and temporary dirs exist
ENV PYTHONUNBUFFERED=1

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

# Create uploads directory for persistent storage
RUN mkdir -p uploads/images uploads/documents && chmod +x entrypoint.sh

# Sync project itself
RUN uv sync --frozen --no-dev

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
