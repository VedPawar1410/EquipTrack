FROM python:3.12-slim

# No .pyc files, unbuffered logs (so `docker logs` shows output immediately)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first: this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into the image so the first upload doesn't wait on a ~70 MB download
# (and the container never needs internet access to Hugging Face at runtime).
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL} \
    FASTEMBED_CACHE_DIR=/app/.cache/fastembed
RUN python -c "import os; from fastembed import TextEmbedding; TextEmbedding(os.environ['EMBEDDING_MODEL'], cache_dir=os.environ['FASTEMBED_CACHE_DIR'])"

COPY app ./app

# Run as an unprivileged user, not root
RUN useradd --create-home appuser && chown -R appuser /app/.cache
USER appuser

EXPOSE 8000

# Production command (no --reload). docker-compose.yml overrides this for local hot reload.
# ${PORT:-8000}: hosts like Render inject PORT; locally it falls back to 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
