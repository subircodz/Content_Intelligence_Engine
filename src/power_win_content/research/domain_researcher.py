"""Domain-independent research facade.

This adapter keeps the existing research machinery while supplying target-site
configuration and removing client-specific language from prompts. It is the
transition point while the underlying research implementation is being cleaned
up further.
"""

from power_win_content.client import ClientConfig
from power_win_content.research.models import (
    ResearchPlan, ResearchQuestion, SourceType
)
from power_win_content.research.researcher import Researcher


class DomainResearcher(Researcher):
    """Researcher configured for an arbitrary target domain."""

    def __init__(self, llm_client, client_config: ClientConfig, **kwargs):
        self.client_config = client_config
        super().__init__(llm_client=llm_client, **kwargs)

    def _build_fallback_plan(self, topic: str) -> ResearchPlan:
        return ResearchPlan(
            topic=topic,
            questions=[
                ResearchQuestion(
                    question=f"What factual information can be verified about: {topic}?",
                    priority="critical",
                    is_power_win_check=True,
                    required_source_types=[SourceType.FIRST_PARTY],
                    notes="Fallback first-party research question.",
                ),
                ResearchQuestion(
                    question=f"What authoritative external context is relevant to: {topic}?",
                    priority="high",
                    is_power_win_check=False,
                    required_source_types=[SourceType.REGULATORY, SourceType.AUTHORITATIVE, SourceType.PRIMARY],
                    notes="Fallback external research question.",
                ),
            ],
            required_power_win_checks=[f"{self.client_config.name} first-party information relevant to {topic}"],
            required_external_checks=[f"authoritative external context for {topic}"],
            claims_to_verify=[topic],
        )

    def _build_plan_prompt(self, topic: str) -> str:
        return (
            "You are a research planner for a content intelligence engine. Create a research plan "
            "for the following topic and target site.\n\n"
            f"Target brand: {self.client_config.name}\n"
            f"Target domain: {self.client_config.domain}\n"
            f"Topic: {topic}\n\n"
            "Return ONLY valid JSON with questions, required_first_party_checks, "
            "required_external_checks, and claims_to_verify. Each question must contain "
            "question, priority, required_source_types, is_power_win_check, and notes. "
            "Use is_power_win_check=true only to mean that the answer should be verified "
            "against the configured target site's first-party sources.\n"
            "Include first-party checks when the target site can substantiate the topic, "
            "and authoritative external checks where appropriate. Do not assume any specific industry."
        )

    def _build_extraction_prompt(self, content, source, question, is_power_win):
        source_type = source.source_type.value if hasattr(source.source_type, "value") else source.source_type
        return (
            "You are a research assistant extracting verifiable claims from source content.\n\n"
            f"Target brand: {self.client_config.name}\n"
            f"Target domain: {self.client_config.domain}\n"
            f"Source: {source.name} ({source.url})\n"
            f"Source Type: {source_type}\n"
            f"Research Question: {question}\n"
            f"Is Target First-Party Check: {is_power_win}\n\n"
            f"Source Content (truncated):\n{content[:8000]}\n\n"
            "Return ONLY JSON containing a claims array. Every excerpt must be an exact quote "
            "from the supplied source content. Extract only claims directly supported by that content."
        )

    def _build_batch_analysis_prompt(self, evidence_list, question, is_power_win):
        blocks = []
        for i, (source, content, _, _, _) in enumerate(evidence_list, start=1):
            source_type = source.source_type.value if hasattr(source.source_type, "value") else source.source_type
            blocks.append(
                f"SOURCE {i}:\nName: {source.name}\nURL: {source.url}\nType: {source_type}\n"
                f"Content:\n{content[:5000]}\n"
            )
        return (
            "You are a research assistant analyzing multiple sources.\n\n"
            f"Target brand: {self.client_config.name}\n"
            f"Target domain: {self.client_config.domain}\n"
            f"Research Question: {question}\n"
            f"Is Target First-Party Check: {is_power_win}\n\n"
            + "\n".join(blocks)
            + "\nReturn ONLY JSON with a claims array. Each claim must contain text, status, nature, "
            "source_index (1-based), exact excerpt from that source, confidence, and notes. "
            "Never invent facts or excerpts."
        )

    def _generate_summary(self, result):
        parts = []
        if result.power_win_facts:
            parts.append(f"Found {len(result.power_win_facts)} first-party facts")
        if result.external_facts:
            parts.append(f"{len(result.external_facts)} external facts")
        if result.unsupported_claims:
            parts.append(f"{len(result.unsupported_claims)} unsupported claims")
        if result.conflicting_information:
            parts.append(f"{len(result.conflicting_information)} conflicts")
        if result.research_gaps:
            parts.append(f"{len(result.research_gaps)} research gaps")
        return "; ".join(parts) if parts else "No findings"
