import logging
import time
from typing import Union

import httpx

from power_win_content.llm.client import LLMClient
from power_win_content.strategy.models import ContentBrief

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_RETRY_DELAYS = [1.0, 2.0]


def _is_transient_error(exc: Exception) -> bool:
    """Return True if the exception represents a transient, retryable failure."""
    # Timeout / connection-level errors are always transient
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True

    # HTTP status-code errors: retry only on 429 and 5xx
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)

    return False


class ContentWriterAgent:
    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def generate(self, brief: Union[ContentBrief, str]) -> str:
        if isinstance(brief, str):
            prompt = self._build_legacy_prompt(brief)
        else:
            prompt = self._build_brief_prompt(brief)

        for attempt in range(_MAX_RETRIES + 1):
            try:
                result = self.llm_client.generate(prompt)

                if result and result.strip():
                    return result

                # Empty / whitespace-only response is a transient failure
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_DELAYS[attempt]
                    logger.debug(
                        "Writing LLM returned empty content (attempt %d/%d). Retrying in %.0fs...",
                        attempt + 1, _MAX_RETRIES + 1, delay,
                    )
                    time.sleep(delay)
                else:
                    logger.debug(
                        "Writing LLM returned empty content after %d attempts.",
                        _MAX_RETRIES + 1,
                    )
                    return ""

            except Exception as exc:
                if _is_transient_error(exc) and attempt < _MAX_RETRIES:
                    delay = _RETRY_DELAYS[attempt]
                    logger.debug(
                        "Writing LLM request failed (attempt %d/%d): %s. Retrying in %.0fs...",
                        attempt + 1, _MAX_RETRIES + 1, exc, delay,
                    )
                    time.sleep(delay)
                else:
                    raise

        return ""

    def _build_legacy_prompt(self, title: str) -> str:
        return (
            "Write an original article based on the following title:\n\n"
            f"Title: {title}\n\n"
            "Requirements:\n"
            "- Use natural, human-sounding language\n"
            "- Avoid generic AI-style wording\n"
            "- Use clear headings and subheadings\n"
            "- Provide useful information to real readers\n"
            "- Maintain a professional editorial tone\n"
            "- Avoid unsupported factual claims\n"
            "- Do not invent statistics, organisations, regulations, studies, or sources\n"
            "- Avoid keyword stuffing\n"
            "- Do not mention that AI was used to write the article\n"
        )

    def _build_brief_prompt(self, brief: ContentBrief) -> str:
        recommended_facts = brief.get_all_recommended_facts()
        required_entities = brief.get_all_required_entities()

        sections = [
            "You are a expert content writer for Power.win. Write a comprehensive, highly accurate article based on the provided strategy brief.\n",
            f"Requested Article Title: {brief.topic}",
            f"Primary Topic: {brief.seo.primary_topic}",
            f"Search Intent: {brief.seo.search_intent}",
            f"Primary Keyword: {brief.seo.primary_keyword}",
        ]

        if brief.seo.recommended_title and brief.seo.recommended_title != brief.topic:
            sections.append(f"SEO Recommended Alternative Title: {brief.seo.recommended_title}")

        if brief.seo.secondary_keywords:
            sections.append(f"Secondary Keywords: {', '.join(brief.seo.secondary_keywords)}")

        if brief.seo.recommended_headings:
            sections.append("\nRecommended Article Structure / Headings:")
            for h in brief.seo.recommended_headings:
                sections.append(f"  - {h}")

        if brief.seo.questions_to_answer:
            sections.append("\nQuestions That Must Be Answered:")
            for q in brief.seo.questions_to_answer:
                sections.append(f"  - {q}")

        if recommended_facts:
            sections.append("\nVerified Facts (Use these for accuracy):")
            for fact in recommended_facts:
                sections.append(f"  - {fact}")

        if brief.aio.concise_answers:
            sections.append("\nDirect Answer Definitions & Q&As:")
            for q, a in brief.aio.concise_answers.items():
                sections.append(f"  - Q: {q} | A: {a}")

        if brief.aio.definitions:
            for term, defn in brief.aio.definitions.items():
                sections.append(f"  - Term: {term} | Definition: {defn}")

        if required_entities:
            sections.append(f"\nKey Entities to Mention: {', '.join(required_entities)}")

        if brief.geo.authoritative_external_sources:
            sections.append(f"Authoritative External Sources: {', '.join(brief.geo.authoritative_external_sources)}")

        if brief.seo.internal_linking_opportunities:
            sections.append(f"Internal Linking Opportunities: {', '.join(brief.seo.internal_linking_opportunities)}")

        if brief.aio.structured_information_requirements:
            sections.append("\nStructured Content Requirements (tables/lists):")
            for req in brief.aio.structured_information_requirements:
                sections.append(f"  - {req}")

        competitor_gaps = getattr(brief, "competitor_gaps", None)
        if competitor_gaps:
            sections.append("\nCompetitor Content Gap Analysis (editorial planning input, NOT factual evidence):")
            if competitor_gaps.missing_topics:
                sections.append("Missing topics to consider: " + ", ".join(competitor_gaps.missing_topics[:10]))
            if competitor_gaps.missing_questions:
                sections.append("Missing questions to consider: " + ", ".join(competitor_gaps.missing_questions[:10]))
            if competitor_gaps.missing_entities:
                sections.append("Missing entities to consider: " + ", ".join(competitor_gaps.missing_entities[:10]))
            if competitor_gaps.missing_comparisons:
                sections.append("Missing comparisons: " + ", ".join(competitor_gaps.missing_comparisons[:10]))
            if competitor_gaps.missing_statistics:
                sections.append("Missing statistics/data needs verification: " + ", ".join(competitor_gaps.missing_statistics[:10]))
            if competitor_gaps.missing_user_concerns:
                sections.append("Missing user concerns: " + ", ".join(competitor_gaps.missing_user_concerns[:10]))
            if competitor_gaps.missing_angles:
                sections.append("Recommended angles: " + ", ".join(competitor_gaps.missing_angles[:10]))
            if competitor_gaps.competitor_topics_absent_from_ours:
                sections.append("Competitor topics absent from our plan: " + ", ".join(competitor_gaps.competitor_topics_absent_from_ours[:10]))
            sections.append(
                "- Use competitor gaps only to improve editorial coverage.\n"
                "- Do NOT copy competitor wording.\n"
                "- Do NOT fabricate facts simply because competitors mention something.\n"
                "- Any factual claim still needs evidence via the existing research system.\n"
                "- Competitor analysis is editorial planning input, NOT factual evidence."
            )

        sections.append(
            "\nStrict Writer Guidelines:\n"
            "- Do NOT invent facts, statistics, claims, URLs, regulations, or citations not backed by the research brief.\n"
            "- Write in clear, engaging, professional Markdown.\n"
            "- Follow the recommended heading structure closely.\n"
            "- Answer direct questions early and clearly for AI and search optimization.\n"
            "- Naturally incorporate the primary and secondary keywords without stuffing.\n"
            "- Maintain an authoritative, neutral editorial voice.\n"
            "- Do NOT mention that this article was created by AI or based on a prompt."
        )

        return "\n".join(sections)
