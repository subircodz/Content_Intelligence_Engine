import json
from unittest.mock import Mock

from intelligence_content_engine.research.models import Claim, ClaimStatus, Evidence, ResearchResult, Source, SourceType
from intelligence_content_engine.strategy.models import AIOStrategy, ContentBrief, GEOStrategy, SEOStrategy
from intelligence_content_engine.strategy.strategist import ContentStrategist


def test_strategy_models_are_domain_independent():
    brief = ContentBrief(
        topic="Example topic",
        seo=SEOStrategy(primary_topic="Example topic", search_intent="informational", primary_keyword="example", recommended_title="Example"),
        aio=AIOStrategy(entities=["Example Entity"]),
        geo=GEOStrategy(first_party_facts=["Verified target-site fact"]),
    )
    assert brief.get_all_required_entities() == ["Example Entity"]
    assert "Verified target-site fact" in brief.get_all_recommended_facts()


def test_strategist_generates_three_sections():
    responses = [
        json.dumps({"primary_topic": "Topic", "search_intent": "informational", "primary_keyword": "topic", "recommended_title": "Topic"}),
        json.dumps({"direct_answer_questions": ["What is it?"]}),
        json.dumps({"important_entities": ["Entity"], "first_party_facts": ["Fact"]}),
    ]
    llm = Mock()
    llm.generate.side_effect = responses
    strategist = ContentStrategist(llm)
    result = ResearchResult(topic="Topic")
    source = Source(name="Target", source_type=SourceType.FIRST_PARTY)
    result.add_first_party_fact(Claim(text="Fact", status=ClaimStatus.VERIFIED, evidence=[Evidence(source=source, excerpt="Fact")]))

    brief, status = strategist.create_brief("Topic", result)
    assert brief.seo.primary_keyword == "topic"
    assert brief.aio.direct_answer_questions == ["What is it?"]
    assert brief.geo.important_entities == ["Entity"]
    assert status.value == "success"
