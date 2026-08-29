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
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


class ContentWriterAgent:
    """Generate article drafts from a domain-independent content brief."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def generate(self, brief: Union[ContentBrief, str]) -> str:
        prompt = self._build_legacy_prompt(brief) if isinstance(brief, str) else self._build_brief_prompt(brief)
        for attempt in range(_MAX_RETRIES + 1):
            try:
                result = self.llm_client.generate(prompt)
                if result and result.strip():
                    return result
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAYS[attempt])
                else:
                    return ""
            except Exception as exc:
                if _is_transient_error(exc) and attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAYS[attempt])
                    continue
                raise
        return ""

    def _build_legacy_prompt(self, title: str) -> str:
        return (
            "Write an original article based on the following title:\n\n"
            f"Title: {title}\n\n"
            "Requirements:\n"
            "- Use natural, human-sounding language\n"
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
            "You are an expert content writer. Write a comprehensive, accurate article based on the provided strategy brief.\n",
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
            sections.extend(f"  - {heading}" for heading in brief.seo.recommended_headings)
        if brief.seo.questions_to_answer:
            sections.append("\nQuestions That Must Be Answered:")
            sections.extend(f"  - {question}" for question in brief.seo.questions_to_answer)
        if recommended_facts:
            sections.append("\nVerified Facts (Use these for accuracy):")
            sections.extend(f"  - {fact}" for fact in recommended_facts)
        if brief.aio.concise_answers:
            sections.append("\nDirect Answers:")
            sections.extend(f"  - Q: {question} | A: {answer}" for question, answer in brief.aio.concise_answers.items())
        if brief.aio.definitions:
            sections.append("\nDefinitions:")
            sections.extend(f"  - {term}: {definition}" for term, definition in brief.aio.definitions.items())
        if required_entities:
            sections.append(f"\nKey Entities to Mention: {', '.join(required_entities)}")
        if brief.geo.authoritative_external_sources:
            sections.append(f"Authoritative External Sources: {', '.join(brief.geo.authoritative_external_sources)}")
        if brief.seo.internal_linking_opportunities:
            sections.append(f"Internal Linking Opportunities: {', '.join(brief.seo.internal_linking_opportunities)}")

        gaps = brief.competitor_gaps
        if gaps:
            sections.append("\nCompetitor Content Opportunities (editorial planning input, NOT factual evidence):")
            if gaps.missing_topics:
                sections.append("Missing topics: " + ", ".join(gaps.missing_topics[:10]))
            if gaps.missing_questions:
                sections.append("Missing questions: " + ", ".join(gaps.missing_questions[:10]))
            if gaps.missing_entities:
                sections.append("Missing entities: " + ", ".join(gaps.missing_entities[:10]))
            if gaps.missing_comparisons:
                sections.append("Missing comparisons: " + ", ".join(gaps.missing_comparisons[:10]))
            if gaps.missing_angles:
                sections.append("Recommended angles: " + ", ".join(gaps.missing_angles[:10]))

        sections.append(
            "\nStrict Writer Guidelines:\n"
            "- Do NOT invent facts, statistics, claims, URLs, regulations, or citations not backed by the research brief.\n"
            "- Write clear, engaging, professional Markdown.\n"
            "- Follow the recommended heading structure closely.\n"
            "- Answer direct questions early and clearly for AI and search optimization.\n"
            "- Naturally incorporate keywords without stuffing.\n"
            "- Maintain an authoritative, neutral editorial voice.\n"
            "- Do NOT mention that this article was created by AI or based on a prompt."
        )
        return "\n".join(sections)
