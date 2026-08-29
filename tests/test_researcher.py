from unittest.mock import Mock

from power_win_content.research.models import PhaseStatus, ResearchResult, SourceType
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
