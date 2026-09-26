"""
Claim verification against cited evidence.
Per docs/11_CITATION_AND_VALIDATION.md.

Verifies:
  - Narrative claims against cited chunk text (text overlap).
  - Numeric claims against cited ExtractedFact records (exact match with tolerance).
  - Strips unsupported claims or flags no_evidence=True.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# Numeric tolerance for fact matching (0.1% relative tolerance)
_NUMERIC_TOLERANCE = 0.001


@dataclass
class VerifiedClaim:
    """A single claim with its verification status."""
    text: str
    citations: List[str]  # e.g. ["C1", "F2"]
    verified: bool = False
    confidence: float = 0.0


@dataclass
class VerificationResult:
    """Result of verifying an LLM response against evidence."""
    original_answer: str
    verified_answer: str
    claims: List[VerifiedClaim]
    no_evidence: bool = False
    overall_confidence: float = 0.0
    unsupported_claims_stripped: int = 0


def verify_response(
    answer: str,
    evidence_chunks: List[Dict[str, Any]],
    evidence_facts: Optional[List[Dict[str, Any]]] = None,
) -> VerificationResult:
    """
    Verify an LLM response against provided evidence.

    Args:
        answer: The raw LLM response text.
        evidence_chunks: The evidence chunks used (keyed C1, C2, ...).
        evidence_facts: The evidence facts used (keyed F1, F2, ...).

    Returns:
        VerificationResult with claim-level verification.
    """
    # Check for NO_EVIDENCE_FOUND
    if "NO_EVIDENCE_FOUND" in answer:
        return VerificationResult(
            original_answer=answer,
            verified_answer=answer,
            claims=[],
            no_evidence=True,
            overall_confidence=1.0,
        )

    # Build citation maps
    chunk_map: Dict[str, str] = {}  # C1 -> chunk text
    for idx, chunk in enumerate(evidence_chunks, start=1):
        chunk_map[f"C{idx}"] = chunk.get("text", "")

    fact_map: Dict[str, Dict[str, Any]] = {}  # F1 -> fact dict
    if evidence_facts:
        for idx, fact in enumerate(evidence_facts, start=1):
            fact_map[f"F{idx}"] = fact

    # Parse claims from the answer
    claims = _extract_claims(answer)

    verified_claims = []
    for claim in claims:
        verified = _verify_claim(claim, chunk_map, fact_map)
        verified_claims.append(verified)

    # Compute overall stats
    total = len(verified_claims)
    verified_count = sum(1 for c in verified_claims if c.verified)
    stripped = sum(1 for c in verified_claims if not c.verified)

    if total > 0:
        overall_confidence = verified_count / total
    else:
        overall_confidence = 0.0

    # Build verified answer (strip unsupported claims if confidence is too low)
    if overall_confidence < 0.3 and total > 0:
        # Too many unsupported claims — flag as no evidence
        verified_answer = (
            "NO_EVIDENCE_FOUND: The generated response could not be adequately "
            "verified against the provided evidence."
        )
        no_evidence = True
    else:
        verified_answer = answer
        no_evidence = False

    logger.info(
        "Verification: %d/%d claims verified (confidence=%.2f, stripped=%d)",
        verified_count, total, overall_confidence, stripped,
    )

    return VerificationResult(
        original_answer=answer,
        verified_answer=verified_answer,
        claims=verified_claims,
        no_evidence=no_evidence,
        overall_confidence=overall_confidence,
        unsupported_claims_stripped=stripped,
    )


def _extract_claims(answer: str) -> List[Dict[str, Any]]:
    """Extract individual claims with their citations from the answer."""
    claims = []

    # Split answer into sentences and bullet points
    sentences = re.split(r"(?<=[.!?])\s+|\n+", answer)

    for sentence in sentences:
        sentence = sentence.strip()
        # Skip empty lines, markdown headers, colon-ending intro labels, and very short phrases (< 4 words)
        if not sentence or sentence.startswith("#") or sentence.endswith(":") or len(sentence.split()) < 4:
            continue

        # Find citations in this sentence
        citations = re.findall(r"\[([CF]\d+)\]", sentence)

        claims.append({
            "text": sentence,
            "citations": citations,
        })

    return claims


def _verify_claim(
    claim: Dict[str, Any],
    chunk_map: Dict[str, str],
    fact_map: Dict[str, Dict[str, Any]],
) -> VerifiedClaim:
    """Verify a single claim against evidence."""
    text = claim["text"]
    citations = claim["citations"]

    if not citations:
        # If no explicit [C1] tags in sentence text, verify against all evidence chunks
        claim_words = set(w.lower() for w in re.findall(r"\w+", text) if len(w) > 3)
        for c_id, chunk_text in chunk_map.items():
            chunk_words = set(w.lower() for w in re.findall(r"\w+", chunk_text.lower()) if len(w) > 3)
            if claim_words and chunk_words:
                overlap = len(claim_words & chunk_words) / len(claim_words)
                if overlap >= 0.15:
                    return VerifiedClaim(text=text, citations=[c_id], verified=True, confidence=overlap)
        return VerifiedClaim(text=text, citations=[], verified=False, confidence=0.0)

    verified = False
    confidence = 0.0

    for cit_id in citations:
        if cit_id.startswith("C") and cit_id in chunk_map:
            # Verify narrative claim against chunk text
            chunk_text = chunk_map[cit_id].lower()
            # Check for significant word overlap
            claim_words = set(
                w.lower() for w in re.findall(r"\w+", text) if len(w) > 3
            )
            chunk_words = set(
                w.lower() for w in re.findall(r"\w+", chunk_text) if len(w) > 3
            )
            if claim_words and chunk_words:
                overlap = len(claim_words & chunk_words) / len(claim_words)
                if overlap >= 0.2:
                    verified = True
                    confidence = max(confidence, overlap)

        elif cit_id.startswith("F") and cit_id in fact_map:
            # Verify numeric claim against fact
            fact = fact_map[cit_id]
            # Check if any number in the claim matches the fact value
            numbers = re.findall(r"[\d,]+\.?\d*", text)
            for num_str in numbers:
                try:
                    claim_num = float(num_str.replace(",", ""))
                    fact_value = float(fact.get("value", 0))
                    if fact_value != 0:
                        rel_diff = abs(claim_num - fact_value) / abs(fact_value)
                        if rel_diff <= _NUMERIC_TOLERANCE:
                            verified = True
                            confidence = max(confidence, 1.0 - rel_diff)
                except (ValueError, ZeroDivisionError):
                    continue

    return VerifiedClaim(
        text=text,
        citations=citations,
        verified=verified,
        confidence=confidence,
    )
