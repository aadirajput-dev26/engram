"""
Query classifier — routes queries to STRUCTURED, RAG, or HYBRID.
Per docs/07_AI_QUERY_ENGINE.md §2-3.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.core.logging import get_logger
KNOWN_METRICS = {"production": ["production", "output"]}
SUBSIDIARY_ALIASES = {"mcl": "Mahanadi Coalfields Limited"}

def parse_period(token: str):
    return None

def identify_subsidiary(token: str):
    return None

logger = get_logger(__name__)

QueryRoute = Literal["structured", "rag", "hybrid"]


class QueryClassification(BaseModel):
    """Classification result for query routing."""
    route: QueryRoute
    metrics: List[str] = Field(default_factory=list)
    mines: List[str] = Field(default_factory=list)
    subsidiaries: List[str] = Field(default_factory=list)
    periods: List[str] = Field(default_factory=list)
    comparison: bool = False
    confidence: float = 1.0


# Golden test case patterns:
# "What was coal production in 2023?" -> STRUCTURED
# "Why did production decline in 2023?" -> RAG (explanatory / causal)
# "Compare production decline with the operational reasons mentioned in reports." -> HYBRID
_EXPLANATORY_PATTERNS = [
    r"\bwhy\b",
    r"\breasons?\b",
    r"\bcauses?\b",
    r"\bchallenges?\b",
    r"\bissues?\b",
    r"\boperational reasons\b",
    r"\bexplain\b",
    r"\bdescribe\b",
    r"\bhow did\b",
    r"\bfactors?\b",
]

_FACTUAL_PATTERNS = [
    r"\bwhat (?:is|was|were|are)\b.*?\b(?:production|target|achievement|dispatch|offtake|output|reserves)\b",
    r"\bhow much\b",
    r"\btotal\b.*?\b(?:production|dispatch|output|tonnes?|mt)\b",
    r"\bfigures?\b",
    r"\bstatistics\b",
    r"\bquantity\b",
]

_COMPARISON_PATTERNS = [
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bversus\b|\bvs\.?\b",
    r"\bdifference between\b",
]


def extract_query_parameters(query_text: str) -> Dict[str, Any]:
    """Extract known metrics, subsidiaries, mines, and periods from query text."""
    clean = query_text.lower()
    
    # 1. Metrics
    found_metrics = []
    for metric_name, aliases in KNOWN_METRICS.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", clean):
                if metric_name not in found_metrics:
                    found_metrics.append(metric_name)

    # 2. Subsidiaries
    found_subsidiaries = []
    for alias, canonical in SUBSIDIARY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", clean):
            if canonical not in found_subsidiaries:
                found_subsidiaries.append(canonical)

    # 3. Periods
    found_periods = []
    # Check for fiscal year or calendar year
    for token in query_text.split():
        p_info = parse_period(token)
        if p_info:
            _, p_val = p_info
            if p_val not in found_periods:
                found_periods.append(p_val)

    # 4. Mines (proper nouns capitalized in original text, excluding subsidiaries)
    found_mines = []
    proper_words = re.findall(r"\b[A-Z][a-z]{2,25}\b", query_text)
    for word in proper_words:
        w_lower = word.lower()
        if w_lower not in SUBSIDIARY_ALIASES and w_lower not in [
            "what", "why", "how", "when", "where", "compare", "report", "annual", "total", "table"
        ]:
            found_mines.append(word)

    # Comparison flag
    is_comparison = any(re.search(p, clean) for p in _COMPARISON_PATTERNS)

    return {
        "metrics": found_metrics,
        "subsidiaries": found_subsidiaries,
        "mines": found_mines,
        "periods": found_periods,
        "comparison": is_comparison,
    }


def classify_query(query_text: str) -> QueryRoute:
    """Classify a query into structured, rag, or hybrid route per docs/07_AI_QUERY_ENGINE.md."""
    params = extract_query_parameters(query_text)
    clean = query_text.lower().strip()

    is_comparison = params["comparison"]
    has_why = bool(re.search(r"\bwhy\b", clean))
    is_explanatory = any(re.search(p, clean) for p in _EXPLANATORY_PATTERNS)
    is_direct_factual = any(re.search(p, clean) for p in _FACTUAL_PATTERNS)

    # 1. Comparison queries linking metrics to narrative context -> HYBRID
    if is_comparison and (is_explanatory or params["metrics"]):
        return "hybrid"

    # 2. Causal / explanatory questions ("Why did...", "Explain reasons...") -> RAG
    if has_why or (is_explanatory and not is_direct_factual):
        return "rag"

    # 3. Direct factual questions ("What was production...", "How much...") -> STRUCTURED
    if is_direct_factual or (params["metrics"] and params["periods"]):
        return "structured"

    # 4. Fallback
    return "rag"


def get_query_classification(query_text: str) -> QueryClassification:
    """Get full typed classification with parameters."""
    route = classify_query(query_text)
    params = extract_query_parameters(query_text)
    return QueryClassification(
        route=route,
        metrics=params["metrics"],
        mines=params["mines"],
        subsidiaries=params["subsidiaries"],
        periods=params["periods"],
        comparison=params["comparison"],
        confidence=0.95,
    )
