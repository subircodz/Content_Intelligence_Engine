"""
Unit tests for the Content Strategy layer (SEO, AIO, GEO).
"""

import json
from unittest.mock import Mock, patch

from power_win_content.llm.client import LLMClient
from power_win_content.research.models import (
    Claim,
    ClaimStatus,
    Evidence,
    InformationNature,
    ResearchGap,
    ResearchQuestion,
    ResearchResult,
    ResearchPlan,
    Source,
    SourceType,
)
from power_win_content.strategy.models import AIOStrategy, ContentBrief, GEOStrategy, SEOStrategy
from power_win_content.strategy.strategist import ContentStrategist


def make_source(name: str, url: str, source_type: SourceType) -> Source:
    return Source(name=name, url=url, source_type=source_type)


def make_evidence(source: Source, excerpt: str) -> Evidence:
    return Evidence(source=source, excerpt=excerpt)


def make_claim(
    text: str,
    status: ClaimStatus = ClaimStatus.VERIFIED,
    nature: InformationNature = InformationNature.FACT,
    confidence: float = 0.9,
    evidence: list[Evidence] = None,
) -> Claim:
    return Claim(
        text=text,
        status=status,
        nature=nature,
        confidence=confidence,
        evidence=evidence or [],
    )


def make_power_win_fact(text: str, source_name: str = "Power.win") -> Claim:
    source = make_source(source_name, f"https://power.win/{source_name.lower().replace(' ', '-')}", SourceType.FIRST_PARTY)
    return make_claim(text, evidence=[make_evidence(source, f"Excerpt for {text}")])


def make_external_fact(text: str, source_name: str = "UKGC") -> Claim:
    source = make_source(source_name, f"https://{source_name.lower()}.gov.uk", SourceType.REGULATORY)
    return make_claim(text, evidence=[make_evidence(source, f"Excerpt for {text}")])


def make_unsupported_claim(text: str) -> Claim:
    return make_claim(text, status=ClaimStatus.UNSUPPORTED, confidence=0.1, evidence=[])


class TestStrategyModels:
    """Test ContentBrief and strategy model validation."""

    def test_seo_strategy_creation_valid(self) -> None:
        seo = SEOStrategy(
            primary_topic="Power.win Casino Reviews",
            search_intent="informational",
            primary_keyword="Power.win casino reviews",
            secondary_keywords=["online casino reviews", "casino ratings"],
            recommended_title="Power.win Casino Reviews: Complete Guide 2024",
            recommended_headings=["How We Review", "Top Casinos", "Methodology"],
            questions_to_answer=["How does Power.win rate casinos?", "What criteria are used?"],
            internal_linking_opportunities=["https://power.win/casino", "https://power.win/methodology"],
            semantic_coverage_requirements=["review methodology", "bonus terms", "licensing"],
        )
        assert seo.primary_topic == "Power.win Casino Reviews"
        assert seo.search_intent == "informational"
        assert len(seo.secondary_keywords) == 2

    def test_aio_strategy_creation_valid(self) -> None:
        aio = AIOStrategy(
            direct_answer_questions=["What is Power.win?", "How does Power.win verify licenses?"],
            concise_answers={
                "What is Power.win?": "Power.win is a crypto casino review platform.",
                "How does Power.win verify licenses?": "Power.win checks all casino licenses with regulators.",
            },
            definitions={"crypto casino": "An online casino accepting cryptocurrency"},
            important_factual_statements=["Power.win verifies all licenses", "Power.win uses letter grades A-F"],
            entities=["Power.win", "UKGC", "MGA"],
            evidence_requirements=["regulator license numbers", "review methodology documentation"],
            structured_information_requirements=["comparison table", "rating scale explanation"],
        )
        assert len(aio.direct_answer_questions) == 2
        assert len(aio.concise_answers) == 2
        assert len(aio.definitions) == 1

    def test_geo_strategy_creation_valid(self) -> None:
        geo = GEOStrategy(
            important_entities=["Power.win", "online casinos", "crypto gambling"],
            entity_relationships=["Power.win reviews online casinos", "Power.win verifies licenses"],
            authoritative_external_sources=["UK Gambling Commission", "Malta Gaming Authority"],
            power_win_first_party_facts=["Power.win uses letter grades A-F", "Power.win checks all licenses"],
            unique_information=["Power.win's proprietary 10-point verification process"],
            citation_evidence_opportunities=["license verification claims", "review methodology"],
            factual_consistency_requirements=["must match published methodology", "license status must be current"],
            questions_to_answer_clearly=["What is Power.win's review process?", "How are casinos rated?"],
        )
        assert len(geo.important_entities) == 3
        assert len(geo.power_win_first_party_facts) == 2
        assert len(geo.unique_information) == 1

    def test_content_brief_creation_valid(self) -> None:
        seo = SEOStrategy(
            primary_topic="Test Topic",
            search_intent="informational",
            primary_keyword="test keyword",
            recommended_title="Test Title",
        )
        aio = AIOStrategy()
        geo = GEOStrategy()

        brief = ContentBrief(
            topic="Test Topic",
            seo=seo,
            aio=aio,
            geo=geo,
            total_verified_facts=5,
            total_power_win_facts=3,
            total_external_facts=2,
            research_gaps_count=1,
            unsupported_claims_count=2,
            conflicts_count=0,
        )
        assert brief.topic == "Test Topic"
        assert brief.total_verified_facts == 5
        assert brief.get_all_recommended_facts() == []

    def test_content_brief_helper_methods(self) -> None:
        seo = SEOStrategy(
            primary_topic="Test Topic",
            search_intent="informational",
            primary_keyword="test keyword",
            recommended_title="Test Title",
        )
        aio = AIOStrategy(
            important_factual_statements=["Fact 1", "Fact 2"],
            entities=["Entity 1", "Entity 2"],
        )
        geo = GEOStrategy(
            power_win_first_party_facts=["PW Fact 1"],
            unique_information=["Unique 1"],
            important_entities=["Geo Entity 1"],
        )

        brief = ContentBrief(
            topic="Test Topic",
            seo=seo,
            aio=aio,
            geo=geo,
        )

        facts = brief.get_all_recommended_facts()
        assert "Fact 1" in facts
        assert "Fact 2" in facts
        assert "PW Fact 1" in facts
        assert "Unique 1" in facts

        entities = brief.get_all_required_entities()
        assert "Entity 1" in entities
        assert "Entity 2" in entities
        assert "Geo Entity 1" in entities


class TestContentStrategist:
    """Test ContentStrategist class."""

    def create_mock_llm(self, responses: list[str]) -> Mock:
        """Create a mock LLM client with sequential responses."""
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = responses
        return mock_llm

    def create_sample_research(self) -> ResearchResult:
        """Create a sample ResearchResult with mixed claims."""
        pw_fact = make_power_win_fact("Power.win uses letter grades A-F for casino ratings")
        pw_fact2 = make_power_win_fact("Power.win verifies all casino licenses with regulators")
        ext_fact = make_external_fact("UKGC requires all operators to hold a valid license")
        unsupported = make_unsupported_claim("Power.win is the best review site")

        plan = ResearchPlan(
            topic="Power.win Editorial Methodology",
            questions=[
                ResearchQuestion(
                    question="What is Power.win's review methodology?",
                    priority="critical",
                    required_source_types=[SourceType.FIRST_PARTY],
                    is_power_win_check=True,
                )
            ],
        )

        result = ResearchResult(
            topic="Power.win Editorial Methodology",
            plan=plan,
            questions=plan.questions,
            power_win_facts=[pw_fact, pw_fact2],
            external_facts=[ext_fact],
            unsupported_claims=[unsupported],
            research_gaps=[
                ResearchGap(
                    question="Exact scoring algorithm",
                    reason="Not publicly disclosed",
                    attempted_sources=["power.win/methodology"],
                    importance="high",
                )
            ],
            conflicting_information=[],
        )
        return result

    def test_create_brief_basic(self) -> None:
        """Test basic ContentBrief creation."""
        mock_llm = self.create_mock_llm([
            # SEO response
            json.dumps({
                "primary_topic": "Power.win Editorial Methodology",
                "search_intent": "informational",
                "primary_keyword": "Power.win editorial methodology",
                "secondary_keywords": ["casino review methodology", "online casino ratings"],
                "recommended_title": "Power.win Editorial Methodology: How We Review Casinos",
                "recommended_headings": ["Our Review Process", "Rating Criteria", "License Verification"],
                "questions_to_answer": ["How does Power.win review casinos?", "What criteria are used?"],
                "internal_linking_opportunities": ["https://power.win/casino", "https://power.win/methodology"],
                "semantic_coverage_requirements": ["review methodology", "license verification", "rating system"],
            }),
            # AIO response
            json.dumps({
                "direct_answer_questions": ["What is Power.win's review methodology?", "How are casinos rated?"],
                "concise_answers": {
                    "What is Power.win's review methodology?": "Power.win uses letter grades A-F based on license verification, game fairness, and bonus terms.",
                    "How are casinos rated?": "Casinos receive letter grades A-F based on a weighted scoring system."
                },
                "definitions": {"letter grade": "A-F rating indicating overall casino quality"},
                "important_factual_statements": [
                    "Power.win uses letter grades A-F for casino ratings",
                    "Power.win verifies all casino licenses with regulators"
                ],
                "entities": ["Power.win", "UKGC", "MGA", "online casinos"],
                "evidence_requirements": ["regulator license numbers", "review methodology documentation"],
                "structured_information_requirements": ["rating scale table", "criteria breakdown"],
            }),
            # GEO response
            json.dumps({
                "important_entities": ["Power.win", "online casinos", "casino licenses"],
                "entity_relationships": ["Power.win reviews online casinos", "Power.win verifies casino licenses"],
                "authoritative_external_sources": ["UK Gambling Commission", "Malta Gaming Authority"],
                "power_win_first_party_facts": [
                    "Power.win uses letter grades A-F for casino ratings",
                    "Power.win verifies all casino licenses with regulators"
                ],
                "unique_information": ["Power.win's proprietary letter grade system A-F"],
                "citation_evidence_opportunities": ["license verification claims", "rating methodology"],
                "factual_consistency_requirements": ["must match published methodology on power.win", "license status must be current"],
                "questions_to_answer_clearly": ["What is Power.win's review process?", "How are letter grades assigned?"],
            }),
        ])

        strategist = ContentStrategist(llm_client=mock_llm)
        research = self.create_sample_research()

        brief, _ = strategist.create_brief("Power.win Editorial Methodology", research)

        assert isinstance(brief, ContentBrief)
        assert brief.topic == "Power.win Editorial Methodology"
        assert brief.total_verified_facts == 3  # 2 pw + 1 ext
        assert brief.total_power_win_facts == 2
        assert brief.total_external_facts == 1
        assert brief.research_gaps_count == 1
        assert brief.unsupported_claims_count == 1
        assert brief.conflicts_count == 0

    def test_brief_includes_verified_facts_only(self) -> None:
        """Test that only verified facts appear in strategy, not unsupported claims."""
        mock_llm = self.create_mock_llm([
            json.dumps({"primary_topic": "Test", "search_intent": "informational", "primary_keyword": "test"}),
            json.dumps({
                "direct_answer_questions": [],
                "concise_answers": {},
                "definitions": {},
                "important_factual_statements": [
                    "Power.win uses letter grades A-F",
                    "UKGC requires valid licenses"
                ],
                "entities": [],
                "evidence_requirements": [],
                "structured_information_requirements": [],
            }),
            json.dumps({
                "important_entities": [],
                "entity_relationships": [],
                "authoritative_external_sources": [],
                "power_win_first_party_facts": ["Power.win uses letter grades A-F"],
                "unique_information": [],
                "citation_evidence_opportunities": [],
                "factual_consistency_requirements": [],
                "questions_to_answer_clearly": [],
            }),
        ])

        strategist = ContentStrategist(llm_client=mock_llm)
        research = self.create_sample_research()

        brief, _ = strategist.create_brief("Test Topic", research)

        # Verify unsupported claim is NOT in important_factual_statements
        unsupported_text = "Power.win is the best review site"
        for fact in brief.aio.important_factual_statements:
            assert unsupported_text not in fact

        # Power.win first party facts should be in GEO
        assert any("letter grades A-F" in f for f in brief.geo.power_win_first_party_facts)

    def test_power_win_facts_distinguishable_from_external(self) -> None:
        """Test that Power.win facts remain separate from external facts in GEO."""
        mock_llm = self.create_mock_llm([
            json.dumps({"primary_topic": "Test", "search_intent": "informational", "primary_keyword": "test"}),
            json.dumps({
                "direct_answer_questions": [],
                "concise_answers": {},
                "definitions": {},
                "important_factual_statements": [],
                "entities": [],
                "evidence_requirements": [],
                "structured_information_requirements": [],
            }),
            json.dumps({
                "important_entities": [],
                "entity_relationships": [],
                "authoritative_external_sources": ["UK Gambling Commission"],
                "power_win_first_party_facts": ["Power.win uses letter grades A-F"],
                "unique_information": [],
                "citation_evidence_opportunities": [],
                "factual_consistency_requirements": [],
                "questions_to_answer_clearly": [],
            }),
        ])

        strategist = ContentStrategist(llm_client=mock_llm)
        research = self.create_sample_research()

        brief, _ = strategist.create_brief("Test Topic", research)

        # Power.win facts should be in power_win_first_party_facts
        assert "Power.win uses letter grades A-F" in brief.geo.power_win_first_party_facts

        # External sources should be in authoritative_external_sources
        assert "UK Gambling Commission" in brief.geo.authoritative_external_sources

    def test_empty_research_handled_safely(self) -> None:
        """Test that empty research result is handled without errors."""
        mock_llm = self.create_mock_llm([
            json.dumps({"primary_topic": "Empty", "search_intent": "informational", "primary_keyword": "empty"}),
            json.dumps({
                "direct_answer_questions": [],
                "concise_answers": {},
                "definitions": {},
                "important_factual_statements": [],
                "entities": [],
                "evidence_requirements": [],
                "structured_information_requirements": [],
            }),
            json.dumps({
                "important_entities": [],
                "entity_relationships": [],
                "authoritative_external_sources": [],
                "power_win_first_party_facts": [],
                "unique_information": [],
                "citation_evidence_opportunities": [],
                "factual_consistency_requirements": [],
                "questions_to_answer_clearly": [],
            }),
        ])

        strategist = ContentStrategist(llm_client=mock_llm)

        plan = ResearchPlan(topic="Empty Topic", questions=[])
        research = ResearchResult(topic="Empty Topic", plan=plan, questions=[])

        brief, _ = strategist.create_brief("Empty Topic", research)

        assert isinstance(brief, ContentBrief)
        assert brief.total_verified_facts == 0
        assert brief.total_power_win_facts == 0
        assert brief.total_external_facts == 0

    def test_malformed_llm_json_handled_safely(self) -> None:
        """Test that malformed JSON from LLM is handled gracefully."""
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = [
            "Not valid JSON {",
            "Also not valid JSON",
            "Still not valid",
        ]

        strategist = ContentStrategist(llm_client=mock_llm)
        research = self.create_sample_research()

        # Should not raise, should return brief with defaults
        brief, _ = strategist.create_brief("Test Topic", research)

        assert isinstance(brief, ContentBrief)
        assert brief.seo.primary_topic == "Test Topic"  # Falls back to topic
        assert brief.seo.search_intent == "informational"  # Default

    def test_empty_llm_responses_handled_safely(self) -> None:
        """Test that empty string responses from LLM are handled without crashing."""
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.return_value = ""

        strategist = ContentStrategist(llm_client=mock_llm)
        research = self.create_sample_research()

        brief, _ = strategist.create_brief("Test Topic", research)

        assert isinstance(brief, ContentBrief)
        assert brief.seo.primary_topic == "Test Topic"
        assert brief.seo.search_intent == "informational"

    def test_unsupported_claims_not_in_strategy(self) -> None:
        """Test that unsupported claims are tracked but not used as recommended facts."""
        mock_llm = self.create_mock_llm([
            json.dumps({"primary_topic": "Test", "search_intent": "informational", "primary_keyword": "test"}),
            json.dumps({
                "direct_answer_questions": [],
                "concise_answers": {},
                "definitions": {},
                "important_factual_statements": ["Verified fact only"],
                "entities": [],
                "evidence_requirements": [],
                "structured_information_requirements": [],
            }),
            json.dumps({
                "important_entities": [],
                "entity_relationships": [],
                "authoritative_external_sources": [],
                "power_win_first_party_facts": ["Power.win verified fact"],
                "unique_information": [],
                "citation_evidence_opportunities": [],
                "factual_consistency_requirements": [],
                "questions_to_answer_clearly": [],
            }),
        ])

        # Research with multiple unsupported claims
        pw_fact = make_power_win_fact("Power.win verified fact")
        unsupported1 = make_unsupported_claim("Unsupported claim 1")
        unsupported2 = make_unsupported_claim("Unsupported claim 2")

        plan = ResearchPlan(topic="Test", questions=[])
        research = ResearchResult(
            topic="Test",
            plan=plan,
            questions=[],
            power_win_facts=[pw_fact],
            external_facts=[],
            unsupported_claims=[unsupported1, unsupported2],
        )

        strategist = ContentStrategist(llm_client=mock_llm)
        brief, _ = strategist.create_brief("Test Topic", research)

        assert brief.unsupported_claims_count == 2
        # Unsupported claims should not appear in recommended facts
        all_facts = brief.get_all_recommended_facts()
        for fact in all_facts:
            assert "Unsupported" not in fact

    def test_partially_supported_facts_tracked(self) -> None:
        """Test that partially supported facts are tracked in metadata."""
        pw_partial = make_power_win_fact("Power.win partially verified fact")
        pw_partial.status = ClaimStatus.PARTIALLY_SUPPORTED
        pw_partial.confidence = 0.6

        plan = ResearchPlan(topic="Test", questions=[])
        research = ResearchResult(
            topic="Test",
            plan=plan,
            questions=[],
            power_win_facts=[pw_partial],
            external_facts=[],
        )

        mock_llm = self.create_mock_llm([
            json.dumps({"primary_topic": "Test", "search_intent": "informational", "primary_keyword": "test"}),
            json.dumps({"direct_answer_questions": [], "concise_answers": {}, "definitions": {},
                       "important_factual_statements": [], "entities": [], "evidence_requirements": [],
                       "structured_information_requirements": []}),
            json.dumps({"important_entities": [], "entity_relationships": [],
                       "authoritative_external_sources": [], "power_win_first_party_facts": [],
                       "unique_information": [], "citation_evidence_opportunities": [],
                       "factual_consistency_requirements": [], "questions_to_answer_clearly": []}),
        ])

        strategist = ContentStrategist(llm_client=mock_llm)
        brief, _ = strategist.create_brief("Test Topic", research)

        # Partially supported should count toward power_win_facts
        assert brief.total_power_win_facts == 1


class TestPhaseStatus:
    def test_strategy_success_when_all_parsed(self) -> None:
        from power_win_content.research.models import PhaseStatus
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = [
            json.dumps({"primary_topic": "Test", "search_intent": "informational", "primary_keyword": "test", "recommended_title": "Test Title"}),
            json.dumps({"direct_answer_questions": [], "concise_answers": {}, "definitions": {}, "important_factual_statements": [], "entities": [], "evidence_requirements": [], "structured_information_requirements": []}),
            json.dumps({"important_entities": [], "entity_relationships": [], "authoritative_external_sources": [], "power_win_first_party_facts": [], "unique_information": [], "citation_evidence_opportunities": [], "factual_consistency_requirements": [], "questions_to_answer_clearly": []}),
        ]
        strategist = ContentStrategist(llm_client=mock_llm)
        research = Mock()
        research.get_safe_claims_for_writer.return_value = []
        research.power_win_facts = []
        research.external_facts = []
        research.unsupported_claims = []
        research.research_gaps = []
        research.conflicting_information = []

        _, status = strategist.create_brief("Test Topic", research)
        assert status == PhaseStatus.SUCCESS

    def test_strategy_degraded_when_all_defaults(self) -> None:
        from power_win_content.research.models import PhaseStatus
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = [
            "invalid json",
            "also invalid",
            "still invalid",
        ]
        strategist = ContentStrategist(llm_client=mock_llm)
        research = Mock()
        research.get_safe_claims_for_writer.return_value = []
        research.power_win_facts = []
        research.external_facts = []
        research.unsupported_claims = []
        research.research_gaps = []
        research.conflicting_information = []

        _, status = strategist.create_brief("Test Topic", research)
        assert status == PhaseStatus.DEGRADED

    def test_strategy_degraded_when_one_defaults(self) -> None:
        from power_win_content.research.models import PhaseStatus
        mock_llm = Mock(spec=LLMClient)
        mock_llm.generate.side_effect = [
            json.dumps({"primary_topic": "Test", "search_intent": "informational", "primary_keyword": "test", "recommended_title": "T"}),
            "invalid json",
            "invalid json",
        ]
        strategist = ContentStrategist(llm_client=mock_llm)
        research = Mock()
        research.get_safe_claims_for_writer.return_value = []
        research.power_win_facts = []
        research.external_facts = []
        research.unsupported_claims = []
        research.research_gaps = []
        research.conflicting_information = []

        _, status = strategist.create_brief("Test Topic", research)
        assert status == PhaseStatus.DEGRADED