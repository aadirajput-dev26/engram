"""
Context builder for LLM generation.
Formats reranked chunks and extracted facts into delimited evidence blocks
with strict citation instructions.

Per docs/07_AI_QUERY_ENGINE.md and docs/11_CITATION_AND_VALIDATION.md.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


SYSTEM_PROMPT = """You are a precise, factual document analysis assistant. Your task is to answer questions using ONLY the provided evidence.

CRITICAL RULES:
1. Use ONLY the provided evidence blocks to answer. Do NOT use any prior knowledge.
2. Every statement, sentence, and bullet point in your answer MUST end with its specific citation tag (e.g. [C1], [C2], or [F1]).
3. Explicitly state which document the information was extracted from (for example: "According to <document_name> (page <page>): ... [C1]").
4. Do not include introductory conversational filler without citations.
5. For numeric claims, cite the specific fact or chunk ID.
6. If the evidence does not contain sufficient information to answer, respond with exactly: "NO_EVIDENCE_FOUND: The provided documents do not contain sufficient information to answer this question."
7. Never fabricate, infer, or extrapolate data not present in the evidence."""


def build_context(
    reranked_chunks: List[Dict[str, Any]],
    extracted_facts: Optional[List[Dict[str, Any]]] = None,
    query_text: str = "",
) -> List[Dict[str, str]]:
    """
    Build the LLM message context from reranked evidence.

    Args:
        reranked_chunks: Top-K chunks from reranking, each with
            'text', 'document_name', 'page_start', 'section_path'.
        extracted_facts: Optional structured facts matching the query.
        query_text: The user's query.

    Returns:
        List of message dicts (role, content) for the LLM.
    """
    evidence_blocks = []

    # Build chunk evidence blocks
    for idx, chunk in enumerate(reranked_chunks, start=1):
        citation_id = f"C{idx}"
        doc_name = chunk.get("document_name", "unknown")
        page = chunk.get("page_start", "?")
        section = chunk.get("section_path", "")
        text = chunk.get("text", "")
        if len(text) > 2000:
            text = text[:2000] + "... [truncated]"

        evidence_blocks.append(
            f'<evidence id="{citation_id}" doc="{doc_name}" '
            f'page="{page}" section="{section}">\n{text}\n</evidence>'
        )

    # Build fact evidence blocks
    if extracted_facts:
        for idx, fact in enumerate(extracted_facts, start=1):
            fact_id = f"F{idx}"
            metric = fact.get("metric", "")
            value = fact.get("value", "")
            unit = fact.get("unit", "")
            mine = fact.get("mine_name", "")
            period = fact.get("period_value", "")
            page = fact.get("page_number", "?")

            evidence_blocks.append(
                f'<fact id="{fact_id}" metric="{metric}" value="{value}" '
                f'unit="{unit}" mine="{mine}" period="{period}" page="{page}"/>'
            )

    evidence_text = "\n\n".join(evidence_blocks)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"## Evidence\n\n{evidence_text}\n\n## Question\n\n{query_text}",
        },
    ]

    return messages
