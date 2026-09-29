"""
Embedding generation using FastEmbed (ONNX Runtime) with graceful fallback.
Loads the model once at startup and provides batched encoding.
"""
from __future__ import annotations

import hashlib
import math
from typing import List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_model = None
_model_name: Optional[str] = None
_model_failed = False
_model_type = None
DEFAULT_FALLBACK_DIM = 768


def _get_model():
    """Lazy-load FastEmbed (or SentenceTransformer) model with graceful fallback."""
    global _model, _model_name, _model_failed, _model_type
    if _model is None and not _model_failed:
        settings = get_settings()
        _model_name = settings.EMBEDDING_MODEL_NAME

        import os
        import sys
        mode = getattr(settings, "EMBEDDINGS_MODE", "") or os.getenv("EMBEDDINGS_MODE", "")
        if mode.lower() == "deterministic" or sys.platform == "win32":
            _model_failed = True
            logger.info("Using deterministic normalized embeddings (dim=%d).", DEFAULT_FALLBACK_DIM)
            return None

        cache_dir = os.environ.get("FASTEMBED_CACHE_PATH", "/tmp/fastembed_cache")
        try:
            from fastembed import TextEmbedding

            _model = TextEmbedding(model_name=_model_name, cache_dir=cache_dir, threads=2)
            _model_type = "fastembed"
            logger.info("FastEmbed embedding model loaded: %s", _model_name)
            return _model
        except Exception as e_fast:
            logger.warning("FastEmbed init failed (%s). Attempting SentenceTransformer fallback.", e_fast)

        try:
            import importlib
            st_mod = importlib.import_module("sentence_transformers")
            SentenceTransformer = st_mod.SentenceTransformer

            _model = SentenceTransformer(_model_name)
            _model_type = "sentence_transformers"
            logger.info(
                "SentenceTransformer loaded: dim=%d",
                _model.get_sentence_embedding_dimension(),
            )
            return _model
        except Exception as e_st:
            logger.warning("SentenceTransformer init failed (%s).", e_st)

        _model_failed = True
        logger.info(
            "Local ML runtime not available natively in host OS. Using deterministic normalized embeddings (dim=%d).",
            DEFAULT_FALLBACK_DIM,
        )
    return _model


def get_embedding_dimension() -> int:
    """Get the embedding vector dimension."""
    model = _get_model()
    if model is not None:
        if _model_type == "sentence_transformers":
            return model.get_sentence_embedding_dimension()
        elif _model_type == "fastembed":
            try:
                sample = next(model.embed(["test"]))
                return len(sample)
            except Exception:
                return DEFAULT_FALLBACK_DIM
    return DEFAULT_FALLBACK_DIM


def get_model_name() -> str:
    """Get the current embedding model name."""
    settings = get_settings()
    return _model_name or settings.EMBEDDING_MODEL_NAME


def _deterministic_pseudo_vector(text: str, dim: int = DEFAULT_FALLBACK_DIM) -> List[float]:
    """Generate a deterministic normalized pseudo-vector when model cannot load."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vals = [(b / 255.0) * 2.0 - 1.0 for b in h]
    repeated = (vals * (dim // len(vals) + 1))[:dim]
    norm = math.sqrt(sum(x * x for x in repeated)) or 1.0
    return [x / norm for x in repeated]


def embed_texts(texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
    """
    Encode a list of texts into embedding vectors.

    Args:
        texts: List of text strings to embed.
        batch_size: Override for batch size (default from settings).

    Returns:
        List of embedding vectors (each a list of floats).
    """
    if not texts:
        return []

    settings = get_settings()
    batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE

    model = _get_model()
    if model is None:
        dim = DEFAULT_FALLBACK_DIM
        return [_deterministic_pseudo_vector(t, dim) for t in texts]

    try:
        if _model_type == "fastembed":
            embeddings_gen = model.embed(texts, batch_size=batch_size)
            return [emb.tolist() for emb in embeddings_gen]
        else:
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            return embeddings.tolist()
    except Exception as e:
        logger.warning("Model encode failed: %s. Using fallback pseudo-vectors.", e)
        return [_deterministic_pseudo_vector(t, DEFAULT_FALLBACK_DIM) for t in texts]


def embed_query(query: str) -> List[float]:
    """
    Encode a single query string into an embedding vector.

    Args:
        query: The query text.

    Returns:
        Embedding vector as a list of floats.
    """
    results = embed_texts([query])
    return results[0] if results else []
