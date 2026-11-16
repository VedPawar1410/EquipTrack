"""Text -> 384-dimension vectors.

Two implementations behind one tiny interface:
- FastEmbedEmbedder: the real one. BAAI/bge-small-en-v1.5 running locally on CPU (ONNX, no PyTorch),
  so embedding costs nothing, has no rate limit, and switching LLM provider never forces a re-embed.
- HashingEmbedder: deterministic and dependency-free, for tests (no model download in CI).
  Shared words give overlapping vectors, so similarity still behaves sensibly.
"""
import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from app.core.config import settings

EMBEDDING_DIM = 384


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str, cache_dir: str | None):
        from fastembed import TextEmbedding  # imported lazily: ~1s and ~100 MB, only when first needed

        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        # query_embed adds the instruction prefix bge models were trained with for search queries.
        return next(iter(self._model.query_embed(text))).tolist()


class HashingEmbedder:
    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBEDDING_DIM
            vector[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    if settings.embedding_provider == "hashing":
        return HashingEmbedder()
    return FastEmbedEmbedder(settings.embedding_model, settings.fastembed_cache_dir)
