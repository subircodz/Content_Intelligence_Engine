"""
Content strategy models for SEO, AIO (AI Optimization), and GEO (Generative Engine Optimization).
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from power_win_content.competitors.models import ContentGap


class SEOStrategy(BaseModel):
    """SEO content strategy for search engine visibility."""

    model_config = ConfigDict(use_enum_values=True)

    primary_topic: str = Field(..., description="Main topic of the article")
    search_intent: str = Field(..., description="User search intent: informational, commercial, transactional, navigational")
    primary_keyword: str = Field(..., description="Primary keyword/topic to target")
    secondary_keywords: list[str] = Field(default_factory=list, description="Secondary keywords and related topics")
    recommended_title: str = Field(..., description="SEO-optimized article title")
    recommended_headings: list[str] = Field(default_factory=list, description="Recommended H2/H3 heading structure")
    questions_to_answer: list[str] = Field(default_factory=list, description="Key questions the article should answer")
    internal_linking_opportunities: list[str] = Field(default_factory=list, description="Internal pages to link to")
    semantic_coverage_requirements: list[str] = Field(
        default_factory=list, description="Semantic topics that must be covered for topical authority"
    )


class AIOStrategy(BaseModel):
    """AIO (AI Optimization) strategy for AI system comprehension and extraction."""

    model_config = ConfigDict(use_enum_values=True)

    direct_answer_questions: list[str] = Field(
        default_factory=list, description="Questions that should have direct, concise answers in the article"
    )
    concise_answers: dict[str, str] = Field(
        default_factory=dict, description="Recommended concise answers for direct-answer questions"
    )
    definitions: dict[str, str] = Field(
        default_factory=dict, description="Key terms that should be clearly defined in the article"
    )
    important_factual_statements: list[str] = Field(
        default_factory=list, description="Verified factual statements that should appear in the article"
    )
    entities: list[str] = Field(
        default_factory=list, description="Important entities (brands, organizations, products, people) to mention"
    )
    evidence_requirements: list[str] = Field(
        default_factory=list, description="Types of evidence/citations needed for AI trust signals"
    )
    structured_information_requirements: list[str] = Field(
        default_factory=list, description="Structured data requirements (lists, tables, step-by-step, comparisons)"
    )


class GEOStrategy(BaseModel):
    """GEO (Generative Engine Optimization) strategy for generative AI citation and synthesis."""

    model_config = ConfigDict(use_enum_values=True)

    important_entities: list[str] = Field(
        default_factory=list, description="Key entities that generative engines should associate with this content"
    )
    entity_relationships: list[str] = Field(
        default_factory=list, description="Relationships between entities (e.g., 'Power.win reviews casinos')"
    )
    authoritative_external_sources: list[str] = Field(
        default_factory=list, description="External authoritative sources to cite for credibility"
    )
    power_win_first_party_facts: list[str] = Field(
        default_factory=list, description="Power.win first-party facts that establish unique authority"
    )
    unique_information: list[str] = Field(
        default_factory=list, description="Information unique to Power.win not available elsewhere"
    )
    citation_evidence_opportunities: list[str] = Field(
        default_factory=list, description="Specific claims that should have inline citations/evidence"
    )
    factual_consistency_requirements: list[str] = Field(
        default_factory=list, description="Requirements to maintain factual consistency with known sources"
    )
    questions_to_answer_clearly: list[str] = Field(
        default_factory=list, description="Questions the article should answer clearly for generative engine synthesis"
    )


class ContentBrief(BaseModel):
    """Complete content brief combining SEO, AIO, and GEO strategies based on research."""

    model_config = ConfigDict(use_enum_values=True)

    topic: str = Field(..., description="Original article topic")
    seo: SEOStrategy = Field(..., description="SEO strategy section")
    aio: AIOStrategy = Field(..., description="AIO (AI Optimization) strategy section")
    geo: GEOStrategy = Field(..., description="GEO (Generative Engine Optimization) strategy section")

    # Metadata
    total_verified_facts: int = Field(default=0, description="Total verified facts available from research")
    total_power_win_facts: int = Field(default=0, description="Power.win first-party facts available")
    total_external_facts: int = Field(default=0, description="External verified facts available")
    research_gaps_count: int = Field(default=0, description="Number of research gaps identified")
    unsupported_claims_count: int = Field(default=0, description="Number of unsupported claims identified")
    conflicts_count: int = Field(default=0, description="Number of conflicting information items")

    competitor_gaps: ContentGap = Field(default_factory=ContentGap, description="Competitor content gap analysis")

    def get_all_recommended_facts(self) -> list[str]:
        """Get all facts recommended for inclusion in the article (verified only)."""
        return (
            self.aio.important_factual_statements
            + self.geo.power_win_first_party_facts
            + self.geo.unique_information
        )

    def get_all_required_entities(self) -> list[str]:
        """Get all entities that should appear in the article."""
        entities = set(self.aio.entities)
        entities.update(self.geo.important_entities)
        return list(entities)