"""Content strategy models for SEO, AIO, and GEO."""

from pydantic import BaseModel, ConfigDict, Field

from intelligence_content_engine.competitors.models import ContentGap, CoverageAssessment


class SEOStrategy(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    primary_topic: str = Field(...)
    search_intent: str = Field(...)
    primary_keyword: str = Field(...)
    secondary_keywords: list[str] = Field(default_factory=list)
    recommended_title: str = Field(...)
    recommended_headings: list[str] = Field(default_factory=list)
    questions_to_answer: list[str] = Field(default_factory=list)
    internal_linking_opportunities: list[str] = Field(default_factory=list)
    semantic_coverage_requirements: list[str] = Field(default_factory=list)


class AIOStrategy(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    direct_answer_questions: list[str] = Field(default_factory=list)
    concise_answers: dict[str, str] = Field(default_factory=dict)
    definitions: dict[str, str] = Field(default_factory=dict)
    important_factual_statements: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    structured_information_requirements: list[str] = Field(default_factory=list)


class GEOStrategy(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    important_entities: list[str] = Field(default_factory=list)
    entity_relationships: list[str] = Field(default_factory=list)
    authoritative_external_sources: list[str] = Field(default_factory=list)
    first_party_facts: list[str] = Field(default_factory=list)
    unique_information: list[str] = Field(default_factory=list)
    citation_evidence_opportunities: list[str] = Field(default_factory=list)
    factual_consistency_requirements: list[str] = Field(default_factory=list)
    questions_to_answer_clearly: list[str] = Field(default_factory=list)


class ContentBrief(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    topic: str = Field(...)
    seo: SEOStrategy = Field(...)
    aio: AIOStrategy = Field(...)
    geo: GEOStrategy = Field(...)
    total_verified_facts: int = Field(default=0)
    total_first_party_facts: int = Field(default=0)
    total_external_facts: int = Field(default=0)
    research_gaps_count: int = Field(default=0)
    unsupported_claims_count: int = Field(default=0)
    conflicts_count: int = Field(default=0)
    competitor_gaps: ContentGap = Field(default_factory=ContentGap)
    market_coverage: CoverageAssessment = Field(default_factory=CoverageAssessment)

    def get_all_recommended_facts(self) -> list[str]:
        return self.aio.important_factual_statements + self.geo.first_party_facts + self.geo.unique_information

    def get_all_required_entities(self) -> list[str]:
        entities = set(self.aio.entities)
        entities.update(self.geo.important_entities)
        return list(entities)
