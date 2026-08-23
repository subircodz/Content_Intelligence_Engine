"""
Content Strategist - generates SEO, AIO, and GEO content briefs from research results.
"""

import json
import logging
from typing import Optional

from power_win_content.llm.client import LLMClient
from power_win_content.research.models import Claim, ClaimStatus, InformationNature, PhaseStatus, ResearchResult
from power_win_content.strategy.models import AIOStrategy, ContentBrief, GEOStrategy, SEOStrategy
from power_win_content.competitors.models import CompetitorAnalysis, ContentGap

logger = logging.getLogger(__name__)


class ContentStrategist:
    """
    Generates content strategy briefs from research results.

    Uses LLM to organize strategy but preserves factual distinction:
    - Verified facts (from ResearchResult.get_safe_claims_for_writer())
    - Partially supported facts
    - Unsupported claims (never become recommended facts)
    - Editorial interpretations
    - Opinions

    Power.win first-party facts remain distinguishable from external facts.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def create_brief(
        self,
        topic: str,
        research: ResearchResult,
        competitor_analysis: Optional[CompetitorAnalysis] = None,
    ) -> tuple[ContentBrief, PhaseStatus]:
        """Create a complete content brief from research results."""
        # Get safe claims for the writer (verified facts only)
        safe_claims = research.get_safe_claims_for_writer()
        power_win_facts = research.power_win_facts
        external_facts = research.external_facts
        unsupported_claims = research.unsupported_claims

        # Separate Power.win and external verified facts
        pw_verified = [c for c in power_win_facts if c.status == ClaimStatus.VERIFIED]
        pw_partially = [c for c in power_win_facts if c.status == ClaimStatus.PARTIALLY_SUPPORTED]
        ext_verified = [c for c in external_facts if c.status == ClaimStatus.VERIFIED]
        ext_partially = [c for c in external_facts if c.status == ClaimStatus.PARTIALLY_SUPPORTED]

        # Build context for LLM
        context = self._build_context(
            topic=topic,
            pw_verified=pw_verified,
            pw_partially=pw_partially,
            ext_verified=ext_verified,
            ext_partially=ext_partially,
            unsupported=unsupported_claims,
            research_gaps=research.research_gaps,
            conflicts=research.conflicting_information,
            competitor_analysis=competitor_analysis,
        )

        # Generate three strategy sections
        seo, seo_parsed = self._generate_seo_strategy(topic, context)
        aio, aio_parsed = self._generate_aio_strategy(topic, context)
        geo, geo_parsed = self._generate_geo_strategy(topic, context)

        parsed_count = sum([seo_parsed, aio_parsed, geo_parsed])

        # Build final brief
        competitor_gaps = competitor_analysis.gaps if competitor_analysis else ContentGap()

        brief = ContentBrief(
            topic=topic,
            seo=seo,
            aio=aio,
            geo=geo,
            total_verified_facts=len(pw_verified) + len(ext_verified),
            total_power_win_facts=len(pw_verified) + len(pw_partially),
            total_external_facts=len(ext_verified) + len(ext_partially),
            research_gaps_count=len(research.research_gaps),
            unsupported_claims_count=len(unsupported_claims),
            conflicts_count=len(research.conflicting_information),
            competitor_gaps=competitor_gaps,
        )

        if parsed_count >= 2:
            phase_status = PhaseStatus.SUCCESS
        elif parsed_count >= 1:
            phase_status = PhaseStatus.DEGRADED
        else:
            phase_status = PhaseStatus.DEGRADED

        return brief, phase_status

    def _build_context(
        self,
        topic: str,
        pw_verified: list[Claim],
        pw_partially: list[Claim],
        ext_verified: list[Claim],
        ext_partially: list[Claim],
        unsupported: list[Claim],
        research_gaps: list,
        conflicts: list,
        competitor_analysis: Optional[CompetitorAnalysis] = None,
    ) -> str:
        """Build structured context for LLM strategy generation."""

        def format_claims(claims: list[Claim], label: str) -> str:
            if not claims:
                return f"{label}: None"
            lines = [f"{label} ({len(claims)}):"]
            for c in claims:
                excerpt = c.evidence[0].excerpt[:150] if c.evidence else "No excerpt"
                source_name = c.evidence[0].source.name if c.evidence else "Unknown source"
                lines.append(f"  - {c.text} (confidence: {c.confidence:.2f})")
                lines.append(f"    Source: {source_name} - {excerpt}")
            return "\n".join(lines)

        def format_gaps(gaps) -> str:
            if not gaps:
                return "Research gaps: None"
            lines = ["Research gaps:"]
            for g in gaps[:5]:
                lines.append(f"  - {g.question}: {g.reason}")
            return "\n".join(lines)

        def format_conflicts(conflicts) -> str:
            if not conflicts:
                return "Conflicts: None"
            lines = ["Conflicting information:"]
            for c in conflicts[:3]:
                lines.append(f"  - {c.topic}: {c.claim_a.text[:80]}... vs {c.claim_b.text[:80]}...")
            return "\n".join(lines)

        sections = [
            f"Topic: {topic}",
            "",
            format_claims(pw_verified, "Power.win VERIFIED facts"),
            format_claims(pw_partially, "Power.win PARTIALLY SUPPORTED facts"),
            format_claims(ext_verified, "External VERIFIED facts"),
            format_claims(ext_partially, "External PARTIALLY SUPPORTED facts"),
            "",
            f"Unsupported claims ({len(unsupported)}): " + (
                ", ".join([c.text[:80] for c in unsupported[:5]]) if unsupported else "None"
            ),
            "",
            format_gaps(research_gaps),
            "",
            format_conflicts(conflicts),
        ]

        if hasattr(self, "_format_competitor_context"):
            competitor_section = self._format_competitor_context(competitor_analysis)
            if competitor_section:
                sections.extend(["", competitor_section])

        return "\n".join(sections)

    def _format_competitor_context(self, analysis: Optional[CompetitorAnalysis]) -> str:
        if not analysis:
            return ""

        gaps = analysis.gaps
        parts = [
            "Competitor Content Gap Analysis (editorial planning only, NOT factual evidence):",
            f"Competitors analyzed: {analysis.domains_analyzed}",
        ]
        if gaps.missing_topics:
            parts.append("Missing topics: " + ", ".join(gaps.missing_topics[:10]))
        if gaps.missing_questions:
            parts.append("Missing questions: " + ", ".join(gaps.missing_questions[:10]))
        if gaps.missing_entities:
            parts.append("Missing entities: " + ", ".join(gaps.missing_entities[:10]))
        if gaps.missing_comparisons:
            parts.append("Missing comparisons: " + ", ".join(gaps.missing_comparisons[:10]))
        if gaps.missing_statistics:
            parts.append("Missing statistics/data: " + ", ".join(gaps.missing_statistics[:10]))
        if gaps.missing_user_concerns:
            parts.append("Missing user concerns: " + ", ".join(gaps.missing_user_concerns[:10]))
        if gaps.missing_angles:
            parts.append("Recommended angles: " + ", ".join(gaps.missing_angles[:10]))
        if gaps.competitor_topics_absent_from_ours:
            parts.append("Competitor topics absent from ours: " + ", ".join(gaps.competitor_topics_absent_from_ours[:10]))

        return "\n".join(parts)

    def _generate_seo_strategy(self, topic: str, context: str) -> tuple[SEOStrategy, bool]:
        """Generate SEO strategy using LLM. Returns (strategy, was_parsed)."""
        prompt = self._build_seo_prompt(topic, context)
        response = self.llm_client.generate(prompt)
        return self._parse_seo_response(response, topic)

    def _build_seo_prompt(self, topic: str, context: str) -> str:
        return (
            "You are an SEO content strategist. Create an SEO strategy for the following topic.\n\n"
            f"Topic: {topic}\n\n"
            f"Research Context:\n{context}\n\n"
            "Output ONLY valid JSON with this exact structure:\n"
            "{\n"
            '  "primary_topic": "...",\n'
            '  "search_intent": "informational|commercial|transactional|navigational",\n'
            '  "primary_keyword": "...",\n'
            '  "secondary_keywords": ["...", "..."],\n'
            '  "recommended_title": "...",\n'
            '  "recommended_headings": ["H2 heading 1", "H2 heading 2", "H3 subheading", "..."],\n'
            '  "questions_to_answer": ["question 1", "question 2", "..."],\n'
            '  "internal_linking_opportunities": ["internal page 1", "internal page 2", "..."],\n'
            '  "semantic_coverage_requirements": ["semantic topic 1", "semantic topic 2", "..."]\n'
            "}\n\n"
            "Rules:\n"
            "- Primary topic should be specific and focused\n"
            "- Search intent must be one of the four types\n"
            "- Primary keyword should match search intent\n"
            "- Secondary keywords should be related but distinct\n"
            "- Title should be click-worthy and include primary keyword\n"
            "- Headings should form a logical article structure\n"
            "- Questions should reflect actual user queries\n"
            "- Internal links should be relevant Power.win pages\n"
            "- Semantic coverage should ensure topical authority\n"
            "- Use ONLY information from the research context\n"
            "- Do NOT invent facts or sources"
        )

    def _parse_seo_response(self, response: str, topic: str) -> tuple[SEOStrategy, bool]:
        parsed = bool(response and response.strip())
        if not parsed:
            logger.warning("Empty SEO LLM response, using defaults")
            data = {}
        else:
            try:
                data = json.loads(response.strip())
            except json.JSONDecodeError:
                logger.warning("Failed to parse SEO LLM response, using defaults")
                data = {}
                parsed = False

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
        """Generate AIO (AI Optimization) strategy using LLM. Returns (strategy, was_parsed)."""
        prompt = self._build_aio_prompt(topic, context)
        response = self.llm_client.generate(prompt)
        return self._parse_aio_response(response)

    def _build_aio_prompt(self, topic: str, context: str) -> str:
        return (
            "You are an AI Optimization (AIO) strategist. Create an AIO strategy for the following topic.\n"
            "Goal: Make important information easy for AI systems to understand and extract.\n\n"
            f"Topic: {topic}\n\n"
            f"Research Context:\n{context}\n\n"
            "Output ONLY valid JSON with this exact structure:\n"
            "{\n"
            '  "direct_answer_questions": ["question 1", "question 2", "..."],\n'
            '  "concise_answers": {"question 1": "concise answer", "question 2": "concise answer"},\n'
            '  "definitions": {"term 1": "definition", "term 2": "definition"},\n'
            '  "important_factual_statements": ["verified fact 1", "verified fact 2", "..."],\n'
            '  "entities": ["entity 1", "entity 2", "..."],\n'
            '  "evidence_requirements": ["evidence type 1", "evidence type 2", "..."],\n'
            '  "structured_information_requirements": ["structured format 1", "structured format 2", "..."]\n'
            "}\n\n"
            "Rules:\n"
            "- Direct answer questions should be specific and answerable\n"
            "- Concise answers MUST come from verified facts in the context\n"
            "- Definitions should clarify key terms from the research\n"
            "- Important factual statements MUST be verified facts only\n"
            "- Entities should include brands, organizations, products mentioned\n"
            "- Evidence requirements should specify citation types needed\n"
            "- Structured info: lists, tables, comparisons, step-by-step\n"
            "- Do NOT use unsupported claims as facts\n"
            "- Do NOT invent information not in the research context"
        )

    def _parse_aio_response(self, response: str) -> tuple[AIOStrategy, bool]:
        parsed = bool(response and response.strip())
        if not parsed:
            logger.warning("Empty AIO LLM response, using defaults")
            data = {}
        else:
            try:
                data = json.loads(response.strip())
            except json.JSONDecodeError:
                logger.warning("Failed to parse AIO LLM response, using defaults")
                data = {}
                parsed = False

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
        """Generate GEO (Generative Engine Optimization) strategy using LLM. Returns (strategy, was_parsed)."""
        prompt = self._build_geo_prompt(topic, context)
        response = self.llm_client.generate(prompt)
        return self._parse_geo_response(response)

    def _build_geo_prompt(self, topic: str, context: str) -> str:
        return (
            "You are a Generative Engine Optimization (GEO) strategist. Create a GEO strategy for the following topic.\n"
            "Goal: Optimize content for citation and synthesis by generative AI systems.\n\n"
            f"Topic: {topic}\n\n"
            f"Research Context:\n{context}\n\n"
            "Output ONLY valid JSON with this exact structure:\n"
            "{\n"
            '  "important_entities": ["entity 1", "entity 2", "..."],\n'
            '  "entity_relationships": ["relationship 1", "relationship 2", "..."],\n'
            '  "authoritative_external_sources": ["source 1", "source 2", "..."],\n'
            '  "power_win_first_party_facts": ["fact 1", "fact 2", "..."],\n'
            '  "unique_information": ["unique fact 1", "unique fact 2", "..."],\n'
            '  "citation_evidence_opportunities": ["claim 1", "claim 2", "..."],\n'
            '  "factual_consistency_requirements": ["requirement 1", "requirement 2", "..."],\n'
            '  "questions_to_answer_clearly": ["question 1", "question 2", "..."]\n'
            "}\n\n"
            "Rules:\n"
            "- Important entities should be those generative engines should associate with this content\n"
            "- Entity relationships describe how entities connect (e.g., 'Power.win reviews casinos')\n"
            "- Authoritative external sources should be from verified external facts\n"
            "- Power.win first-party facts MUST come from Power.win verified facts only\n"
            "- Unique information should be facts not available elsewhere\n"
            "- Citation opportunities should be specific claims needing inline evidence\n"
            "- Factual consistency requirements ensure alignment with known sources\n"
            "- Questions to answer clearly should enable generative synthesis\n"
            "- Do NOT use unsupported claims\n"
            "- Do NOT invent information not in the research context"
        )

    def _parse_geo_response(self, response: str) -> tuple[GEOStrategy, bool]:
        parsed = bool(response and response.strip())
        if not parsed:
            logger.warning("Empty GEO LLM response, using defaults")
            data = {}
        else:
            try:
                data = json.loads(response.strip())
            except json.JSONDecodeError:
                logger.warning("Failed to parse GEO LLM response, using defaults")
                data = {}
                parsed = False

        return GEOStrategy(
            important_entities=data.get("important_entities", []),
            entity_relationships=data.get("entity_relationships", []),
            authoritative_external_sources=data.get("authoritative_external_sources", []),
            power_win_first_party_facts=data.get("power_win_first_party_facts", []),
            unique_information=data.get("unique_information", []),
            citation_evidence_opportunities=data.get("citation_evidence_opportunities", []),
            factual_consistency_requirements=data.get("factual_consistency_requirements", []),
            questions_to_answer_clearly=data.get("questions_to_answer_clearly", []),
        ), parsed