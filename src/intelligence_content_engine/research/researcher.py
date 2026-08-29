import hashlib
import json
import logging
import time
from collections import defaultdict
from typing import Optional

from intelligence_content_engine.llm.client import LLMClient
from intelligence_content_engine.research.models import (
    Claim,
    ClaimStatus,
    ConflictingClaim,
    Evidence,
    InformationNature,
    PhaseStatus,
    ResearchGap,
    ResearchPlan,
    ResearchQuestion,
    ResearchResult,
    Source,
    SourceType,
)
from intelligence_content_engine.research.tools import HybridFetcher, SitemapFetcher, WebFetcher, WebSearchTool

logger = logging.getLogger(__name__)

MAX_PLAN_QUESTIONS = 3
MAX_SOURCES_PER_QUESTION = 2
MAX_SITEMAP_SOURCES_TOTAL = 6
MAX_SITEMAP_SOURCES_PER_QUESTION = 2
MAX_FIRST_PARTY_CHECKS = 2
MAX_EXTERNAL_CHECKS = 2
MAX_TOTAL_SOURCES_PROCESSED = 12
MAX_RESEARCH_TIME_SECONDS = 55


class Researcher:
    """Domain-independent research agent using real web sources."""

    def __init__(
        self,
        llm_client: LLMClient,
        search_tool: Optional[WebSearchTool] = None,
        fetcher: Optional[WebFetcher] = None,
        sitemap_fetcher: Optional[SitemapFetcher] = None,
    ) -> None:
        self.llm_client = llm_client
        self.search_tool = search_tool or WebSearchTool()
        self.fetcher = fetcher or HybridFetcher()
        self.sitemap_fetcher = sitemap_fetcher or SitemapFetcher()

    def create_plan(self, topic: str) -> ResearchPlan:
        prompt = self._build_plan_prompt(topic)
        try:
            response = self.llm_client.generate(prompt)
        except Exception as exc:
            logger.debug("Research plan generation failed; using fallback plan: %s", exc)
            return self._build_fallback_plan(topic)

        if not response or not response.strip():
            return self._build_fallback_plan(topic)

        plan = self._parse_plan_response(topic, response)
        return self._build_fallback_plan(topic) if self._is_empty_plan(plan) else plan

    def _is_empty_plan(self, plan: ResearchPlan) -> bool:
        return (
            len(plan.questions) <= 1
            and not plan.required_first_party_checks
            and not plan.required_external_checks
        )

    def _build_fallback_plan(self, topic: str) -> ResearchPlan:
        return ResearchPlan(
            topic=topic,
            questions=[
                ResearchQuestion(
                    question=f"What factual information can be verified about: {topic}?",
                    priority="critical",
                    is_first_party_check=True,
                    required_source_types=[SourceType.FIRST_PARTY],
                    notes="Fallback first-party research question.",
                ),
                ResearchQuestion(
                    question=f"What authoritative external context is relevant to: {topic}?",
                    priority="high",
                    required_source_types=[SourceType.REGULATORY, SourceType.AUTHORITATIVE, SourceType.PRIMARY],
                    notes="Fallback external research question.",
                ),
            ],
            required_first_party_checks=[f"Target-site information relevant to {topic}"],
            required_external_checks=[f"Authoritative external context for {topic}"],
            claims_to_verify=[topic],
        )

    def _build_plan_prompt(self, topic: str) -> str:
        return (
            "You are a research planner for a domain-independent content intelligence engine. "
            "Create a structured research plan for the following topic.\n\n"
            f"Topic: {topic}\n\n"
            "Return ONLY valid JSON with this structure:\n"
            "{\n"
            '  "questions": [{"question": "...", "priority": "critical|high|medium|low", '
            '"required_source_types": ["first_party", "regulatory", "government", "primary", '
            '"authoritative", "secondary", "general", "unknown"], '
            '"is_first_party_check": true|false, "notes": "..."}],\n'
            '  "required_first_party_checks": ["target-site checks"],\n'
            '  "required_external_checks": ["external checks"],\n'
            '  "claims_to_verify": ["claims"]\n'
            "}\n\n"
            "Guidelines:\n"
            "- Use first-party checks only when target-site information is relevant.\n"
            "- Use regulatory/government/authoritative sources when appropriate.\n"
            "- Break the topic into specific, answerable research questions.\n"
            "- Output ONLY valid JSON, no extra text."
        )

    def _parse_plan_response(self, topic: str, response: str) -> ResearchPlan:
        try:
            data = json.loads(response.strip())
        except json.JSONDecodeError:
            return self._build_fallback_plan(topic)

        questions = []
        for item in data.get("questions", []):
            if not isinstance(item, dict):
                continue
            try:
                questions.append(ResearchQuestion(**item))
            except Exception:
                continue

        try:
            return ResearchPlan(
                topic=topic,
                questions=questions,
                required_first_party_checks=data.get("required_first_party_checks", []),
                required_external_checks=data.get("required_external_checks", []),
                claims_to_verify=data.get("claims_to_verify", []),
            )
        except Exception:
            return self._build_fallback_plan(topic)

    async def research(self, topic: str) -> tuple[ResearchResult, PhaseStatus]:
        start_time = time.time()
        plan = self.create_plan(topic)
        used_fallback = any(
            q.notes == "Fallback first-party research question." or q.notes == "Fallback research question generated after planning LLM failure."
            for q in plan.questions
        )
        plan.questions = plan.questions[:MAX_PLAN_QUESTIONS]
        result = ResearchResult(topic=topic, plan=plan, questions=plan.questions)

        first_party_sources: list[Source] = []
        if any(q.is_first_party_check for q in plan.questions):
            try:
                first_party_sources = self.sitemap_fetcher.discover_first_party_sources(topic)
            except Exception as exc:
                logger.debug("First-party sitemap discovery failed: %s", exc)
            first_party_sources = first_party_sources[:MAX_SITEMAP_SOURCES_TOTAL]

        all_evidence: list[tuple[Source, str, str, bool, str]] = []
        total_sources = 0

        for question in plan.questions:
            if self._deadline_reached(start_time):
                break
            evidence, gaps = await self._collect_evidence_for_question(
                question,
                first_party_sources if question.is_first_party_check else [],
            )
            all_evidence.extend(evidence)
            result.research_gaps.extend(gaps)
            total_sources += len(evidence)
            if total_sources >= MAX_TOTAL_SOURCES_PROCESSED:
                break

        first_party_checks = 0
        for check in plan.required_first_party_checks:
            if self._deadline_reached(start_time) or first_party_checks >= MAX_FIRST_PARTY_CHECKS or total_sources >= MAX_TOTAL_SOURCES_PROCESSED:
                break
            question = ResearchQuestion(question=check, priority="high", is_first_party_check=True)
            evidence, gaps = await self._collect_evidence_for_question(question, first_party_sources)
            all_evidence.extend(evidence)
            result.research_gaps.extend(gaps)
            total_sources += len(evidence)
            first_party_checks += 1

        external_checks = 0
        for check in plan.required_external_checks:
            if self._deadline_reached(start_time) or external_checks >= MAX_EXTERNAL_CHECKS or total_sources >= MAX_TOTAL_SOURCES_PROCESSED:
                break
            question = ResearchQuestion(question=check, priority="high")
            evidence, gaps = await self._collect_evidence_for_question(question, [])
            all_evidence.extend(evidence)
            result.research_gaps.extend(gaps)
            total_sources += len(evidence)
            external_checks += 1

        grouped = defaultdict(list)
        for evidence in all_evidence:
            grouped[evidence[2]].append(evidence)

        for question_text, evidence_list in grouped.items():
            if self._deadline_reached(start_time):
                break
            is_first_party = any(item[3] for item in evidence_list)
            claims = self._analyze_evidence_batch(evidence_list, question_text, is_first_party)
            for claim in claims:
                if claim.status in (ClaimStatus.VERIFIED, ClaimStatus.PARTIALLY_SUPPORTED):
                    target = result.first_party_facts if is_first_party else result.external_facts
                    target.append(claim)
                else:
                    result.unsupported_claims.append(claim)

        self._determine_overall_status(result)
        elapsed = time.time() - start_time
        logger.info("Research completed in %.1fs: %d sources, %d first-party facts, %d external facts", elapsed, total_sources, len(result.first_party_facts), len(result.external_facts))

        status = PhaseStatus.SUCCESS
        if used_fallback or not result.first_party_facts and not result.external_facts:
            status = PhaseStatus.DEGRADED
        if elapsed >= MAX_RESEARCH_TIME_SECONDS:
            status = PhaseStatus.DEGRADED
        return result, status

    def _deadline_reached(self, start_time: float) -> bool:
        return time.time() - start_time >= MAX_RESEARCH_TIME_SECONDS

    async def _collect_evidence_for_question(self, question: ResearchQuestion, first_party_sources: list[Source] | None = None) -> tuple[list, list]:
        query = self._build_search_query(question)
        try:
            sources = await self.search_tool.search(query)
        except Exception as exc:
            return [], [ResearchGap(question=question.question, reason=f"Search failed: {exc}", attempted_sources=[query], importance=question.priority)]

        if question.is_first_party_check and first_party_sources:
            relevant = self._filter_sources_by_question(first_party_sources, question)[:MAX_SITEMAP_SOURCES_PER_QUESTION]
            sources = relevant + sources

        if question.required_source_types:
            sources = [source for source in sources if source.source_type in question.required_source_types]

        unique = []
        seen = set()
        for source in sources:
            url = str(source.url)
            if url not in seen:
                seen.add(url)
                unique.append(source)

        if not unique:
            return [], [ResearchGap(question=question.question, reason="No suitable sources found in search results", attempted_sources=[query], importance=question.priority)]

        evidence = []
        gaps = []
        for source in unique[:MAX_SOURCES_PER_QUESTION]:
            try:
                content = self.fetcher.fetch(str(source.url))
            except Exception as exc:
                content = None
                logger.debug("Failed to fetch %s: %s", source.url, exc)
            if not content:
                gaps.append(ResearchGap(question=question.question, reason=f"Could not fetch source: {source.name}", attempted_sources=[str(source.url)], importance=question.priority))
                continue
            method = "browser" if hasattr(self.fetcher, "browser_fetcher") else "http"
            evidence.append((source, content, question.question, question.is_first_party_check, method))
        return evidence, gaps

    def _build_search_query(self, question: ResearchQuestion) -> str:
        return question.question

    def _filter_sources_by_question(self, sources: list[Source], question: ResearchQuestion) -> list[Source]:
        return sources

    def _analyze_evidence_batch(self, evidence_list: list, question: str, is_first_party: bool) -> list[Claim]:
        if not evidence_list:
            return []
        prompt = self._build_batch_analysis_prompt(evidence_list, question, is_first_party)
        try:
            response = self.llm_client.generate(prompt)
            data = json.loads(response.strip())
        except Exception as exc:
            logger.warning("Evidence analysis failed for %s: %s", question[:80], exc)
            return []

        claims = []
        for claim_data in data.get("claims", []):
            claim = self._parse_batch_claim(claim_data, evidence_list)
            if claim:
                claims.append(claim)
        return claims

    def _build_extraction_prompt(self, content: str, source: Source, question: str, is_first_party: bool) -> str:
        source_type = source.source_type.value if hasattr(source.source_type, "value") else source.source_type
        return (
            "Extract verifiable claims from the supplied source content.\n\n"
            f"Source: {source.name} ({source.url})\nSource Type: {source_type}\n"
            f"Research Question: {question}\nTarget First-Party Check: {is_first_party}\n\n"
            f"Source Content (truncated):\n{content[:8000]}\n\n"
            "Return ONLY JSON with a claims array. Every excerpt MUST be an exact quote from the supplied source."
        )

    def _build_batch_analysis_prompt(self, evidence_list: list, question: str, is_first_party: bool) -> str:
        blocks = []
        for index, (source, content, _, _, _) in enumerate(evidence_list, start=1):
            source_type = source.source_type.value if hasattr(source.source_type, "value") else source.source_type
            blocks.append(f"SOURCE {index}:\nName: {source.name}\nURL: {source.url}\nType: {source_type}\nContent:\n{content[:5000]}\n")
        return (
            "You are a research assistant analyzing multiple sources to extract verifiable claims.\n\n"
            f"Research Question: {question}\nTarget First-Party Check: {is_first_party}\n\n"
            + "\n".join(blocks)
            + "\nReturn ONLY JSON with a claims array. Each claim must contain text, status, nature, source_index, exact excerpt, confidence, and notes.\n"
            "Rules: only use claims directly supported by the supplied content; source_index is 1-based; "
            "the excerpt MUST be an exact quote from the selected source; do not invent information."
        )

    def _parse_batch_claim(self, claim_data: dict, evidence_list: list) -> Optional[Claim]:
        try:
            status = ClaimStatus(claim_data.get("status", "uncertain"))
        except ValueError:
            status = ClaimStatus.UNCERTAIN
        try:
            nature = InformationNature(claim_data.get("nature", "fact"))
        except ValueError:
            nature = InformationNature.FACT

        excerpt = str(claim_data.get("excerpt", "")).strip()
        if not excerpt:
            return None
        try:
            source_index = int(claim_data.get("source_index", 1)) - 1
        except (TypeError, ValueError):
            return None
        if not 0 <= source_index < len(evidence_list):
            return None

        source, content, _, _, retrieval_method = evidence_list[source_index]
        if excerpt not in content:
            logger.warning("Rejecting claim with excerpt not present in retrieved source: %s", source.url)
            return None

        content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        evidence = Evidence(
            source=source,
            excerpt=excerpt,
            notes=claim_data.get("notes"),
            retrieval_method=retrieval_method,
            content_sha256=content_sha256,
            excerpt_verified=True,
        )
        return Claim(
            text=claim_data.get("text", ""),
            status=status,
            nature=nature,
            evidence=[evidence],
            confidence=claim_data.get("confidence", 0.0),
            notes=claim_data.get("notes"),
        )

    def _determine_overall_status(self, result: ResearchResult) -> None:
        supported = result.first_party_facts + result.external_facts
        total = len(supported) + len(result.unsupported_claims)
        if total == 0:
            result.status = ClaimStatus.UNCERTAIN
        elif result.conflicting_information:
            result.status = ClaimStatus.CONFLICTING
        elif any(c.status == ClaimStatus.VERIFIED for c in supported) and not result.unsupported_claims:
            result.status = ClaimStatus.VERIFIED
        elif supported:
            result.status = ClaimStatus.PARTIALLY_SUPPORTED
        else:
            result.status = ClaimStatus.UNSUPPORTED
        result.summary = self._generate_summary(result)

    def _generate_summary(self, result: ResearchResult) -> str:
        parts = []
        if result.first_party_facts:
            parts.append(f"Found {len(result.first_party_facts)} first-party facts")
        if result.external_facts:
            parts.append(f"{len(result.external_facts)} external facts")
        if result.unsupported_claims:
            parts.append(f"{len(result.unsupported_claims)} unsupported claims")
        if result.research_gaps:
            parts.append(f"{len(result.research_gaps)} research gaps")
        return "; ".join(parts) if parts else "No findings"
