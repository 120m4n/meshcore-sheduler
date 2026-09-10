FROM python:3.12-slim

WORKDIR /app

# Build tools for any source-built wheels (e.g. bleak/bcrypt deps on some
# platforms); removed from the final layer to keep the image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic.ini ./

RUN pip install --no-cache-dir .

EXPOSE 8000

# Runs pending migrations before serving — safe to repeat on every
# container start since Alembic no-ops when already at head.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
