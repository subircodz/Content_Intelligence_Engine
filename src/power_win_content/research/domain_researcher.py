"""Domain-independent research facade."""

from urllib.parse import urlparse

from power_win_content.client import ClientConfig
from power_win_content.research.models import ResearchPlan, ResearchQuestion, Source, SourceType
from power_win_content.research.researcher import Researcher


class DomainResearcher(Researcher):
    """Researcher configured for an arbitrary target domain."""

    def __init__(self, llm_client, client_config: ClientConfig, **kwargs):
        self.client_config = client_config
        super().__init__(llm_client=llm_client, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        close = getattr(self.fetcher, "close", None)
        if callable(close):
            close()
        return False

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
            required_first_party_checks=[f"{self.client_config.name} first-party information relevant to {topic}"],
            required_external_checks=[f"authoritative external context for {topic}"],
            claims_to_verify=[topic],
        )

    def _build_plan_prompt(self, topic: str) -> str:
        return (
            "You are a research planner for a domain-independent content intelligence engine.\n\n"
            f"Target brand: {self.client_config.name}\nTarget domain: {self.client_config.domain}\nTopic: {topic}\n\n"
            "Return ONLY valid JSON with questions, required_first_party_checks, required_external_checks, and claims_to_verify. "
            "Use is_first_party_check=true only for target-site first-party verification. Do not assume any particular industry."
        )

    def _filter_sources_by_question(self, sources: list[Source], question: ResearchQuestion) -> list[Source]:
        def priority(source: Source) -> int:
            host = urlparse(str(source.url)).hostname or ""
            host = host.lower().removeprefix("www.")
            if host in self.client_config.first_party_domains:
                return 1
            if host.endswith(f".{self.client_config.domain}"):
                return 2
            return 3
        return sorted(sources, key=priority)

    def _build_extraction_prompt(self, content, source, question, is_first_party):
        source_type = source.source_type.value if hasattr(source.source_type, "value") else source.source_type
        return (
            "Extract verifiable claims from the supplied source content.\n\n"
            f"Target brand: {self.client_config.name}\nTarget domain: {self.client_config.domain}\n"
            f"Source: {source.name} ({source.url})\nSource Type: {source_type}\n"
            f"Research Question: {question}\nIs Target First-Party Check: {is_first_party}\n\n"
            f"Source Content (truncated):\n{content[:8000]}\n\n"
            "Return ONLY JSON containing a claims array. Every excerpt MUST be an exact quote from the supplied source content."
        )

    def _build_batch_analysis_prompt(self, evidence_list, question, is_first_party):
        blocks = []
        for i, (source, content, _, _, _) in enumerate(evidence_list, start=1):
            source_type = source.source_type.value if hasattr(source.source_type, "value") else source.source_type
            blocks.append(f"SOURCE {i}:\nName: {source.name}\nURL: {source.url}\nType: {source_type}\nContent:\n{content[:5000]}\n")
        return (
            "Analyze multiple sources to extract verifiable claims.\n\n"
            f"Target brand: {self.client_config.name}\nTarget domain: {self.client_config.domain}\n"
            f"Research Question: {question}\nTarget First-Party Check: {is_first_party}\n\n"
            + "\n".join(blocks)
            + "\nReturn ONLY JSON with a claims array. Each claim must contain text, status, nature, source_index (1-based), exact excerpt, confidence, and notes."
        )

    def _generate_summary(self, result):
        parts = []
        if result.first_party_facts:
            parts.append(f"Found {len(result.first_party_facts)} first-party facts")
        if result.external_facts:
            parts.append(f"{len(result.external_facts)} external facts")
        if result.unsupported_claims:
            parts.append(f"{len(result.unsupported_claims)} unsupported claims")
        if result.conflicting_information:
            parts.append(f"{len(result.conflicting_information)} conflicts")
        if result.research_gaps:
            parts.append(f"{len(result.research_gaps)} research gaps")
        return "; ".join(parts) if parts else "No findings"
