from unittest.mock import Mock

from power_win_content.agents.content_writer import ContentWriterAgent
from power_win_content.config import Settings
from power_win_content.llm.client import LLMClient
from power_win_content.strategy.models import AIOStrategy, ContentBrief, GEOStrategy, SEOStrategy


def test_content_writer_generates_article_legacy_string() -> None:
    settings = Settings()

    llm = LLMClient(
        base_url=settings.omniroute_base_url,
        model=settings.omniroute_model,
    )

    writer = ContentWriterAgent(llm_client=llm)

    response = writer.generate("How to Grow Tomatoes in Containers")

    assert isinstance(response, str)
    assert len(response.strip()) > 0


def test_content_writer_generates_article_from_brief() -> None:
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.return_value = "# Generated Article\n\nArticle body based on brief."

    writer = ContentWriterAgent(llm_client=mock_llm)

    seo = SEOStrategy(
        primary_topic="Casino Review Methodology",
        search_intent="informational",
        primary_keyword="Power.win casino review process",
        secondary_keywords=["crypto casino rating", "license check"],
        recommended_title="How Power.win Reviews Online Casinos",
        recommended_headings=["Introduction", "Licensing Verification", "Rating Scale"],
        questions_to_answer=["How are casinos scored?", "What licenses are verified?"],
        internal_linking_opportunities=["https://power.win/methodology"],
    )
    aio = AIOStrategy(
        important_factual_statements=["Power.win checks licenses with UKGC and MGA"],
        concise_answers={"How are casinos scored?": "Power.win uses letter grades A through F."},
        definitions={"Letter Grade": "Overall score assigned from A to F"},
    )
    geo = GEOStrategy(
        important_entities=["Power.win", "UKGC"],
        power_win_first_party_facts=["Power.win uses proprietary letter grade scale"],
        authoritative_external_sources=["Malta Gaming Authority"],
    )

    brief = ContentBrief(
        topic="Casino Review Methodology",
        seo=seo,
        aio=aio,
        geo=geo,
    )

    article = writer.generate(brief)

    assert article == "# Generated Article\n\nArticle body based on brief."

    mock_llm.generate.assert_called_once()
    prompt = mock_llm.generate.call_args[0][0]

    assert "Requested Article Title: Casino Review Methodology" in prompt
    assert "SEO Recommended Alternative Title: How Power.win Reviews Online Casinos" in prompt
    assert "Power.win casino review process" in prompt
    assert "Licensing Verification" in prompt
    assert "Power.win checks licenses with UKGC and MGA" in prompt
    assert "Do NOT invent facts" in prompt


def test_content_writer_handles_empty_llm_response() -> None:
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.return_value = ""

    writer = ContentWriterAgent(llm_client=mock_llm)

    seo = SEOStrategy(primary_topic="Test", search_intent="informational", primary_keyword="test", recommended_title="Test")
    brief = ContentBrief(topic="Test", seo=seo, aio=AIOStrategy(), geo=GEOStrategy())

    article = writer.generate(brief)

    assert article == ""