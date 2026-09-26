"""
Unit tests for Claim Verifier.
Per docs/11_CITATION_AND_VALIDATION.md.
"""
from __future__ import annotations

from app.core.validation.claim_verifier import verify_response


def test_verify_narrative_claim_success():
    evidence_chunks = [
        {
            "text": "Coal production at the Jayant opencast mine was halted for two weeks due to heavy monsoon flooding and equipment breakdown in July 2023."
        }
    ]
    answer = "Operations at Jayant mine were suspended due to severe monsoon flooding [C1]."

    result = verify_response(answer=answer, evidence_chunks=evidence_chunks)
    assert result.no_evidence is False
    assert result.overall_confidence > 0.3
    assert result.claims[0].verified is True


def test_verify_numeric_claim_against_fact():
    evidence_facts = [
        {
            "metric": "production",
            "value": 131.5,
            "unit": "MT",
            "mine_name": "Jayant",
            "period_value": "FY2023-24",
        }
    ]
    answer = "Jayant mine reported total production of 131.5 MT in FY2023-24 [F1]."

    result = verify_response(
        answer=answer,
        evidence_chunks=[],
        evidence_facts=evidence_facts,
    )
    assert result.no_evidence is False
    assert result.claims[0].verified is True
    assert result.overall_confidence >= 0.99


def test_no_evidence_found_pass_through():
    answer = "NO_EVIDENCE_FOUND: The provided documents do not contain sufficient information."
    result = verify_response(answer=answer, evidence_chunks=[])
    assert result.no_evidence is True
    assert "NO_EVIDENCE_FOUND" in result.verified_answer


def test_unsupported_claim_detection():
    evidence_chunks = [
        {"text": "The project operates two draglines and four shovels."}
    ]
    # Answer hallucinates completely unrelated gold production
    answer = "The facility produced 500 kg of refined gold in 2021 [C1]."

    result = verify_response(answer=answer, evidence_chunks=evidence_chunks)
    # Since overlap is below threshold, claim is unsupported
    assert result.claims[0].verified is False
