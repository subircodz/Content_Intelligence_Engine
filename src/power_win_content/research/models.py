from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class SourceType(str, Enum):
    FIRST_PARTY = "first_party"
    REGULATORY = "regulatory"
    GOVERNMENT = "government"
    PRIMARY = "primary"
    AUTHORITATIVE = "authoritative"
    SECONDARY = "secondary"
    GENERAL = "general"
    UNKNOWN = "unknown"


class ClaimStatus(str, Enum):
    VERIFIED = "verified"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"
    UNCERTAIN = "uncertain"


class PhaseStatus(str, Enum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILED = "failed"


class InformationNature(str, Enum):
    FACT = "fact"
    EDITORIAL_INTERPRETATION = "editorial_interpretation"
    OPINION = "opinion"


class Source(BaseModel):
    name: str = Field(..., description="Human-readable source name")
    url: Optional[HttpUrl] = Field(None, description="Source URL if available")
    source_type: SourceType = Field(default=SourceType.UNKNOWN, description="Authority classification")
    provider: str = Field(default="unknown", description="Search engine that discovered this source")
    title: Optional[str] = Field(None, description="Article/page title")
    publication_date: Optional[datetime] = Field(None, description="Original publication date")
    updated_date: Optional[datetime] = Field(None, description="Last known update date")
    checked_date: datetime = Field(default_factory=datetime.now, description="When this source was last verified")
    notes: Optional[str] = Field(None, description="Additional context about the source")

    model_config = {"use_enum_values": True}


class Evidence(BaseModel):
    source: Source = Field(..., description="The source this evidence comes from")
    excerpt: str = Field(..., description="Relevant text excerpt from the source")
    notes: Optional[str] = Field(None, description="Additional context about this evidence")
    retrieval_method: str = Field(default="http", description="How content was retrieved")

    model_config = {"use_enum_values": True}


class Claim(BaseModel):
    text: str = Field(..., description="The claim statement")
    status: ClaimStatus = Field(default=ClaimStatus.UNCERTAIN, description="Verification status")
    nature: InformationNature = Field(default=InformationNature.FACT, description="Type of information")
    evidence: list[Evidence] = Field(default_factory=list, description="Evidence supporting this claim")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in claim validity")
    notes: Optional[str] = Field(None, description="Additional context or caveats")

    model_config = {"use_enum_values": True}


class ResearchGap(BaseModel):
    question: str = Field(..., description="The unanswered research question")
    reason: str = Field(..., description="Why this gap exists")
    attempted_sources: list[str] = Field(default_factory=list, description="Sources checked but insufficient")
    importance: str = Field(default="medium", description="Impact of this gap")

    model_config = {"use_enum_values": True}


class ConflictingClaim(BaseModel):
    topic: str = Field(..., description="What the conflict is about")
    claim_a: Claim = Field(..., description="First conflicting claim")
    claim_b: Claim = Field(..., description="Second conflicting claim")
    resolution: Optional[str] = Field(None, description="Recommended resolution")
    status: ClaimStatus = Field(default=ClaimStatus.CONFLICTING, description="Overall conflict status")

    model_config = {"use_enum_values": True}


class ResearchQuestion(BaseModel):
    question: str = Field(..., description="The research question")
    priority: str = Field(default="medium", description="Priority level")
    required_source_types: list[SourceType] = Field(default_factory=list, description="Preferred source types")
    is_first_party_check: bool = Field(default=False, description="Whether this requires target-site first-party sources")
    notes: Optional[str] = Field(None, description="Additional research context")

    model_config = {"use_enum_values": True}


class ResearchPlan(BaseModel):
    topic: str = Field(..., description="The article topic/title")
    questions: list[ResearchQuestion] = Field(default_factory=list, description="Research questions")
    required_first_party_checks: list[str] = Field(default_factory=list, description="Specific target-site checks")
    required_external_checks: list[str] = Field(default_factory=list, description="External sources to consult")
    claims_to_verify: list[str] = Field(default_factory=list, description="Claims requiring verification")
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = {"use_enum_values": True}


class ResearchResult(BaseModel):
    topic: str = Field(..., description="The article topic/title")
    plan: Optional[ResearchPlan] = Field(None, description="Research plan used")
    questions: list[ResearchQuestion] = Field(default_factory=list, description="Questions investigated")
    first_party_facts: list[Claim] = Field(default_factory=list, description="Verified facts from target-site sources")
    external_facts: list[Claim] = Field(default_factory=list, description="Verified facts from external sources")
    unsupported_claims: list[Claim] = Field(default_factory=list, description="Claims lacking sufficient evidence")
    conflicting_information: list[ConflictingClaim] = Field(default_factory=list, description="Conflicting source information")
    research_gaps: list[ResearchGap] = Field(default_factory=list, description="Questions that could not be answered")
    summary: Optional[str] = Field(None, description="Narrative summary of findings")
    status: ClaimStatus = Field(default=ClaimStatus.UNCERTAIN, description="Overall research completeness")
    researched_at: datetime = Field(default_factory=datetime.now)

    model_config = {"use_enum_values": True}

    def add_first_party_fact(self, claim: Claim) -> None:
        self.first_party_facts.append(claim)

    def add_external_fact(self, claim: Claim) -> None:
        self.external_facts.append(claim)

    def add_research_gap(self, gap: ResearchGap) -> None:
        self.research_gaps.append(gap)

    def add_conflict(self, conflict: ConflictingClaim) -> None:
        self.conflicting_information.append(conflict)

    def get_all_verified_facts(self) -> list[Claim]:
        return [
            claim
            for claim in self.first_party_facts + self.external_facts
            if claim.status == ClaimStatus.VERIFIED and claim.nature == InformationNature.FACT
        ]

    def get_safe_claims_for_writer(self) -> list[Claim]:
        safe_statuses = {ClaimStatus.VERIFIED, ClaimStatus.PARTIALLY_SUPPORTED}
        return [
            claim
            for claim in self.first_party_facts + self.external_facts
            if claim.status in safe_statuses and claim.nature == InformationNature.FACT
        ]
