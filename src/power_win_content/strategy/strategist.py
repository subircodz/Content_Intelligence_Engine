"""Generate SEO, AIO, and GEO content briefs from research results."""

import json
import logging
from typing import Optional

from power_win_content.competitors.models import CompetitorAnalysis, ContentGap
from power_win_content.llm.client import LLMClient
from power_win_content.research.models import Claim, ClaimStatus, InformationNature, PhaseStatus, ResearchResult
from power_win_content.strategy.models import AIOStrategy, ContentBrief, GEOStrategy, SEOStrategy

logger = logging.getLogger(__name__)


class ContentStrategist:
    """Domain-independent content strategy generator."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def create_brief(
        self,
        topic: str,
        research: ResearchResult,
        competitor_analysis: Optional[CompetitorAnalysis] = None,
    ) -> tuple[ContentBrief, PhaseStatus]:
        first_party_facts = research.first_party_facts
        external_facts = research.external_facts
        unsupported_claims = research.unsupported_claims

        first_party_verified = [c for c in first_party_facts if c.status == ClaimStatus.VERIFIED]
        first_party_partial = [c for c in first_party_facts if c.status == ClaimStatus.PARTIALLY_SUPPORTED]
        external_verified = [c for c in external_facts if c.status == ClaimStatus.VERIFIED]
        external_partial = [c for c in external_facts if c.status == ClaimStatus.PARTIALLY_SUPPORTED]

        context = self._build_context(
            topic,
            first_party_verified,
            first_party_partial,
            external_verified,
            external_partial,
            unsupported_claims,
            research.research_gaps,
            research.conflicting_information,
            competitor_analysis,
        )

        seo, seo_ok = self._generate_seo_strategy(topic, context)
        aio, aio_ok = self._generate_aio_strategy(topic, context)
        geo, geo_ok = self._generate_geo_strategy(topic, context)

        brief = ContentBrief(
            topic=topic,
            seo=seo,
            aio=aio,
            geo=geo,
            total_verified_facts=len(first_party_verified) + len(external_verified),
            total_first_party_facts=len(first_party_verified) + len(first_party_partial),
            total_external_facts=len(external_verified) + len(external_partial),
            research_gaps_count=len(research.research_gaps),
            unsupported_claims_count=len(unsupported_claims),
            conflicts_count=len(research.conflicting_information),
            competitor_gaps=competitor_analysis.gaps if competitor_analysis else ContentGap(),
        )

        parsed_count = sum((seo_ok, aio_ok, geo_ok))
        return brief, PhaseStatus.SUCCESS if parsed_count == 3 else PhaseStatus.DEGRADED

    def _build_context(
        self,
        topic: str,
        first_party_verified: list[Claim],
        first_party_partial: list[Claim],
        external_verified: list[Claim],
        external_partial: list[Claim],
        unsupported: list[Claim],
        research_gaps: list,
        conflicts: list,
        competitor_analysis: Optional[CompetitorAnalysis] = None,
    ) -> str:
        def format_claims(claims: list[Claim], label: str) -> str:
            if not claims:
                return f"{label}: None"
            lines = [f"{label} ({len(claims)}):"]
            for claim in claims:
                excerpt = claim.evidence[0].excerpt[:150] if claim.evidence else "No excerpt"
                source = claim.evidence[0].source.name if claim.evidence else "Unknown source"
                lines.append(f"  - {claim.text} (confidence: {claim.confidence:.2f})")
                lines.append(f"    Source: {source} - {excerpt}")
            return "\n".join(lines)

        sections = [
            f"Topic: {topic}",
            "",
            format_claims(first_party_verified, "Target-site VERIFIED facts"),
            format_claims(first_party_partial, "Target-site PARTIALLY SUPPORTED facts"),
            format_claims(external_verified, "External VERIFIED facts"),
            format_claims(external_partial, "External PARTIALLY SUPPORTED facts"),
            "",
            f"Unsupported claims ({len(unsupported)}): " + (", ".join(c.text[:80] for c in unsupported[:5]) if unsupported else "None"),
            "",
            "Research gaps: " + ("; ".join(f"{g.question}: {g.reason}" for g in research_gaps[:5]) if research_gaps else "None"),
            "",
            "Conflicting information: " + ("; ".join(c.topic for c in conflicts[:3]) if conflicts else "None"),
        ]

        competitor_section = self._format_competitor_context(competitor_analysis)
        if competitor_section:
            sections.extend(["", competitor_section])
        return "\n".join(sections)

    def _format_competitor_context(self, analysis: Optional[CompetitorAnalysis]) -> str:
        if not analysis:
            return ""
        gaps = analysis.gaps
        parts = [
            "Competitor content opportunity analysis (editorial planning only, NOT factual evidence):",
            f"Competitors analyzed: {analysis.domains_analyzed}",
        ]
        for label, values in (
            ("Missing topics", gaps.missing_topics),
            ("Missing questions", gaps.missing_questions),
            ("Missing entities", gaps.missing_entities),
            ("Missing comparisons", gaps.missing_comparisons),
            ("Missing statistics/data", gaps.missing_statistics),
            ("Missing user concerns", gaps.missing_user_concerns),
            ("Recommended angles", gaps.missing_angles),
        ):
            if values:
                parts.append(f"{label}: {', '.join(values[:10])}")
        return "\n".join(parts)

    def _generate_seo_strategy(self, topic: str, context: str) -> tuple[SEOStrategy, bool]:
        return self._parse_seo_response(self.llm_client.generate(self._build_seo_prompt(topic, context)), topic)

    def _build_seo_prompt(self, topic: str, context: str) -> str:
        return (
            "You are an SEO content strategist. Create an SEO strategy for the topic below.\n\n"
            f"Topic: {topic}\n\nResearch Context:\n{context}\n\n"
            "Return ONLY valid JSON containing primary_topic, search_intent, primary_keyword, secondary_keywords, "
            "recommended_title, recommended_headings, questions_to_answer, internal_linking_opportunities, "
            "and semantic_coverage_requirements. Use only the supplied research context for factual details."
        )

    def _parse_seo_response(self, response: str, topic: str) -> tuple[SEOStrategy, bool]:
        data, parsed = self._parse_json(response)
        return SEOStrategy(
            primary_topic=data.get("primary_topic", topic),
            search_intent=data.get("search_intent", "informational"),
            primary_keyword=data.get("primary_keyword", topic),
            secondary_keywords=data.get("secondary_keywords", []),
            recommended_title=data.get("recommended_title", topic),
            recommended_headings=data.get("recommended_headings", []),
            questions_to_answer=data.get("questions_to_answer", []),
            internal_linking_opportunities=data.get("internal_linking_opportunities", []),
            semantic_coverage_requirements=data.get("semantic_coverage_requirements", []),
        ), parsed

    def _generate_aio_strategy(self, topic: str, context: str) -> tuple[AIOStrategy, bool]:
        return self._parse_aio_response(self.llm_client.generate(self._build_aio_prompt(topic, context)))

    def _build_aio_prompt(self, topic: str, context: str) -> str:
        return (
            "You are an AI Optimization (AIO) strategist. Create an AIO strategy.\n\n"
            f"Topic: {topic}\n\nResearch Context:\n{context}\n\n"
            "Return ONLY valid JSON containing direct_answer_questions, concise_answers, definitions, "
            "important_factual_statements, entities, evidence_requirements, and structured_information_requirements."
        )

    def _parse_aio_response(self, response: str) -> tuple[AIOStrategy, bool]:
        data, parsed = self._parse_json(response)
        return AIOStrategy(
            direct_answer_questions=data.get("direct_answer_questions", []),
            concise_answers=data.get("concise_answers", {}),
            definitions=data.get("definitions", {}),
            important_factual_statements=data.get("important_factual_statements", []),
            entities=data.get("entities", []),
            evidence_requirements=data.get("evidence_requirements", []),
            structured_information_requirements=data.get("structured_information_requirements", []),
        ), parsed

    def _generate_geo_strategy(self, topic: str, context: str) -> tuple[GEOStrategy, bool]:
        return self._parse_geo_response(self.llm_client.generate(self._build_geo_prompt(topic, context)))

    def _build_geo_prompt(self, topic: str, context: str) -> str:
        return (
            "You are a Generative Engine Optimization (GEO) strategist. Create a GEO strategy.\n\n"
            f"Topic: {topic}\n\nResearch Context:\n{context}\n\n"
            "Return ONLY valid JSON containing important_entities, entity_relationships, authoritative_external_sources, "
            "first_party_facts, unique_information, citation_evidence_opportunities, factual_consistency_requirements, "
            "and questions_to_answer_clearly. Do not invent facts."
        )

    def _parse_geo_response(self, response: str) -> tuple[GEOStrategy, bool]:
        data, parsed = self._parse_json(response)
        return GEOStrategy(
            important_entities=data.get("important_entities", []),
            entity_relationships=data.get("entity_relationships", []),
            authoritative_external_sources=data.get("authoritative_external_sources", []),
            first_party_facts=data.get("first_party_facts", []),
            unique_information=data.get("unique_information", []),
            citation_evidence_opportunities=data.get("citation_evidence_opportunities", []),
            factual_consistency_requirements=data.get("factual_consistency_requirements", []),
            questions_to_answer_clearly=data.get("questions_to_answer_clearly", []),
        ), parsed

    @staticmethod
    def _parse_json(response: str) -> tuple[dict, bool]:
        if not response or not response.strip():
            return {}, False
        try:
            data = json.loads(response.strip())
            return (data if isinstance(data, dict) else {}), isinstance(data, dict)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM strategy response")
            return {}, False
