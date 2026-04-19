FROM python:3.11-slim AS builder

WORKDIR /build
# Build tools needed for packages that compile C extensions (asyncpg, cryptography, bcrypt)
# Especially required on ARM64 (Apple Silicon / Render's infrastructure)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
# Create a minimal package stub so setuptools can build the wheel and resolve
# all dependencies. The real app/ source is copied in the final stage.
RUN mkdir -p app && touch app/__init__.py
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim

WORKDIR /app
# Copy installed packages and console-scripts from the builder
COPY --from=builder /install /usr/local
# Copy the real application source
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY app/ ./app/

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
