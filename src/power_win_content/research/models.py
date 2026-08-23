from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class SourceType(str, Enum):
    """Classification of source authority and origin."""

    FIRST_PARTY = "first_party"
    REGULATORY = "regulatory"
    GOVERNMENT = "government"
    PRIMARY = "primary"
    AUTHORITATIVE = "authoritative"
    SECONDARY = "secondary"
    GENERAL = "general"
    UNKNOWN = "unknown"


class ClaimStatus(str, Enum):
    """Verification status of a claim."""

    VERIFIED = "verified"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"
    UNCERTAIN = "uncertain"


class PhaseStatus(str, Enum):
    """Pipeline execution status for a phase."""

    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILED = "failed"


class InformationNature(str, Enum):
    """Distinguishes factual content from interpretation/opinion."""

    FACT = "fact"
    EDITORIAL_INTERPRETATION = "editorial_interpretation"
    OPINION = "opinion"


class Source(BaseModel):
    """A research source with metadata for credibility assessment."""

    name: str = Field(..., description="Human-readable source name")
    url: Optional[HttpUrl] = Field(None, description="Source URL if available")
    source_type: SourceType = Field(
        default=SourceType.UNKNOWN, description="Authority classification"
    )
    provider: str = Field(
        default="unknown", description="Search engine that discovered this source"
    )
    title: Optional[str] = Field(None, description="Article/page title")
    publication_date: Optional[datetime] = Field(None, description="Original publication date")
    updated_date: Optional[datetime] = Field(None, description="Last known update date")
    checked_date: datetime = Field(
        default_factory=datetime.now, description="When this source was last verified"
    )
    notes: Optional[str] = Field(None, description="Additional context about the source")

    model_config = {
        "use_enum_values": True,
    }


class Evidence(BaseModel):
    """A piece of evidence extracted from a source supporting a claim."""

    source: Source = Field(..., description="The source this evidence comes from")
    excerpt: str = Field(..., description="Relevant text excerpt from the source")
    notes: Optional[str] = Field(None, description="Additional context about this evidence")
    retrieval_method: str = Field(
        default="http", description="How the content was retrieved: http, browser, sitemap, api"
    )

    model_config = {
        "use_enum_values": True,
    }


class Claim(BaseModel):
    """A verifiable claim with supporting evidence and status."""

    text: str = Field(..., description="The claim statement")
    status: ClaimStatus = Field(
        default=ClaimStatus.UNCERTAIN, description="Verification status"
    )
    nature: InformationNature = Field(
        default=InformationNature.FACT, description="Type of information"
    )
    evidence: list[Evidence] = Field(
        default_factory=list, description="Evidence supporting this claim"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence in claim validity (0-1)"
    )
    notes: Optional[str] = Field(None, description="Additional context or caveats")

    model_config = {
        "use_enum_values": True,
    }


class ResearchGap(BaseModel):
    """A research question that could not be answered with available evidence."""

    question: str = Field(..., description="The unanswered research question")
    reason: str = Field(..., description="Why this gap exists (e.g., 'no reliable source found')")
    attempted_sources: list[str] = Field(
        default_factory=list, description="Sources checked but found insufficient"
    )
    importance: str = Field(
        default="medium", description="Impact of this gap on the article (low/medium/high)"
    )

    model_config = {
        "use_enum_values": True,
    }


class ConflictingClaim(BaseModel):
    """Conflicting information from multiple sources about the same topic."""

    topic: str = Field(..., description="What the conflict is about")
    claim_a: Claim = Field(..., description="First conflicting claim")
    claim_b: Claim = Field(..., description="Second conflicting claim")
    resolution: Optional[str] = Field(
        None, description="Recommended resolution or status of conflict"
    )
    status: ClaimStatus = Field(
        default=ClaimStatus.CONFLICTING, description="Overall status of the conflict"
    )

    model_config = {
        "use_enum_values": True,
    }


class ResearchQuestion(BaseModel):
    """A single research question to investigate."""

    question: str = Field(..., description="The research question")
    priority: str = Field(
        default="medium", description="Priority level (low/medium/high/critical)"
    )
    required_source_types: list[SourceType] = Field(
        default_factory=list, description="Source types that would best answer this"
    )
    is_power_win_check: bool = Field(
        default=False, description="Whether this specifically requires Power.win sources"
    )
    notes: Optional[str] = Field(None, description="Additional context for the researcher")

    model_config = {
        "use_enum_values": True,
    }


class ResearchPlan(BaseModel):
    """A structured plan for researching a topic."""

    topic: str = Field(..., description="The article topic/title")
    questions: list[ResearchQuestion] = Field(
        default_factory=list, description="Research questions to investigate"
    )
    required_power_win_checks: list[str] = Field(
        default_factory=list, description="Specific Power.win content to verify"
    )
    required_external_checks: list[str] = Field(
        default_factory=list, description="External sources to consult"
    )
    claims_to_verify: list[str] = Field(
        default_factory=list, description="Specific claims that need verification"
    )
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = {
        "use_enum_values": True,
    }


class ResearchResult(BaseModel):
    """Complete research package for the Content Writer."""

    topic: str = Field(..., description="The article topic/title")
    plan: Optional[ResearchPlan] = Field(None, description="The research plan used")
    questions: list[ResearchQuestion] = Field(
        default_factory=list, description="All research questions investigated"
    )
    power_win_facts: list[Claim] = Field(
        default_factory=list, description="Verified facts about Power.win specifically"
    )
    external_facts: list[Claim] = Field(
        default_factory=list, description="Verified facts from external sources"
    )
    unsupported_claims: list[Claim] = Field(
        default_factory=list, description="Claims that lack sufficient evidence"
    )
    conflicting_information: list[ConflictingClaim] = Field(
        default_factory=list, description="Conflicts found during research"
    )
    research_gaps: list[ResearchGap] = Field(
        default_factory=list, description="Questions that could not be answered"
    )
    summary: Optional[str] = Field(None, description="Narrative summary of research findings")
    status: ClaimStatus = Field(
        default=ClaimStatus.UNCERTAIN, description="Overall research completeness"
    )
    researched_at: datetime = Field(default_factory=datetime.now)

    model_config = {
        "use_enum_values": True,
    }

    def add_power_win_fact(self, claim: Claim) -> None:
        """Add a verified Power.win fact."""
        self.power_win_facts.append(claim)

    def add_external_fact(self, claim: Claim) -> None:
        """Add a verified external fact."""
        self.external_facts.append(claim)

    def add_research_gap(self, gap: ResearchGap) -> None:
        """Record an unanswered research question."""
        self.research_gaps.append(gap)

    def add_conflict(self, conflict: ConflictingClaim) -> None:
        """Record conflicting information."""
        self.conflicting_information.append(conflict)

    def get_all_verified_facts(self) -> list[Claim]:
        """Get all verified facts regardless of source (excludes opinions/interpretations)."""
        return [
            c for c in self.power_win_facts + self.external_facts
            if c.status == ClaimStatus.VERIFIED and c.nature == InformationNature.FACT
        ]

    def get_safe_claims_for_writer(self) -> list[Claim]:
        """Get claims safe for the Content Writer to use (verified + partially supported facts)."""
        safe_statuses = {ClaimStatus.VERIFIED, ClaimStatus.PARTIALLY_SUPPORTED}
        all_facts = self.power_win_facts + self.external_facts
        return [
            c for c in all_facts
            if c.status in safe_statuses and c.nature == InformationNature.FACT
        ]