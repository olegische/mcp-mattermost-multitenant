# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev --no-editable

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Clean up the virtual environment to reduce image size
RUN find /app/.venv -name '__pycache__' -type d -exec rm -rf {} + && \
    find /app/.venv -name '*.pyc' -delete && \
    find /app/.venv -name '*.pyo' -delete && \
    find /app/.venv -name '*.pyd' -delete && \
    find /app/.venv -name 'test*' -type d -exec rm -rf {} + && \
    echo "Cleaned up .venv"

# Final stage - use slim image for smaller size
FROM python:3.12-slim-bookworm

# Install git for potential dependencies that need it
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Create a non-root user for security
RUN groupadd -r app && useradd -r -g app -d /home/app -s /bin/bash -c "App user" app && \
    mkdir -p /home/app && \
    chown -R app:app /home/app

# Set working directory
WORKDIR /app

# Copy the virtual environment from builder stage
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Copy source code
COPY --from=builder --chown=app:app /app/src /app/src

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

# Switch to non-root user
USER app

# Run the MCP server using its main entrypoint
# This ensures the environment (e.g., from .env) is set up correctly before the app runs.
CMD ["python", "-m", "src.main"]
