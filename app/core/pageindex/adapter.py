"""
PageIndex SDK adapter.

Uses the verified pageindex==0.2.18 SDK for document structure intelligence.
PageIndex is used ONLY for building the hierarchical document tree —
it does NOT replace our RAG pipeline (PostgreSQL FTS, Qdrant, RRF, reranking).

Verified SDK API:
  - PageIndexLocalClient(model=..., storage_path=...)
  - PageIndexCloudClient(api_key=...)
  - client.submit_document(file_path, wait=True) -> {'doc_id', 'name'}
  - client.get_tree(doc_id, node_summary=True, include_text=True) -> {'result': [nodes]}
  - client.get_document_structure(doc_id) -> [nodes] (structure only, no text)
  - client.get_ocr(doc_id, format="page") -> {'result': [{'page_index', 'markdown'}]}
  - client.get_document(doc_id) -> {'status', 'pageNum', ...}

NOT USED (our RAG pipeline handles retrieval):
  - client.chat()
  - client.submit_query()
  - client.resolve_citations()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PageIndexTreeNode:
    """Internal representation of a PageIndex tree node."""
    title: str
    node_id: str
    page_index: int  # 0-indexed from PageIndex
    summary: Optional[str] = None
    text: Optional[str] = None
    children: List["PageIndexTreeNode"] = field(default_factory=list)


@dataclass
class PageIndexResult:
    """Result from PageIndex document processing."""
    doc_id: str
    name: str
    page_count: int
    tree: List[PageIndexTreeNode]
    page_texts: Dict[int, str]  # page_index -> markdown text
    success: bool = True
    error: Optional[str] = None


class PageIndexAdapter:
    """
    Adapter encapsulating all PageIndex SDK interactions.
    Provides clean degradation if PageIndex is unavailable.
    """

    def __init__(self):
        self._client = None
        self._mode: Optional[str] = None

    def _get_client(self):
        """Lazy-initialize the PageIndex client."""
        if self._client is not None:
            return self._client

        settings = get_settings()
        self._mode = settings.PAGEINDEX_MODE.lower() if settings.PAGEINDEX_MODE else "local"

        if self._mode in ("off", "disabled", "none"):
            raise ValueError("PageIndex is disabled by configuration")

        if not settings.LLM_API_KEY or settings.LLM_API_KEY in ("your_llm_api_key_here", "test-llm-key"):
            logger.info("PageIndex skipped: LLM_API_KEY not configured with real key")
            raise ValueError("LLM_API_KEY not configured for PageIndex")

        try:
            if self._mode == "cloud":
                from pageindex import PageIndexCloudClient

                api_key = settings.PAGEINDEX_API_KEY
                if not api_key:
                    raise ValueError(
                        "PAGEINDEX_API_KEY required for cloud mode. "
                        "Set it in .env or switch to PAGEINDEX_MODE=local."
                    )
                self._client = PageIndexCloudClient(api_key=api_key)
                logger.info("PageIndex client initialized in CLOUD mode")

            else:  # local mode
                import os
                os.environ["OPENAI_API_KEY"] = settings.LLM_API_KEY
                os.environ["GEMINI_API_KEY"] = settings.LLM_API_KEY
                os.environ["GOOGLE_API_KEY"] = settings.LLM_API_KEY
                os.environ["LITELLM_NUM_RETRIES"] = "2"
                from pageindex import PageIndexLocalClient

                self._client = PageIndexLocalClient(
                    model=settings.PAGEINDEX_MODEL_NAME,
                    storage_path=settings.PAGEINDEX_STORAGE_PATH,
                )
                logger.info(
                    "PageIndex client initialized in LOCAL mode "
                    "(model=%s, storage=%s)",
                    settings.PAGEINDEX_MODEL_NAME,
                    settings.PAGEINDEX_STORAGE_PATH,
                )

        except Exception as e:
            logger.error("Failed to initialize PageIndex client: %s", e)
            self._client = None
            raise

        return self._client

    def process_document(self, file_path: str) -> PageIndexResult:
        """
        Submit a document to PageIndex and retrieve its structure tree.

        Args:
            file_path: Path to the PDF file.

        Returns:
            PageIndexResult with the hierarchical structure tree and page texts.
        """
        try:
            client = self._get_client()

            # Submit document and wait for completion
            logger.info("Submitting document to PageIndex: %s", file_path)
            submit_result = client.submit_document(file_path, wait=True)
            doc_id = submit_result["doc_id"]
            doc_name = submit_result.get("name", "")
            logger.info(
                "Document submitted to PageIndex: doc_id=%s, name=%s",
                doc_id, doc_name,
            )

            # Get document info for page count
            doc_info = client.get_document(doc_id)
            page_count = doc_info.get("pageNum", 0)

            # Get the full structure tree with text
            tree_response = client.get_tree(
                doc_id, node_summary=True, include_text=True
            )
            raw_tree = tree_response.get("result", [])

            # Parse tree nodes recursively
            tree_nodes = _parse_tree_nodes(raw_tree) if raw_tree else []

            # Get page-level text via OCR endpoint
            page_texts: Dict[int, str] = {}
            try:
                ocr_response = client.get_ocr(doc_id, format="page")
                ocr_result = ocr_response.get("result", [])
                if ocr_result:
                    for page_entry in ocr_result:
                        page_idx = page_entry.get("page_index", 0)
                        markdown = page_entry.get("markdown", "")
                        page_texts[page_idx] = markdown
            except Exception as e:
                logger.warning("Failed to get page texts from PageIndex: %s", e)

            logger.info(
                "PageIndex processing complete: %d tree nodes, %d pages with text",
                _count_nodes(tree_nodes), len(page_texts),
            )

            return PageIndexResult(
                doc_id=doc_id,
                name=doc_name,
                page_count=page_count,
                tree=tree_nodes,
                page_texts=page_texts,
            )

        except Exception as e:
            logger.error("PageIndex processing failed: %s", e)
            return PageIndexResult(
                doc_id="",
                name="",
                page_count=0,
                tree=[],
                page_texts={},
                success=False,
                error=str(e),
            )

    def cleanup_document(self, doc_id: str) -> None:
        """Delete a document from PageIndex (cleanup)."""
        try:
            client = self._get_client()
            client.delete_document(doc_id)
            logger.info("Deleted document from PageIndex: %s", doc_id)
        except Exception as e:
            logger.warning("Failed to delete PageIndex document %s: %s", doc_id, e)


def _parse_tree_nodes(raw_nodes: list) -> List[PageIndexTreeNode]:
    """Recursively parse raw PageIndex tree nodes into internal representation."""
    result = []
    if not raw_nodes:
        return result

    # Handle case where raw_nodes is a single dict (root node)
    if isinstance(raw_nodes, dict):
        raw_nodes = [raw_nodes]

    for node in raw_nodes:
        if not isinstance(node, dict):
            continue

        parsed = PageIndexTreeNode(
            title=node.get("title", ""),
            node_id=node.get("node_id", ""),
            page_index=node.get("page_index", 0),
            summary=node.get("summary") or node.get("prefix_summary"),
            text=node.get("text"),
            children=_parse_tree_nodes(node.get("nodes", [])),
        )
        result.append(parsed)

    return result


def _count_nodes(nodes: List[PageIndexTreeNode]) -> int:
    """Count total nodes in a tree."""
    count = len(nodes)
    for node in nodes:
        count += _count_nodes(node.children)
    return count


# Module-level singleton
_adapter: Optional[PageIndexAdapter] = None


def get_pageindex_adapter() -> PageIndexAdapter:
    """Get or create the PageIndex adapter singleton."""
    global _adapter
    if _adapter is None:
        _adapter = PageIndexAdapter()
    return _adapter
