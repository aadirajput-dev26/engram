"""
Cross-encoder reranker using FastEmbed (ONNX Runtime) with graceful fallback.
Per docs/05_RETRIEVAL_AND_RERANKING.md §5.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_reranker = None
_reranker_type = None  # "fastembed" or "sentence_transformers"
_reranker_failed = False


def _get_reranker():
    """Lazy-load the cross-encoder reranker model with graceful fallback."""
    global _reranker, _reranker_type, _reranker_failed
    if _reranker is None and not _reranker_failed:
        settings = get_settings()
        model_name = settings.RERANKER_MODEL_NAME

        import os
        if os.getenv("EMBEDDINGS_MODE") == "deterministic":
            _reranker_failed = True
            logger.info("Using token overlap and reciprocal rank scoring fallback.")
            return None

        cache_dir = os.environ.get("FASTEMBED_CACHE_PATH", "/tmp/fastembed_cache")
        try:
            try:
                from fastembed.rerank.cross_encoder import TextCrossEncoder as FastReranker
            except ImportError:
                from fastembed import TextReranker as FastReranker

            _reranker = FastReranker(model_name=model_name, cache_dir=cache_dir, threads=2)
            _reranker_type = "fastembed"
            logger.info("FastEmbed reranker model loaded: %s", model_name)
            return _reranker
        except Exception as e_fast:
            logger.warning("FastEmbed TextReranker init failed (%s). Attempting SentenceTransformers CrossEncoder fallback.", e_fast)

        try:
            from sentence_transformers import CrossEncoder

            _reranker = CrossEncoder(model_name)
            _reranker_type = "sentence_transformers"
            logger.info("CrossEncoder model loaded: %s", model_name)
            return _reranker
        except Exception as e_st:
            logger.warning("SentenceTransformers CrossEncoder init failed (%s).", e_st)

        _reranker_failed = True
        logger.info("Local reranker not available natively. Falling back to RRF rank ordering.")
    return _reranker


def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Rerank candidates using a cross-encoder model or fast RRF ordering.

    Args:
        query: The user's query.
        candidates: List of candidate dicts (must have 'text' field).
        top_k: Number of top results to return (default from settings).

    Returns:
        Reranked candidates with 'rerank_score' added, sorted descending.
    """
    settings = get_settings()
    top_k = top_k or settings.RETRIEVAL_TOP_K_FINAL

    if not candidates:
        return []

    import os
    reranker_enabled = os.getenv("RERANKER_ENABLED", "false").lower() in ("true", "1", "yes")
    if not reranker_enabled:
        for i, c in enumerate(candidates):
            c["rerank_score"] = c.get("rrf_score", round(1.0 / (i + 1), 4))
        return candidates[:top_k]

    reranker = _get_reranker()
    if reranker is None:
        for i, c in enumerate(candidates):
            c["rerank_score"] = c.get("rrf_score", round(1.0 / (i + 1), 4))
        return candidates[:top_k]

    pool = candidates[:8]
    try:
        if _reranker_type == "fastembed":
            docs = [c.get("text", "")[:400] for c in pool]
            results = list(reranker.rerank(query, docs))
            for item in results:
                pool[item.index]["rerank_score"] = float(item.score)
            pool.sort(key=lambda c: c.get("rerank_score", 0.0), reverse=True)
            return pool[:top_k]
        else:
            pairs = [(query, c.get("text", "")[:400]) for c in pool]
            scores = reranker.predict(pairs)
            for candidate, score in zip(pool, scores):
                candidate["rerank_score"] = float(score)
            pool.sort(key=lambda c: c["rerank_score"], reverse=True)
            return pool[:top_k]
    except Exception as e:
        logger.warning("Reranking prediction failed: %s. Using candidate order.", e)
        for i, c in enumerate(candidates):
            c["rerank_score"] = c.get("rrf_score", round(1.0 / (i + 1), 4))
        return candidates[:top_k]
