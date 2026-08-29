from pydantic import ValidationError
import pytest

from intelligence_content_engine.research.models import (
    Claim, ClaimStatus, Evidence, InformationNature, ResearchGap, ResearchPlan,
    ResearchQuestion, ResearchResult, Source, SourceType,
)


def test_source_creation():
    source = Source(name="Example", url="https://example.com", source_type=SourceType.FIRST_PARTY)
    assert source.source_type == SourceType.FIRST_PARTY
    assert str(source.url) == "https://example.com/"
    assert source.checked_date.tzinfo is not None


def test_evidence_and_claim():
    source = Source(name="Example", source_type=SourceType.PRIMARY)
    evidence = Evidence(
        source=source,
        excerpt="Exact source text",
        content_sha256="abc123",
        excerpt_verified=True,
    )
    claim = Claim(text="A verified claim", status=ClaimStatus.VERIFIED, evidence=[evidence])
    assert claim.evidence[0].source.name == "Example"
    assert claim.evidence[0].excerpt_verified is True
    assert claim.evidence[0].content_sha256 == "abc123"
    assert claim.evidence[0].retrieved_at.tzinfo is not None


def test_research_question_first_party_flag():
    question = ResearchQuestion(question="What does the target site say?", is_first_party_check=True)
    assert question.is_first_party_check is True


def test_research_plan_first_party_checks():
    plan = ResearchPlan(topic="Topic", required_first_party_checks=["About page"], required_external_checks=["Regulator source"])
    assert plan.required_first_party_checks == ["About page"]


def test_research_result_helpers():
    source = Source(name="Target", source_type=SourceType.FIRST_PARTY)
    evidence = Evidence(source=source, excerpt="Verified text")
    result = ResearchResult(topic="Topic")
    result.add_first_party_fact(Claim(text="Verified", status=ClaimStatus.VERIFIED, evidence=[evidence]))
    result.add_first_party_fact(Claim(text="Partial", status=ClaimStatus.PARTIALLY_SUPPORTED, evidence=[evidence]))
    result.add_external_fact(Claim(text="External", status=ClaimStatus.VERIFIED, evidence=[evidence]))
    result.add_research_gap(ResearchGap(question="Unknown", reason="No source"))

    assert len(result.get_all_verified_facts()) == 2
    assert len(result.get_safe_claims_for_writer()) == 3
    assert len(result.research_gaps) == 1


def test_information_nature():
    claim = Claim(text="Opinion", nature=InformationNature.OPINION)
    assert claim.nature == InformationNature.OPINION


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        Claim(text="Invalid", confidence=1.5)
    with pytest.raises(ValidationError):
        Claim(text="Invalid", confidence=-0.1)
