from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from intelligence_content_engine.competitors.models import CompetitorAnalysis, TopicCoverageStatus
from intelligence_content_engine.research.models import ClaimStatus, ResearchResult


class ResearchQualityStatus(str, Enum):
    PASS = "PASS"
    DEGRADED = "DEGRADED"
    FAIL = "FAIL"


class ResearchQualityReport(BaseModel):
    status: ResearchQualityStatus
    rationale: str
    safe_claims: int = 0
    unsupported_claims: int = 0
    conflicting_claims: int = 0
    research_gaps: int = 0
    competitor_coverage_status: str | None = None
    competitor_confidence: str | None = None
    warnings: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)


class ResearchQualityGate:
    """Evaluate whether research is safe enough to enter strategy generation.

    A degraded competitor result does not block article generation. In particular,
    NOT_FOUND is a valid Case 2 outcome and must continue to SEO/AIO/GEO strategy.
    A failed research phase or failed competitor search blocks the pipeline because
    those states do not provide enough information to make a reliable conclusion.
    """

    def __init__(self, minimum_safe_claims: int = 1, max_unsupported_ratio: float = 0.75) -> None:
        self.minimum_safe_claims = minimum_safe_claims
        self.max_unsupported_ratio = max_unsupported_ratio

    def evaluate(
        self,
        research_result: ResearchResult,
        competitor_analysis: CompetitorAnalysis | None,
    ) -> ResearchQualityReport:
        safe_claims = len(research_result.get_safe_claims_for_writer())
        unsupported = len(research_result.unsupported_claims)
        conflicts = len(research_result.conflicting_information)
        gaps = len(research_result.research_gaps)
        warnings: list[str] = []
        blocking: list[str] = []

        if safe_claims < self.minimum_safe_claims:
            blocking.append(
                f"Research produced only {safe_claims} safe claims; "
                f"at least {self.minimum_safe_claims} are required."
            )

        total_claims = safe_claims + unsupported
        if total_claims and unsupported / total_claims > self.max_unsupported_ratio:
            blocking.append("Too high a proportion of researched claims are unsupported.")

        if conflicts:
            warnings.append(f"{conflicts} conflicting claim set(s) require editorial caution.")
        if gaps:
            warnings.append(f"{gaps} research question(s) remain unresolved.")

        coverage_status = None
        coverage_confidence = None
        if competitor_analysis is None:
            blocking.append("Competitor analysis was not produced.")
        else:
            coverage_status = str(competitor_analysis.coverage.status)
            coverage_confidence = str(competitor_analysis.coverage.confidence)

            if competitor_analysis.coverage.status == TopicCoverageStatus.SEARCH_FAILED:
                blocking.append("Competitor search failed; market coverage cannot be determined.")
            elif competitor_analysis.coverage.status == TopicCoverageStatus.INSUFFICIENT_DATA:
                warnings.append(
                    "Competitor evidence is insufficient for a market-coverage conclusion; "
                    "do not label the topic as market whitespace."
                )
            elif competitor_analysis.coverage.status == TopicCoverageStatus.NOT_FOUND:
                warnings.append(
                    "Topic is classified as market whitespace; continue with independent research "
                    "and generate the SEO/AIO/GEO article normally."
                )

        if blocking:
            status = ResearchQualityStatus.FAIL
            rationale = "Research quality gate failed: " + " ".join(blocking)
        elif warnings:
            status = ResearchQualityStatus.DEGRADED
            rationale = "Research is usable with warnings."
        else:
            status = ResearchQualityStatus.PASS
            rationale = "Research meets the minimum quality requirements for strategy generation."

        return ResearchQualityReport(
            status=status,
            rationale=rationale,
            safe_claims=safe_claims,
            unsupported_claims=unsupported,
            conflicting_claims=conflicts,
            research_gaps=gaps,
            competitor_coverage_status=coverage_status,
            competitor_confidence=coverage_confidence,
            warnings=warnings,
            blocking_reasons=blocking,
        )
