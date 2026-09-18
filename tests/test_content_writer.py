from unittest.mock import Mock

from intelligence_content_engine.agents.content_writer import ContentWriterAgent
from intelligence_content_engine.language import ContentLanguage
from intelligence_content_engine.llm.client import LLMClient
from intelligence_content_engine.strategy.models import AIOStrategy, ContentBrief, GEOStrategy, SEOStrategy


def test_content_writer_generates_article_from_brief():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.return_value = "# Generated Article\n\nArticle body."
    writer = ContentWriterAgent(llm_client=mock_llm)

    brief = ContentBrief(
        topic="Example topic",
        seo=SEOStrategy(
            primary_topic="Example topic",
            search_intent="informational",
            primary_keyword="example",
            recommended_title="Example topic",
        ),
        aio=AIOStrategy(important_factual_statements=["Verified fact"]),
        geo=GEOStrategy(first_party_facts=["Target-site fact"]),
    )

    assert writer.generate(brief) == "# Generated Article\n\nArticle body."
    prompt = mock_llm.generate.call_args[0][0]
    assert "Requested Article Title: Example topic" in prompt
    assert "Verified fact" in prompt
    assert "Do NOT invent facts" in prompt


def test_content_writer_includes_requested_language():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.return_value = "# Generated Article"
    writer = ContentWriterAgent(llm_client=mock_llm, language=ContentLanguage.TELUGU)

    brief = ContentBrief(
        topic="వాతావరణ మార్పు",
        seo=SEOStrategy(
            primary_topic="వాతావరణ మార్పు",
            search_intent="informational",
            primary_keyword="వాతావరణ మార్పు",
            recommended_title="వాతావరణ మార్పు",
        ),
        aio=AIOStrategy(),
        geo=GEOStrategy(),
    )

    writer.generate(brief)
    prompt = mock_llm.generate.call_args[0][0]
    assert "OUTPUT LANGUAGE: Telugu" in prompt
    assert "complete article in Telugu" in prompt


def test_content_writer_handles_empty_llm_response():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.return_value = ""
    writer = ContentWriterAgent(llm_client=mock_llm)
    brief = ContentBrief(
        topic="Test",
        seo=SEOStrategy(
            primary_topic="Test",
            search_intent="informational",
            primary_keyword="test",
            recommended_title="Test",
        ),
        aio=AIOStrategy(),
        geo=GEOStrategy(),
    )
    assert writer.generate(brief) == ""
