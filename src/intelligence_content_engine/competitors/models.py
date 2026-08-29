from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TopicCoverageStatus(str, Enum):
    """Market-level coverage state for the requested topic."""

    FOUND = "FOUND"
    PARTIALLY_FOUND = "PARTIALLY_FOUND"
    NOT_FOUND = "NOT_FOUND"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    SEARCH_FAILED = "SEARCH_FAILED"


class OpportunityType(str, Enum):
    """The content opportunity identified by market research."""

    COMPETITIVE_GAP = "COMPETITIVE_GAP"
    MARKET_WHITESPACE = "MARKET_WHITESPACE"


class CoverageConfidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CompetitorSource(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    domain: str = Field(..., description="Competitor domain discovered from search results")
    url: str = Field(..., description="Specific competitor page URL analyzed")
    title: Optional[str] = Field(None, description="Page title when available")
    search_intent: Optional[str] = Field(None, description="Detected search intent of the competitor page")
    coverage_scope: str = Field(default="UNKNOWN", description="FULL, PARTIAL, or NOT_RELEVANT coverage of the requested topic")
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    headings: list[str] = Field(default_factory=list)
    questions_answered: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    statistics: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    unique_angles: list[str] = Field(default_factory=list)
    approximate_word_count: int = Field(default=0)
    fetched_successfully: bool = Field(default=False)
    fetch_failure_reason: Optional[str] = Field(None)


class CoverageElement(BaseModel):
    """A semantically clustered element observed across competitor pages."""

    model_config = ConfigDict(use_enum_values=True)

    element: str
    element_type: str = "unknown"
    variants: list[str] = Field(default_factory=list)
    covered_by_domains: list[str] = Field(default_factory=list)
    coverage_count: int = 0
    coverage_percentage: float = 0.0


class ContentGap(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    missing_topics: list[str] = Field(default_factory=list)
    missing_questions: list[str] = Field(default_factory=list)
    missing_entities: list[str] = Field(default_factory=list)
    missing_comparisons: list[str] = Field(default_factory=list)
    missing_statistics: list[str] = Field(default_factory=list)
    missing_user_concerns: list[str] = Field(default_factory=list)
    missing_angles: list[str] = Field(default_factory=list)
    competitor_topics_absent_from_target: list[str] = Field(default_factory=list)


class CoverageAssessment(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    status: TopicCoverageStatus = TopicCoverageStatus.INSUFFICIENT_DATA
    confidence: CoverageConfidence = CoverageConfidence.LOW
    opportunity_type: Optional[OpportunityType] = None
    rationale: str = ""
    relevant_pages_found: int = 0
    relevant_domains_found: int = 0
    search_queries_attempted: int = 0
    search_queries_succeeded: int = 0
    candidate_pages_discovered: int = 0
    successfully_analyzed: int = 0
    failed_analysis: int = 0
    minimum_analysis_required: int = 0
    minimum_domains_required: int = 0


class CompetitorAnalysis(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    topic: str
    analyzed_sources: list[CompetitorSource] = Field(default_factory=list)
    coverage: CoverageAssessment = Field(default_factory=CoverageAssessment)
    coverage_elements: list[CoverageElement] = Field(default_factory=list)
    gaps: ContentGap = Field(default_factory=ContentGap)
    domains_analyzed: int = Field(default=0)
    successfully_fetched: int = Field(default=0)
    failures: int = Field(default=0)
