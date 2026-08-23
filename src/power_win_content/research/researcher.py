import json
import logging
import time
from typing import Optional

from power_win_content.llm.client import LLMClient
from power_win_content.research.models import (
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
from power_win_content.research.tools import WebFetcher, WebSearchTool, HybridFetcher, SitemapFetcher

logger = logging.getLogger(__name__)

# Bounded limits to prevent unbounded execution time
MAX_PLAN_QUESTIONS = 3          # Tightened from 5
MAX_SOURCES_PER_QUESTION = 2    # Tightened from 3
MAX_SITEMAP_SOURCES_TOTAL = 6   # Tightened from 15
MAX_SITEMAP_SOURCES_PER_QUESTION = 2  # Tightened from 3
MAX_POWER_WIN_CHECKS = 2        # Tightened from 3
MAX_EXTERNAL_CHECKS = 2         # Tightened from 3
MAX_TOTAL_SOURCES_PROCESSED = 12  # Tightened from 25
MAX_RESEARCH_TIME_SECONDS = 55   # Must finish clearly before CLI timeout


class Researcher:
    """Research agent that produces structured research packages using real web sources."""

    def __init__(
        self,
        llm_client: LLMClient,
        search_tool: Optional[WebSearchTool] = None,
        fetcher: Optional[WebFetcher] = None,
        sitemap_fetcher: Optional[SitemapFetcher] = None,
    ) -> None:
        self.llm_client = llm_client
        self.search_tool = search_tool or WebSearchTool()
        # Default to HybridFetcher (HTTP + browser fallback) for better SPA/Cloudflare handling
        self.fetcher = fetcher or HybridFetcher()
        # Sitemap fetcher for first-party source discovery
        self.sitemap_fetcher = sitemap_fetcher or SitemapFetcher()

    def create_plan(self, topic: str) -> ResearchPlan:
        """Create a structured research plan for the given topic."""
        prompt = self._build_plan_prompt(topic)
        try:
            response = self.llm_client.generate(prompt)
        except Exception as exc:
            logger.debug("Research plan LLM generation failed, using fallback plan: %s", exc)
            return self._build_fallback_plan(topic)

        if not response or not response.strip():
            logger.debug("Research plan LLM returned empty response, using fallback plan")
            return self._build_fallback_plan(topic)

        plan = self._parse_plan_response(topic, response)
        if self._is_empty_plan(plan):
            logger.debug("Research plan LLM response produced empty plan, using fallback plan")
            return self._build_fallback_plan(topic)

        return plan

    def _is_empty_plan(self, plan: ResearchPlan) -> bool:
        return (
            len(plan.questions) <= 1
            and len(plan.required_power_win_checks) == 0
            and len(plan.required_external_checks) == 0
        )

    def _build_fallback_plan(self, topic: str) -> ResearchPlan:
        return ResearchPlan(
            topic=topic,
            questions=[
                ResearchQuestion(
                    question=f"What factual information can be verified for: {topic}?",
                    priority="critical",
                    is_power_win_check=True,
                    required_source_types=[SourceType.FIRST_PARTY],
                    notes="Fallback research question generated after planning LLM failure.",
                ),
                ResearchQuestion(
                    question=f"What authoritative external context is relevant to: {topic}?",
                    priority="high",
                    is_power_win_check=False,
                    required_source_types=[SourceType.REGULATORY, SourceType.AUTHORITATIVE, SourceType.PRIMARY],
                    notes="Fallback external context question generated after planning LLM failure.",
                ),
            ],
            required_power_win_checks=[
                "Power.win editorial methodology or review process",
                "Power.win responsible gambling and transparency information",
            ],
            required_external_checks=[
                "online casino review methodology standards",
                "online gambling licensing and responsible gambling guidance",
            ],
            claims_to_verify=[topic],
        )

    def _build_plan_prompt(self, topic: str) -> str:
        """Build the prompt for creating a research plan."""
        return (
            "You are a research planner for Power.win content. Create a detailed research plan "
            "for the following article topic.\n\n"
            f"Topic: {topic}\n\n"
            "Your task is to output a JSON object with the following structure:\n"
            "{\n"
            '  "questions": [\n'
            '    {"question": "...", "priority": "critical|high|medium|low", '
            '"required_source_types": ["first_party", "regulatory", "government", "primary", '
            '"authoritative", "secondary", "general", "unknown"], '
            '"is_power_win_check": true|false, "notes": "..."},\n'
            '    ...\n'
            "  ],\n"
            '  "required_power_win_checks": ["specific Power.win pages/sections to check"],\n'
            '  "required_external_checks": ["external sources to consult"],\n'
            '  "claims_to_verify": ["specific claims that need verification"]\n'
            "}\n\n"
            "Guidelines:\n"
            "- Always include Power.win-specific checks when Power.win is relevant to the topic\n"
            "- For Power.win topics, check: editorial methodology, product info, features, "
            "licensing stated on site, payment methods, bonuses, responsible gambling info, "
            "terms, contact/support\n"
            "- For gambling regulation topics, include regulatory/government source checks\n"
            "- Break the topic into specific, answerable research questions\n"
            "- Mark questions that require Power.win sources with is_power_win_check=true\n"
            "- Prioritize: critical > high > medium > low\n"
            "- Output ONLY valid JSON, no extra text"
        )

    def _build_research_prompt(self, topic: str, plan: ResearchPlan) -> str:
        """Build the prompt for executing research (legacy method for backward compatibility)."""
        questions_json = [
            {
                "question": q.question,
                "priority": q.priority,
                "is_power_win_check": q.is_power_win_check,
                "required_source_types": [s.value for s in q.required_source_types],
            }
            for q in plan.questions
        ]

        return (
            "You are a researcher for Power.win content. Research the following topic "
            "using the provided research plan. You must output a structured research result.\n\n"
            f"Topic: {topic}\n\n"
            f"Research Plan Questions: {json.dumps(questions_json, indent=2)}\n\n"
            f"Required Power.win Checks: {plan.required_power_win_checks}\n\n"
            f"Required External Checks: {plan.required_external_checks}\n\n"
            f"Claims to Verify: {plan.claims_to_verify}\n\n"
            "Output a JSON object with this exact structure:\n"
            "{\n"
            '  "power_win_facts": [\n'
            '    {"text": "...", "status": "verified|partially_supported|unsupported|conflicting|uncertain", '
            '"nature": "fact|editorial_interpretation|opinion", '
            '"evidence": [{"source_name": "...", "source_url": "...", "source_type": "...", '
            '"excerpt": "...", "source_title": "...", "source_publication_date": "...", '
            '"source_updated_date": "...", "notes": "..."}], '
            '"confidence": 0.0-1.0, "notes": "..."},\n'
            '    ...\n'
            "  ],\n"
            '  "external_facts": [ ... same structure ... ],\n'
            '  "unsupported_claims": [ ... same structure ... ],\n'
            '  "conflicting_information": [\n'
            '    {"topic": "...", "claim_a": {...}, "claim_b": {...}, '
            '"resolution": "...", "status": "conflicting"},\n'
            '    ...\n'
            "  ],\n"
            '  "research_gaps": [\n'
            '    {"question": "...", "reason": "...", "attempted_sources": [...], '
            '"importance": "low|medium|high"},\n'
            '    ...\n'
            "  ],\n"
            '  "summary": "Narrative summary of findings",\n'
            '  "status": "verified|partially_supported|unsupported|conflicting|uncertain"\n'
            "}\n\n"
            "Critical Rules:\n"
            "- NEVER invent facts about Power.win. If information cannot be verified, "
            "put it in unsupported_claims or research_gaps\n"
            "- Separate Power.win-specific facts (first_party sources) from external facts\n"
            "- Every factual claim MUST have evidence with source information\n"
            "- Distinguish: fact (verifiable), editorial_interpretation (analysis), opinion\n"
            "- For unsupported claims: status=unsupported, evidence=[]\n"
            "- For conflicting sources: put in conflicting_information with both claims\n"
            "- For unanswerable questions: put in research_gaps with reason\n"
            "- Output ONLY valid JSON, no extra text"
        )

    def research(self, topic: str) -> tuple[ResearchResult, PhaseStatus]:
        """Perform research on the topic using real web sources and return a ResearchResult.

        Bounded execution with hard limits:
        - MAX_PLAN_QUESTIONS (5): Maximum questions in research plan
        - MAX_SOURCES_PER_QUESTION (3): Sources processed per question
        - MAX_SITEMAP_SOURCES_TOTAL (15): Total sitemap sources discovered
        - MAX_SITEMAP_SOURCES_PER_QUESTION (3): Sitemap sources per question
        - MAX_POWER_WIN_CHECKS (3): Power.win specific checks
        - MAX_EXTERNAL_CHECKS (3): External source checks
        - MAX_TOTAL_SOURCES_PROCESSED (25): Hard limit on all sources
        - MAX_RESEARCH_TIME_SECONDS (300): 5 minute hard timeout

        Model: Web search -> Sitemap discovery -> Fetch sources -> Collect evidence -> LLM analyzes evidence
        """
        start_time = time.time()
        llm_calls = 0
        llm_success = 0
        llm_429_count = 0
        used_fallback_plan = False

        # 1. Create research plan (1 LLM call)
        plan = self.create_plan(topic)
        llm_calls += 1
        llm_success += 1

        if any(q.notes == "Fallback research question generated after planning LLM failure." for q in plan.questions):
            used_fallback_plan = True

        # Bound the plan questions
        if len(plan.questions) > MAX_PLAN_QUESTIONS:
            logger.warning("Plan has %d questions, limiting to %d", len(plan.questions), MAX_PLAN_QUESTIONS)
            plan.questions = plan.questions[:MAX_PLAN_QUESTIONS]

        # Initialize result
        result = ResearchResult(topic=topic, plan=plan, questions=plan.questions)

        # 2. Discover first-party sources via sitemap (no LLM)
        is_power_win_topic = any(q.is_power_win_check for q in plan.questions)
        first_party_sources = []
        if is_power_win_topic:
            first_party_sources = self.sitemap_fetcher.discover_first_party_sources(topic)
            if len(first_party_sources) > MAX_SITEMAP_SOURCES_TOTAL:
                logger.warning("Sitemap returned %d sources, limiting to %d", len(first_party_sources), MAX_SITEMAP_SOURCES_TOTAL)
                first_party_sources = first_party_sources[:MAX_SITEMAP_SOURCES_TOTAL]

        # 3. Collect evidence from all sources FIRST (no LLM calls during fetch)
        all_evidence = []  # List of (source, content, question, is_power_win, retrieval_method)
        sources_fetched = 0
        sources_failed = 0

        # Process research questions
        for question in plan.questions:
            if time.time() - start_time > MAX_RESEARCH_TIME_SECONDS:
                logger.warning("Research time limit reached (%ds), stopping evidence collection", MAX_RESEARCH_TIME_SECONDS)
                break

            evidence, gaps = self._collect_evidence_for_question(
                question, first_party_sources if question.is_power_win_check else []
            )
            all_evidence.extend(evidence)
            sources_fetched += len(evidence)
            result.research_gaps.extend(gaps)

        # Process Power.win checks
        pw_checks_processed = 0
        for pw_check in plan.required_power_win_checks:
            if time.time() - start_time > MAX_RESEARCH_TIME_SECONDS:
                break
            if pw_checks_processed >= MAX_POWER_WIN_CHECKS:
                logger.warning("Power.win checks limit reached (%d), stopping", MAX_POWER_WIN_CHECKS)
                break

            question = ResearchQuestion(
                question=pw_check,
                priority="high",
                is_power_win_check=True,
            )
            evidence, gaps = self._collect_evidence_for_question(question, first_party_sources)
            all_evidence.extend(evidence)
            sources_fetched += len(evidence)
            result.research_gaps.extend(gaps)
            pw_checks_processed += 1

        # Process external checks
        ext_checks_processed = 0
        for ext_check in plan.required_external_checks:
            if time.time() - start_time > MAX_RESEARCH_TIME_SECONDS:
                break
            if ext_checks_processed >= MAX_EXTERNAL_CHECKS:
                logger.warning("External checks limit reached (%d), stopping", MAX_EXTERNAL_CHECKS)
                break

            question = ResearchQuestion(
                question=ext_check,
                priority="high",
                is_power_win_check=False,
            )
            evidence, gaps = self._collect_evidence_for_question(question, [])
            all_evidence.extend(evidence)
            sources_fetched += len(evidence)
            result.research_gaps.extend(gaps)
            ext_checks_processed += 1

        logger.info("Evidence collection: %d sources fetched, %d failed", sources_fetched, sources_failed)

        # 4. Analyze collected evidence with LLM (batched - 1 call per question/check)
        # Group evidence by question
        from collections import defaultdict
        evidence_by_question = defaultdict(list)
        for ev in all_evidence:
            evidence_by_question[ev[2]].append(ev)  # group by question

        for question_text, ev_list in evidence_by_question.items():
            if time.time() - start_time > MAX_RESEARCH_TIME_SECONDS:
                logger.warning("Research time limit reached (%ds), stopping analysis", MAX_RESEARCH_TIME_SECONDS)
                break

            # Determine if this is a Power.win question
            is_pw = any(ev[3] for ev in ev_list)  # is_power_win flag

            # Single LLM call to analyze all evidence for this question
            claims = self._analyze_evidence_batch(ev_list, question_text, is_pw)
            llm_calls += 1
            if claims:
                llm_success += 1

            for claim in claims:
                if is_pw:
                    if claim.status in (ClaimStatus.VERIFIED, ClaimStatus.PARTIALLY_SUPPORTED):
                        result.power_win_facts.append(claim)
                    else:
                        result.unsupported_claims.append(claim)
                else:
                    if claim.status in (ClaimStatus.VERIFIED, ClaimStatus.PARTIALLY_SUPPORTED):
                        result.external_facts.append(claim)
                    else:
                        result.unsupported_claims.append(claim)

        # 5. Determine overall status
        self._determine_overall_status(result)

        elapsed = time.time() - start_time
        logger.info(
            "Research completed in %.1fs: %d questions, %d sources discovered, "
            "%d sources fetched, %d LLM calls (%d success, %d 429)",
            elapsed,
            len(plan.questions),
            len(first_party_sources) if is_power_win_topic else 0,
            sources_fetched,
            llm_calls,
            llm_success,
            llm_429_count,
        )

        research_phase_status = PhaseStatus.SUCCESS
        if used_fallback_plan:
            research_phase_status = PhaseStatus.DEGRADED
        elif len(result.power_win_facts) == 0 and len(result.external_facts) == 0:
            research_phase_status = PhaseStatus.DEGRADED

        return result, research_phase_status

    def _research_question(self, question: ResearchQuestion, result: ResearchResult, first_party_sources: list = None) -> None:
        """Research a single question by searching, fetching, and extracting evidence."""
        # Build search query
        query = self._build_search_query(question)
        logger.info("Searching for: %s", query)

        # Search for sources (bounded by search tool's own limits)
        sources = self.search_tool.search(query)

        # For Power.win questions, prioritize accessible first-party sources from sitemap (bounded)
        if question.is_power_win_check and first_party_sources:
            # Filter first_party_sources by relevance to question
            relevant_first_party = self._filter_sources_by_question(first_party_sources, question)
            # Limit sitemap sources per question
            if len(relevant_first_party) > MAX_SITEMAP_SOURCES_PER_QUESTION:
                relevant_first_party = relevant_first_party[:MAX_SITEMAP_SOURCES_PER_QUESTION]
            # Prepend them to sources so they're processed first
            # This ensures docs.power.win and blog.power.win are tried before power.win
            sources = relevant_first_party + sources

        # Filter sources by required types if specified
        if question.required_source_types:
            sources = [s for s in sources if s.source_type in question.required_source_types]

        if not sources:
            # No sources found - record research gap
            gap = ResearchGap(
                question=question.question,
                reason="No suitable sources found in search results",
                attempted_sources=[query],
                importance=question.priority,
            )
            result.research_gaps.append(gap)
            return

        # Fetch content from sources and extract claims (bounded)
        for source in sources[:MAX_SOURCES_PER_QUESTION]:  # Limit to top N sources per question
            self._process_source(source, question, result)

    def _build_search_query(self, question: ResearchQuestion) -> str:
        """Build a search query from a research question."""
        query = question.question
        # Don't append site:power.win as it causes 403 from DuckDuckGo
        # We rely on sitemap discovery for first-party sources instead
        return query

    def _filter_sources_by_question(self, sources: list[Source], question: ResearchQuestion) -> list[Source]:
        """Filter and prioritize first-party sources by relevance to question.

        Priority order:
        1. docs.power.win (documentation)
        2. blog.power.win (blog/articles)
        3. power.win (main site - may be inaccessible)
        """
        # Define priority order for power.win subdomains
        def get_priority(source: Source) -> int:
            url_lower = str(source.url).lower()
            if "docs.power.win" in url_lower:
                return 1
            elif "blog.power.win" in url_lower:
                return 2
            elif "power.win" in url_lower:
                return 3
            return 4

        # Sort by priority
        sorted_sources = sorted(sources, key=get_priority)
        return sorted_sources

    def _process_source(
        self, source: Source, question: ResearchQuestion, result: ResearchResult
    ) -> None:
        """Fetch a source and extract relevant claims/evidence."""
        # Fetch the page content
        content = self.fetcher.fetch(str(source.url))
        if not content:
            # Record gap for failed fetch
            gap = ResearchGap(
                question=f"Failed to fetch: {source.name}",
                reason="Network error, timeout, or non-text content",
                attempted_sources=[str(source.url)],
                importance=question.priority,
            )
            result.research_gaps.append(gap)
            return

        # Determine retrieval method
        retrieval_method = "browser" if hasattr(self.fetcher, 'browser_fetcher') else "http"

        # Use LLM to extract claims from the content
        claims = self._extract_claims_from_content(
            content=content,
            source=source,
            question=question.question,
            is_power_win=question.is_power_win_check,
            retrieval_method=retrieval_method,
        )

        # Add claims to appropriate lists in result
        for claim in claims:
            if question.is_power_win_check:
                if claim.status == ClaimStatus.VERIFIED or claim.status == ClaimStatus.PARTIALLY_SUPPORTED:
                    result.power_win_facts.append(claim)
                else:
                    result.unsupported_claims.append(claim)
            else:
                if claim.status == ClaimStatus.VERIFIED or claim.status == ClaimStatus.PARTIALLY_SUPPORTED:
                    result.external_facts.append(claim)
                else:
                    result.unsupported_claims.append(claim)

    def _search_and_process_power_win(self, check: str, result: ResearchResult) -> None:
        """Search Power.win for a specific check and process results.

        Prioritizes accessible first-party sources: docs.power.win > blog.power.win > power.win

        Bounded: limits sitemap sources per check to MAX_SITEMAP_SOURCES_PER_QUESTION,
        and total sources processed to 3.
        """
        # First try to get relevant first-party sources from sitemap (bounded)
        first_party_sources = self.sitemap_fetcher.discover_first_party_sources(check)
        if len(first_party_sources) > MAX_SITEMAP_SOURCES_TOTAL:
            first_party_sources = first_party_sources[:MAX_SITEMAP_SOURCES_TOTAL]

        # Filter to relevant ones
        relevant_sources = self._filter_sources_by_question(first_party_sources,
            ResearchQuestion(question=check, priority="high", is_power_win_check=True))
        if len(relevant_sources) > MAX_SITEMAP_SOURCES_PER_QUESTION:
            relevant_sources = relevant_sources[:MAX_SITEMAP_SOURCES_PER_QUESTION]

        # Also search as fallback
        query = f"{check} site:power.win"
        search_sources = self.search_tool.search(query)
        power_win_search_sources = [s for s in search_sources if s.source_type == SourceType.FIRST_PARTY]

        # Combine: sitemap sources first (prioritized), then search sources
        all_sources = relevant_sources + power_win_search_sources

        # Deduplicate by URL
        seen_urls = set()
        unique_sources = []
        for source in all_sources:
            url_str = str(source.url)
            if url_str not in seen_urls:
                seen_urls.add(url_str)
                unique_sources.append(source)

        # Limit to top 3 sources
        for source in unique_sources[:3]:
            self._process_source(
                source,
                ResearchQuestion(
                    question=check,
                    priority="high",
                    is_power_win_check=True,
                ),
                result,
            )

    def _search_and_process_external(self, check: str, result: ResearchResult) -> None:
        """Search for external sources and process results."""
        sources = self.search_tool.search(check)

        # Prefer higher-authority sources
        priority_order = [
            SourceType.REGULATORY,
            SourceType.GOVERNMENT,
            SourceType.PRIMARY,
            SourceType.AUTHORITATIVE,
            SourceType.SECONDARY,
            SourceType.GENERAL,
        ]

        # Sort by priority
        sources.sort(key=lambda s: priority_order.index(s.source_type) if s.source_type in priority_order else 99)

        for source in sources[:3]:
            self._process_source(
                source,
                ResearchQuestion(
                    question=check,
                    priority="high",
                    is_power_win_check=False,
                ),
                result,
            )

    def _extract_claims_from_content(
        self,
        content: str,
        source: Source,
        question: str,
        is_power_win: bool,
        retrieval_method: str = "http",
    ) -> list[Claim]:
        """Use LLM to extract structured claims with evidence from source content."""
        prompt = self._build_extraction_prompt(content, source, question, is_power_win)
        response = self.llm_client.generate(prompt)

        try:
            data = json.loads(response.strip())
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM extraction response for %s", source.name)
            return []

        claims = []
        for claim_data in data.get("claims", []):
            claim = self._parse_extracted_claim(claim_data, source, retrieval_method)
            if claim:
                claims.append(claim)

        return claims

    def _build_extraction_prompt(
        self, content: str, source: Source, question: str, is_power_win: bool
    ) -> str:
        # Handle both enum and string source_type (from use_enum_values)
        source_type_str = source.source_type.value if hasattr(source.source_type, 'value') else source.source_type
        return (
            "You are a research assistant extracting verifiable claims from source content.\n\n"
            f"Source: {source.name} ({source.url})\n"
            f"Source Type: {source_type_str}\n"
            f"Research Question: {question}\n"
            f"Is Power.win Check: {is_power_win}\n\n"
            f"Source Content (truncated):\n{content[:8000]}\n\n"
            "Extract claims that answer the research question. Output JSON:\n"
            "{\n"
            '  "claims": [\n'
            '    {"text": "...", "status": "verified|partially_supported|unsupported|conflicting|uncertain", '
            '"nature": "fact|editorial_interpretation|opinion", '
            '"excerpt": "exact supporting text from source", '
            '"confidence": 0.0-1.0, "notes": "..."},\n'
            '    ...\n'
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Only extract claims DIRECTLY SUPPORTED by the provided source text\n"
            "- The 'excerpt' MUST be an exact quote from the source content\n"
            "- If the source doesn't answer the question, return empty claims array\n"
            "- status=verified: source directly confirms the claim\n"
            "- status=partially_supported: source supports part but not all\n"
            "- status=unsupported: source mentions topic but doesn't confirm\n"
            "- nature=fact: verifiable objective statement\n"
            "- nature=editorial_interpretation: analysis of facts\n"
            "- nature=opinion: subjective view\n"
            "- If multiple conflicting claims in same source, include all with appropriate status\n"
            "- Output ONLY valid JSON"
        )

    def _parse_extracted_claim(self, claim_data: dict, source: Source, retrieval_method: str = "http") -> Optional[Claim]:
        """Parse an extracted claim into a Claim object with evidence."""
        try:
            status = ClaimStatus(claim_data.get("status", "uncertain"))
        except ValueError:
            status = ClaimStatus.UNCERTAIN

        try:
            nature = InformationNature(claim_data.get("nature", "fact"))
        except ValueError:
            nature = InformationNature.FACT

        excerpt = claim_data.get("excerpt", "")
        if not excerpt:
            return None  # No evidence, skip

        evidence = Evidence(
            source=source,
            excerpt=excerpt,
            notes=claim_data.get("notes"),
            retrieval_method=retrieval_method,
        )

        return Claim(
            text=claim_data.get("text", ""),
            status=status,
            nature=nature,
            evidence=[evidence],
            confidence=claim_data.get("confidence", 0.0),
            notes=claim_data.get("notes"),
        )

    def _collect_evidence_for_question(
        self,
        question: ResearchQuestion,
        first_party_sources: list = None,
    ) -> tuple[list, list]:
        """Collect evidence from sources for a single question (no LLM calls).

        Returns tuple of (evidence_list, gaps_list) where:
        - evidence_list: list of tuples (source, content, question_text, is_power_win, retrieval_method)
        - gaps_list: list of ResearchGap objects
        """
        # Build search query
        query = self._build_search_query(question)
        logger.info("Searching for: %s", query)

        # Search for sources (bounded by search tool's own limits)
        sources = self.search_tool.search(query)

        # For Power.win questions, prioritize accessible first-party sources from sitemap (bounded)
        if question.is_power_win_check and first_party_sources:
            # Filter first_party_sources by relevance to question
            relevant_first_party = self._filter_sources_by_question(first_party_sources, question)
            # Limit sitemap sources per question
            if len(relevant_first_party) > MAX_SITEMAP_SOURCES_PER_QUESTION:
                relevant_first_party = relevant_first_party[:MAX_SITEMAP_SOURCES_PER_QUESTION]
            # Prepend them to sources so they're processed first
            sources = relevant_first_party + sources

        # Filter sources by required types if specified
        if question.required_source_types:
            sources = [s for s in sources if s.source_type in question.required_source_types]

        evidence = []
        gaps = []

        if not sources:
            # No sources found - record research gap
            gap = ResearchGap(
                question=question.question,
                reason="No suitable sources found in search results",
                attempted_sources=[query],
                importance=question.priority,
            )
            gaps.append(gap)
            return evidence, gaps

        # Fetch content from sources (bounded, NO LLM CALLS)
        for source in sources[:MAX_SOURCES_PER_QUESTION]:
            content = self.fetcher.fetch(str(source.url))
            if not content:
                logger.warning("Failed to fetch: %s", source.url)
                gaps.append(ResearchGap(
                    question=question.question,
                    reason=f"Could not fetch source: {source.name}",
                    attempted_sources=[str(source.url)],
                    importance=question.priority,
                ))
                continue

            retrieval_method = "browser" if hasattr(self.fetcher, 'browser_fetcher') else "http"
            evidence.append((source, content, question.question, question.is_power_win_check, retrieval_method))

        return evidence, gaps

    def _analyze_evidence_batch(
        self,
        evidence_list: list,
        question: str,
        is_power_win: bool,
    ) -> list[Claim]:
        """Analyze multiple pieces of evidence for a question in a single LLM call.

        Returns list of Claims with evidence attached.
        """
        if not evidence_list:
            return []

        # Build combined prompt with all source content
        prompt = self._build_batch_analysis_prompt(evidence_list, question, is_power_win)

        try:
            response = self.llm_client.generate(prompt)
        except Exception as e:
            logger.warning("LLM analysis failed for question '%s': %s", question[:80], e)
            return []

        try:
            data = json.loads(response.strip())
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM batch analysis response")
            return []

        claims = []
        for claim_data in data.get("claims", []):
            # Need to find the source for this claim based on the excerpt
            claim = self._parse_batch_claim(claim_data, evidence_list)
            if claim:
                claims.append(claim)

        return claims

    def _build_batch_analysis_prompt(
        self,
        evidence_list: list,
        question: str,
        is_power_win: bool,
    ) -> str:
        """Build prompt for batch analysis of multiple sources."""
        source_blocks = []
        for i, (source, content, q_text, is_pw, retrieval_method) in enumerate(evidence_list):
            source_type_str = source.source_type.value if hasattr(source.source_type, 'value') else source.source_type
            source_blocks.append(
                f"SOURCE {i+1}:\n"
                f"  Name: {source.name}\n"
                f"  URL: {source.url}\n"
                f"  Type: {source_type_str}\n"
                f"  Content:\n{content[:5000]}\n"  # Truncate per source to keep prompt manageable
            )

        sources_text = "\n".join(source_blocks)

        return (
            "You are a research assistant analyzing multiple sources to extract verifiable claims.\n\n"
            f"Research Question: {question}\n"
            f"Is Power.win Check: {is_power_win}\n\n"
            f"Sources:\n{sources_text}\n\n"
            "Extract claims that answer the research question using ONLY the provided source content. "
            "Output JSON:\n"
            "{\n"
            '  "claims": [\n'
            '    {"text": "...", "status": "verified|partially_supported|unsupported|conflicting|uncertain", '
            '"nature": "fact|editorial_interpretation|opinion", '
            '"source_index": 0,  // which source (1-based index from above) supports this claim\n'
            '"excerpt": "exact supporting text from that source", '
            '"confidence": 0.0-1.0, "notes": "..."},\n'
            '    ...\n'
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Only extract claims DIRECTLY SUPPORTED by the provided source text\n"
            "- The 'excerpt' MUST be an exact quote from the source content\n"
            "- If the sources don't answer the question, return empty claims array\n"
            "- status=verified: source directly confirms the claim\n"
            "- status=partially_supported: source supports part but not all\n"
            "- status=unsupported: source mentions topic but doesn't confirm\n"
            "- nature=fact: verifiable objective statement\n"
            "- nature=editorial_interpretation: analysis of facts\n"
            "- nature=opinion: subjective view\n"
            "- source_index is 1-based (1, 2, 3...)\n"
            "- If multiple sources support the same claim, include it once with the best source\n"
            "- If conflicting information across sources, include both claims with appropriate status\n"
            "- Output ONLY valid JSON"
        )

    def _parse_batch_claim(self, claim_data: dict, evidence_list: list) -> Optional[Claim]:
        """Parse a batch analysis claim into a Claim object with evidence."""
        try:
            status = ClaimStatus(claim_data.get("status", "uncertain"))
        except ValueError:
            status = ClaimStatus.UNCERTAIN

        try:
            nature = InformationNature(claim_data.get("nature", "fact"))
        except ValueError:
            nature = InformationNature.FACT

        excerpt = claim_data.get("excerpt", "")
        if not excerpt:
            return None

        # Find the source based on source_index
        source_index = claim_data.get("source_index", 1) - 1  # Convert to 0-based
        if source_index < 0 or source_index >= len(evidence_list):
            return None

        source, _, _, _, retrieval_method = evidence_list[source_index]

        evidence = Evidence(
            source=source,
            excerpt=excerpt,
            notes=claim_data.get("notes"),
            retrieval_method=retrieval_method,
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
        """Determine overall research status based on findings."""
        total_claims = (
            len(result.power_win_facts)
            + len(result.external_facts)
            + len(result.unsupported_claims)
        )
        if total_claims == 0:
            result.status = ClaimStatus.UNCERTAIN
            return

        verified_count = sum(
            1
            for c in result.power_win_facts + result.external_facts
            if c.status == ClaimStatus.VERIFIED
        )
        supported_count = sum(
            1
            for c in result.power_win_facts + result.external_facts
            if c.status == ClaimStatus.PARTIALLY_SUPPORTED
        )
        unsupported_count = len(result.unsupported_claims)
        conflict_count = len(result.conflicting_information)

        if conflict_count > 0:
            result.status = ClaimStatus.CONFLICTING
        elif verified_count > 0 and unsupported_count == 0:
            result.status = ClaimStatus.VERIFIED
        elif verified_count > 0 or supported_count > 0:
            result.status = ClaimStatus.PARTIALLY_SUPPORTED
        else:
            result.status = ClaimStatus.UNSUPPORTED

        # Generate summary
        result.summary = self._generate_summary(result)

    def _generate_summary(self, result: ResearchResult) -> str:
        """Generate a narrative summary of research findings."""
        parts = []
        if result.power_win_facts:
            parts.append(f"Found {len(result.power_win_facts)} Power.win facts")
        if result.external_facts:
            parts.append(f"{len(result.external_facts)} external facts")
        if result.unsupported_claims:
            parts.append(f"{len(result.unsupported_claims)} unsupported claims")
        if result.conflicting_information:
            parts.append(f"{len(result.conflicting_information)} conflicts")
        if result.research_gaps:
            parts.append(f"{len(result.research_gaps)} research gaps")

        return "; ".join(parts) if parts else "No findings"

    def _parse_plan_response(self, topic: str, response: str) -> ResearchPlan:
        """Parse the LLM response into a ResearchPlan object."""
        try:
            data = json.loads(response.strip())
        except json.JSONDecodeError:
            return ResearchPlan(topic=topic)

        questions = []
        for q_data in data.get("questions", []):
            source_types = []
            for st in q_data.get("required_source_types", []):
                try:
                    source_types.append(SourceType(st))
                except ValueError:
                    source_types.append(SourceType.UNKNOWN)

            questions.append(
                ResearchQuestion(
                    question=q_data.get("question", ""),
                    priority=q_data.get("priority", "medium"),
                    required_source_types=source_types,
                    is_power_win_check=q_data.get("is_power_win_check", False),
                    notes=q_data.get("notes"),
                )
            )

        return ResearchPlan(
            topic=topic,
            questions=questions,
            required_power_win_checks=data.get("required_power_win_checks", []),
            required_external_checks=data.get("required_external_checks", []),
            claims_to_verify=data.get("claims_to_verify", []),
        )

    def close(self) -> None:
        """Close underlying HTTP clients."""
        self.search_tool.close()
        self.fetcher.close()
        self.sitemap_fetcher.close()

    def __enter__(self) -> "Researcher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()