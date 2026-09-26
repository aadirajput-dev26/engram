"""
Maps PageIndex tree nodes into internal Section records.
Computes hierarchical section_path (e.g., "1 > 1.2 > 1.2.1")
and maintains page ranges (page_start, page_end).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.core.logging import get_logger
from app.core.pageindex.adapter import PageIndexTreeNode

logger = get_logger(__name__)


@dataclass
class MappedSection:
    """Internal section record mapped from a PageIndex tree node."""
    id: uuid.UUID
    parent_id: Optional[uuid.UUID]
    level: int
    title: str
    page_start: int  # 1-indexed
    page_end: int    # 1-indexed
    section_path: str
    summary: Optional[str] = None
    text: Optional[str] = None
    children: List["MappedSection"] = field(default_factory=list)


def map_tree_to_sections(
    tree_nodes: List[PageIndexTreeNode],
    total_pages: int,
) -> List[MappedSection]:
    """
    Recursively map PageIndex tree nodes into MappedSection records.

    Args:
        tree_nodes: List of top-level PageIndex tree nodes.
        total_pages: Total number of pages in the document.

    Returns:
        Flat list of all MappedSection records (with hierarchy via parent_id).
    """
    all_sections: List[MappedSection] = []

    def _recurse(
        nodes: List[PageIndexTreeNode],
        parent_id: Optional[uuid.UUID],
        level: int,
        path_prefix: str,
    ) -> None:
        for idx, node in enumerate(nodes, start=1):
            section_id = uuid.uuid4()

            # Compute section numbering
            section_number = str(idx)
            section_path = (
                f"{path_prefix} > {section_number}" if path_prefix else section_number
            )

            # PageIndex page_index is 0-based; convert to 1-based
            page_start = node.page_index + 1

            # Compute page_end from children or default to page_start
            page_end = _compute_page_end(node, total_pages)

            section = MappedSection(
                id=section_id,
                parent_id=parent_id,
                level=level,
                title=node.title or f"Section {section_path}",
                page_start=page_start,
                page_end=page_end,
                section_path=section_path,
                summary=node.summary,
                text=node.text,
            )
            all_sections.append(section)

            # Recurse into children
            if node.children:
                _recurse(
                    node.children,
                    parent_id=section_id,
                    level=level + 1,
                    path_prefix=section_path,
                )
                # Update children reference
                section.children = [
                    s for s in all_sections
                    if s.parent_id == section_id
                ]

    _recurse(tree_nodes, parent_id=None, level=0, path_prefix="")

    logger.info("Mapped %d sections from PageIndex tree", len(all_sections))
    return all_sections


def _compute_page_end(node: PageIndexTreeNode, total_pages: int) -> int:
    """
    Compute the page_end for a node.
    Uses the maximum page_index from all descendants, or the node's own page if leaf.
    """
    max_page = node.page_index + 1  # 1-indexed

    def _find_max(n: PageIndexTreeNode) -> None:
        nonlocal max_page
        page = n.page_index + 1
        if page > max_page:
            max_page = page
        for child in n.children:
            _find_max(child)

    for child in node.children:
        _find_max(child)

    # Clamp to total_pages
    return min(max_page, total_pages)


def get_section_for_page(
    sections: List[MappedSection], page_number: int
) -> Optional[MappedSection]:
    """Find the most specific (deepest level) section containing a given page."""
    best: Optional[MappedSection] = None
    for section in sections:
        if section.page_start <= page_number <= section.page_end:
            if best is None or section.level > best.level:
                best = section
    return best
