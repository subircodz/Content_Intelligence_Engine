import hashlib
from unittest.mock import Mock

from power_win_content.research.models import PhaseStatus, ResearchResult, Source, SourceType
from power_win_content.research.researcher import Researcher


def test_fallback_plan_is_domain_independent():
    llm = Mock()
    llm.generate.side_effect = RuntimeError("planning unavailable")
    researcher = Researcher(llm_client=llm, search_tool=Mock(), fetcher=Mock(), sitemap_fetcher=Mock())

    plan = researcher.create_plan("Example topic")
    assert plan.topic == "Example topic"
    assert plan.required_first_party_checks
    assert plan.questions[0].is_first_party_check is True


def test_empty_plan_response_uses_fallback():
    llm = Mock()
    llm.generate.return_value = '{"questions": [], "required_first_party_checks": [], "required_external_checks": []}'
    researcher = Researcher(llm_client=llm, search_tool=Mock(), fetcher=Mock(), sitemap_fetcher=Mock())

    plan = researcher.create_plan("Example topic")
    assert plan.questions


def test_source_type_first_party_is_generic():
    assert SourceType.FIRST_PARTY.value == "first_party"


def test_claim_excerpt_must_exist_in_retrieved_content():
    researcher = Researcher(llm_client=Mock(), search_tool=Mock(), fetcher=Mock(), sitemap_fetcher=Mock())
    source = Source(name="Example", url="https://example.com", source_type=SourceType.PRIMARY)
    content = "The source says the withdrawal takes three days."
    evidence_list = [(source, content, "withdrawal timing", False, "http")]

    rejected = researcher._parse_batch_claim(
        {
            "text": "The withdrawal takes one day.",
            "status": "verified",
            "nature": "fact",
            "source_index": 1,
            "excerpt": "The withdrawal takes one day.",
            "confidence": 0.9,
        },
        evidence_list,
    )
    assert rejected is None

    accepted_excerpt = "The source says the withdrawal takes three days."
    accepted = researcher._parse_batch_claim(
        {
            "text": "The withdrawal takes three days.",
            "status": "verified",
            "nature": "fact",
            "source_index": 1,
            "excerpt": accepted_excerpt,
            "confidence": 0.9,
        },
        evidence_list,
    )
    assert accepted is not None
    assert accepted.evidence[0].excerpt_verified is True
    assert accepted.evidence[0].content_sha256 == hashlib.sha256(content.encode("utf-8")).hexdigest()
