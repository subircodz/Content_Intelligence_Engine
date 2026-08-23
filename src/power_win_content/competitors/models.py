from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class CompetitorSource(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    domain: str = Field(..., description="Competitor domain discovered from search results")
    url: str = Field(..., description="Specific competitor page URL analyzed")
    title: Optional[str] = Field(None, description="Page title when available")
    search_intent: Optional[str] = Field(None, description="Detected search intent of the competitor page")
    headings: list[str] = Field(default_factory=list)
    questions_answered: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    statistics: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    unique_angles: list[str] = Field(default_factory=list)
    approximate_word_count: int = Field(default=0)
    fetched_successfully: bool = Field(default=False)
    fetch_failure_reason: Optional[str] = Field(None)


class ContentGap(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    missing_topics: list[str] = Field(default_factory=list)
    missing_questions: list[str] = Field(default_factory=list)
    missing_entities: list[str] = Field(default_factory=list)
    missing_comparisons: list[str] = Field(default_factory=list)
    missing_statistics: list[str] = Field(default_factory=list)
    missing_user_concerns: list[str] = Field(default_factory=list)
    missing_angles: list[str] = Field(default_factory=list)
    competitor_topics_absent_from_ours: list[str] = Field(default_factory=list)


class CompetitorAnalysis(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    topic: str
    analyzed_sources: list[CompetitorSource] = Field(default_factory=list)
    gaps: ContentGap = Field(default_factory=ContentGap)
    domains_analyzed: int = Field(default=0)
    successfully_fetched: int = Field(default=0)
    failures: int = Field(default=0)
