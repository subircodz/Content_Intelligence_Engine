from datetime import datetime

from pydantic import ValidationError
import pytest

from power_win_content.research.models import (
    SourceType,
    ClaimStatus,
    InformationNature,
    Source,
    Evidence,
    Claim,
    ResearchGap,
    ConflictingClaim,
    ResearchQuestion,
    ResearchPlan,
    ResearchResult,
)


def test_source_creation_valid() -> None:
    """Test that a valid source can be created with all fields."""
    source = Source(
        name="Power.win Editorial Guidelines",
        url="https://power.win/editorial-guidelines",
        source_type=SourceType.FIRST_PARTY,
        title="Our Editorial Process",
        publication_date=datetime(2024, 1, 15),
        updated_date=datetime(2024, 6, 1),
        notes="Official methodology page",
    )
    assert source.name == "Power.win Editorial Guidelines"
    assert source.source_type == SourceType.FIRST_PARTY
    assert str(source.url) == "https://power.win/editorial-guidelines"


def test_source_creation_minimal() -> None:
    """Test that a source can be created with only required fields."""
    source = Source(name="Test Source")
    assert source.name == "Test Source"
    assert source.source_type == SourceType.UNKNOWN
    assert source.checked_date is not None


def test_source_invalid_url_rejected() -> None:
    """Test that invalid URLs are rejected."""
    with pytest.raises(ValidationError):
        Source(name="Test", url="not-a-url")


def test_evidence_associated_with_claim() -> None:
    """Test that evidence can be created and associated with a claim."""
    source = Source(name="Test Source", source_type=SourceType.PRIMARY)
    evidence = Evidence(source=source, excerpt="Relevant text from the source")
    claim = Claim(
        text="Power.win uses a 10-point scoring system",
        status=ClaimStatus.VERIFIED,
        evidence=[evidence],
    )
    assert len(claim.evidence) == 1
    assert claim.evidence[0].excerpt == "Relevant text from the source"
    assert claim.evidence[0].source.name == "Test Source"


def test_claim_status_enum_works() -> None:
    """Test that claim status enum values work correctly."""
    claim = Claim(text="Test claim", status=ClaimStatus.VERIFIED)
    assert claim.status == ClaimStatus.VERIFIED

    claim.status = ClaimStatus.PARTIALLY_SUPPORTED
    assert claim.status == ClaimStatus.PARTIALLY_SUPPORTED

    claim.status = ClaimStatus.UNSUPPORTED
    assert claim.status == ClaimStatus.UNSUPPORTED

    claim.status = ClaimStatus.CONFLICTING
    assert claim.status == ClaimStatus.CONFLICTING

    claim.status = ClaimStatus.UNCERTAIN
    assert claim.status == ClaimStatus.UNCERTAIN


def test_information_nature_enum_works() -> None:
    """Test that information nature enum works correctly."""
    claim = Claim(text="Test claim", nature=InformationNature.FACT)
    assert claim.nature == InformationNature.FACT

    claim.nature = InformationNature.EDITORIAL_INTERPRETATION
    assert claim.nature == InformationNature.EDITORIAL_INTERPRETATION

    claim.nature = InformationNature.OPINION
    assert claim.nature == InformationNature.OPINION


def test_research_gap_representation() -> None:
    """Test that research gaps can be represented."""
    gap = ResearchGap(
        question="Does Power.win use a numerical casino scoring system?",
        reason="No reliable source found on Power.win or affiliated sites",
        attempted_sources=["https://power.win/about", "https://power.win/reviews"],
        importance="high",
    )
    assert gap.question == "Does Power.win use a numerical casino scoring system?"
    assert gap.importance == "high"
    assert len(gap.attempted_sources) == 2


def test_conflicting_information_representation() -> None:
    """Test that conflicting information can be represented."""
    source_a = Source(name="Source A", source_type=SourceType.PRIMARY)
    source_b = Source(name="Source B", source_type=SourceType.SECONDARY)

    claim_a = Claim(
        text="Power.win scores casinos 1-10",
        status=ClaimStatus.VERIFIED,
        evidence=[Evidence(source=source_a, excerpt="We use a 10-point scale")],
    )
    claim_b = Claim(
        text="Power.win uses letter grades A-F",
        status=ClaimStatus.VERIFIED,
        evidence=[Evidence(source=source_b, excerpt="Our grades range from A to F")],
    )

    conflict = ConflictingClaim(
        topic="Power.win casino scoring methodology",
        claim_a=claim_a,
        claim_b=claim_b,
        resolution="Need to check latest Power.win methodology page",
    )
    assert conflict.topic == "Power.win casino scoring methodology"
    assert conflict.claim_a.text != conflict.claim_b.text
    assert conflict.status == ClaimStatus.CONFLICTING


def test_research_plan_nested_structure() -> None:
    """Test that ResearchPlan can contain nested research questions."""
    plan = ResearchPlan(
        topic="How we Evaluate Online Casinos",
        questions=[
            ResearchQuestion(
                question="Does Power.win publish an editorial methodology?",
                priority="critical",
                is_power_win_check=True,
            ),
            ResearchQuestion(
                question="What licensing bodies are recognized?",
                priority="high",
                required_source_types=[SourceType.REGULATORY, SourceType.GOVERNMENT],
            ),
        ],
        required_power_win_checks=["editorial guidelines page", "review criteria"],
        required_external_checks=["UKGC license register", "MGA license register"],
        claims_to_verify=["10-point scoring system", "letter grade system"],
    )
    assert plan.topic == "How we Evaluate Online Casinos"
    assert len(plan.questions) == 2
    assert plan.questions[0].is_power_win_check is True
    assert SourceType.REGULATORY in plan.questions[1].required_source_types


def test_research_result_nested_structure() -> None:
    """Test that ResearchResult can contain all nested research information."""
    source = Source(name="Power.win", source_type=SourceType.FIRST_PARTY)
    evidence = Evidence(source=source, excerpt="We check licenses")

    result = ResearchResult(
        topic="How we Evaluate Online Casinos",
        questions=[
            ResearchQuestion(question="Does Power.win check licenses?", is_power_win_check=True),
        ],
        power_win_facts=[
            Claim(
                text="Power.win verifies casino licenses",
                status=ClaimStatus.VERIFIED,
                evidence=[evidence],
            )
        ],
        external_facts=[],
        unsupported_claims=[
            Claim(
                text="Power.win uses a 100-point scale",
                status=ClaimStatus.UNSUPPORTED,
            )
        ],
        conflicting_information=[],
        research_gaps=[
            ResearchGap(
                question="What is the exact scoring formula?",
                reason="Not published",
            )
        ],
        summary="Research found licensing verification but no scoring details.",
        status=ClaimStatus.PARTIALLY_SUPPORTED,
    )

    assert result.topic == "How we Evaluate Online Casinos"
    assert len(result.power_win_facts) == 1
    assert len(result.unsupported_claims) == 1
    assert len(result.research_gaps) == 1
    assert result.status == ClaimStatus.PARTIALLY_SUPPORTED


def test_research_result_helper_methods() -> None:
    """Test helper methods on ResearchResult."""
    source = Source(name="Test", source_type=SourceType.FIRST_PARTY)
    evidence = Evidence(source=source, excerpt="Test")

    result = ResearchResult(topic="Test Topic")

    # Add verified fact
    result.add_power_win_fact(Claim(text="Verified fact", status=ClaimStatus.VERIFIED, evidence=[evidence]))
    # Add partially supported fact
    result.add_power_win_fact(Claim(text="Partial fact", status=ClaimStatus.PARTIALLY_SUPPORTED, evidence=[evidence]))
    # Add unsupported claim
    result.add_power_win_fact(Claim(text="Unsupported", status=ClaimStatus.UNSUPPORTED, evidence=[evidence]))
    # Add editorial interpretation (should not be in safe claims)
    result.add_power_win_fact(Claim(text="Opinion", status=ClaimStatus.VERIFIED, nature=InformationNature.OPINION, evidence=[evidence]))

    verified = result.get_all_verified_facts()
    assert len(verified) == 1
    assert verified[0].text == "Verified fact"

    safe = result.get_safe_claims_for_writer()
    assert len(safe) == 2  # verified + partially supported, both FACT nature
    texts = {c.text for c in safe}
    assert "Verified fact" in texts
    assert "Partial fact" in texts
    assert "Unsupported" not in texts
    assert "Opinion" not in texts


def test_claim_confidence_bounds() -> None:
    """Test that claim confidence is bounded 0-1."""
    claim = Claim(text="Test", confidence=0.5)
    assert claim.confidence == 0.5

    with pytest.raises(ValidationError):
        Claim(text="Test", confidence=1.5)

    with pytest.raises(ValidationError):
        Claim(text="Test", confidence=-0.1)


def test_source_type_enum_values() -> None:
    """Test all source type enum values are accessible."""
    assert SourceType.FIRST_PARTY.value == "first_party"
    assert SourceType.REGULATORY.value == "regulatory"
    assert SourceType.GOVERNMENT.value == "government"
    assert SourceType.PRIMARY.value == "primary"
    assert SourceType.AUTHORITATIVE.value == "authoritative"
    assert SourceType.SECONDARY.value == "secondary"
    assert SourceType.GENERAL.value == "general"
    assert SourceType.UNKNOWN.value == "unknown"


def test_invalid_source_type_rejected() -> None:
    """Test that invalid source type is rejected."""
    with pytest.raises(ValidationError):
        Source(name="Test", source_type="invalid_type")