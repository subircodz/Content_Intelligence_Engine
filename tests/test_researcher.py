import json
from unittest.mock import Mock, patch, MagicMock

import httpx

from power_win_content.llm.client import LLMClient
from power_win_content.research.models import (
    Claim,
    ClaimStatus,
    Evidence,
    InformationNature,
    ResearchPlan,
    ResearchQuestion,
    ResearchResult,
    Source,
    SourceType,
)
from power_win_content.research.researcher import Researcher
from power_win_content.research.tools import WebSearchTool, WebFetcher, SitemapFetcher


def test_researcher_creates_plan() -> None:
    """Test that Researcher can create a research plan."""
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.return_value = json.dumps({
        "questions": [
            {
                "question": "Does Power.win publish an editorial methodology?",
                "priority": "critical",
                "required_source_types": ["first_party"],
                "is_power_win_check": True,
                "notes": "Check power.win for methodology page"
            },
            {
                "question": "What licensing bodies are recognized?",
                "priority": "high",
                "required_source_types": ["regulatory", "government"],
                "is_power_win_check": False,
                "notes": "External regulatory sources"
            }
        ],
        "required_power_win_checks": ["editorial guidelines page", "about us"],
        "required_external_checks": ["UKGC register", "MGA register"],
        "claims_to_verify": ["10-point scoring system"]
    })

    researcher = Researcher(llm_client=mock_llm)
    plan = researcher.create_plan("How we Evaluate Online Casinos")

    assert isinstance(plan, ResearchPlan)
    assert plan.topic == "How we Evaluate Online Casinos"
    assert len(plan.questions) == 2
    assert plan.questions[0].is_power_win_check is True
    assert plan.questions[1].required_source_types == [SourceType.REGULATORY, SourceType.GOVERNMENT]
    assert "editorial guidelines page" in plan.required_power_win_checks
    assert "UKGC register" in plan.required_external_checks
    assert "10-point scoring system" in plan.claims_to_verify


def test_researcher_includes_power_win_checks_in_plan() -> None:
    """Test that research plans always include Power.win checks for Power.win topics."""
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.return_value = json.dumps({
        "questions": [
            {
                "question": "What is Power.win's review process?",
                "priority": "critical",
                "required_source_types": ["first_party"],
                "is_power_win_check": True
            },
            {
                "question": "What bonuses does Power.win list?",
                "priority": "high",
                "required_source_types": ["first_party"],
                "is_power_win_check": True
            }
        ],
        "required_power_win_checks": ["reviews section", "bonuses page", "methodology page"],
        "required_external_checks": [],
        "claims_to_verify": []
    })

    researcher = Researcher(llm_client=mock_llm)
    plan = researcher.create_plan("Power.win Casino Reviews")

    # Verify Power.win checks are included
    power_win_questions = [q for q in plan.questions if q.is_power_win_check]
    assert len(power_win_questions) >= 1
    assert len(plan.required_power_win_checks) >= 1


def test_researcher_returns_research_result_not_article() -> None:
    """Test that researcher returns ResearchResult, not an article string."""
    mock_llm = Mock(spec=LLMClient)
    # First call: create_plan - note is_power_win_check=True for Power.win question
    # Second call: extract claims from content (for _research_question)
    # Third call: extract claims from sitemap source (for _search_and_process_power_win)
    mock_llm.generate.side_effect = [
        json.dumps({
            "questions": [
                {
                    "question": "Does Power.win verify licenses?",
                    "priority": "high",
                    "required_source_types": ["first_party"],
                    "is_power_win_check": True
                }
            ],
            "required_power_win_checks": [],
            "required_external_checks": [],
            "claims_to_verify": []
        }),
        # Second call: extract claims from content (for _research_question source)
        json.dumps({
            "claims": [
                {
                    "text": "Power.win verifies licenses",
                    "status": "verified",
                    "nature": "fact",
                    "excerpt": "We verify all licenses",
                    "confidence": 0.9
                }
            ]
        }),
        # Third call: extract claims from sitemap source (for _search_and_process_power_win)
        json.dumps({
            "claims": []
        }),
    ]

    # Mock search tool to return a source
    mock_search = Mock(spec=WebSearchTool)
    mock_search.search.return_value = [
        Source(name="Power.win", url="https://power.win", source_type=SourceType.FIRST_PARTY)
    ]
    mock_search.close = Mock()

    # Mock fetcher to return content
    mock_fetcher = Mock(spec=WebFetcher)
    mock_fetcher.fetch.return_value = "We verify all licenses. Power.win checks every casino license."
    mock_fetcher.close = Mock()

    # Mock sitemap_fetcher to return empty sources to avoid real HTTP calls
    mock_sitemap = Mock(spec=SitemapFetcher)
    mock_sitemap.discover_first_party_sources.return_value = []
    mock_sitemap.close = Mock()

    researcher = Researcher(
        llm_client=mock_llm,
        search_tool=mock_search,
        fetcher=mock_fetcher,
        sitemap_fetcher=mock_sitemap,
    )
    result, _ = researcher.research("Test Topic")

    assert isinstance(result, ResearchResult)
    assert not isinstance(result, str)  # Not an article
    assert result.topic == "Test Topic"
    assert len(result.power_win_facts) == 1
    assert result.power_win_facts[0].text == "Power.win verifies licenses"
    assert len(result.power_win_facts[0].evidence) == 1
    assert result.power_win_facts[0].evidence[0].excerpt == "We verify all licenses"


def test_research_result_separates_power_win_and_external_facts() -> None:
    """Test that ResearchResult keeps Power.win facts separate from external facts."""
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = [
        # create_plan response
        json.dumps({
            "questions": [],
            "required_power_win_checks": ["editorial page"],
            "required_external_checks": ["UKGC site"],
            "claims_to_verify": []
        }),
        # Extract claims from Power.win source (_research_question)
        json.dumps({
            "claims": [{
                "text": "Power.win checks licenses",
                "status": "verified",
                "nature": "fact",
                "excerpt": "We check licenses",
                "confidence": 0.9
            }]
        }),
        # Extract claims from external source (_research_question)
        json.dumps({
            "claims": [{
                "text": "UKGC requires license verification",
                "status": "verified",
                "nature": "fact",
                "excerpt": "License verification required",
                "confidence": 0.95
            }]
        }),
        # Extract claims from sitemap source (_search_and_process_power_win)
        json.dumps({
            "claims": []
        }),
    ]

    mock_search = Mock(spec=WebSearchTool)
    # First search: Power.win check
    # Second search: external check
    mock_search.search.side_effect = [
        [Source(name="Power.win Editorial", url="https://power.win/editorial", source_type=SourceType.FIRST_PARTY)],
        [Source(name="UKGC", url="https://ukgc.gov.uk", source_type=SourceType.REGULATORY)],
    ]
    mock_search.close = Mock()

    mock_fetcher = Mock(spec=WebFetcher)
    mock_fetcher.fetch.side_effect = [
        "We check licenses for all casinos.",
        "License verification required by UK law.",
    ]
    mock_fetcher.close = Mock()

    # Mock sitemap_fetcher to return empty sources
    mock_sitemap = Mock(spec=SitemapFetcher)
    mock_sitemap.discover_first_party_sources.return_value = []
    mock_sitemap.close = Mock()

    researcher = Researcher(
        llm_client=mock_llm,
        search_tool=mock_search,
        fetcher=mock_fetcher,
        sitemap_fetcher=mock_sitemap,
    )
    result, _ = researcher.research("Test Topic")

    assert len(result.power_win_facts) == 1
    assert len(result.external_facts) == 1
    assert result.power_win_facts[0].text == "Power.win checks licenses"
    assert result.external_facts[0].text == "UKGC requires license verification"


def test_unsupported_information_not_treated_as_verified() -> None:
    """Test that unsupported claims are kept separate from verified facts."""
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = [
        # create_plan - the question is a Power.win check
        json.dumps({
            "questions": [
                {
                    "question": "What facts are on the test page?",
                    "priority": "high",
                    "required_source_types": ["first_party"],
                    "is_power_win_check": True
                }
            ],
            "required_power_win_checks": [],
            "required_external_checks": [],
            "claims_to_verify": []
        }),
        # Extract claims - returns one verified, one unsupported (_research_question)
        json.dumps({
            "claims": [
                {
                    "text": "Verified fact",
                    "status": "verified",
                    "nature": "fact",
                    "excerpt": "Evidence for verified fact",
                    "confidence": 0.9
                },
                {
                    "text": "Unverified claim",
                    "status": "unsupported",
                    "nature": "fact",
                    "excerpt": "Source mentions topic but doesn't confirm",
                    "confidence": 0.1
                }
            ]
        }),
        # Extract claims from sitemap source (_search_and_process_power_win)
        json.dumps({
            "claims": []
        }),
    ]

    mock_search = Mock(spec=WebSearchTool)
    mock_search.search.return_value = [
        Source(name="Test Source", url="https://example.com", source_type=SourceType.FIRST_PARTY)
    ]
    mock_search.close = Mock()

    mock_fetcher = Mock(spec=WebFetcher)
    mock_fetcher.fetch.return_value = "Evidence for verified fact. Source mentions topic but doesn't confirm."
    mock_fetcher.close = Mock()

    # Mock sitemap_fetcher to return empty sources
    mock_sitemap = Mock(spec=SitemapFetcher)
    mock_sitemap.discover_first_party_sources.return_value = []
    mock_sitemap.close = Mock()

    researcher = Researcher(
        llm_client=mock_llm,
        search_tool=mock_search,
        fetcher=mock_fetcher,
        sitemap_fetcher=mock_sitemap,
    )
    result, _ = researcher.research("Test Topic")

    # Unsupported claims should be in separate list
    assert len(result.unsupported_claims) == 1
    assert result.unsupported_claims[0].status == ClaimStatus.UNSUPPORTED

    # Verified facts should not include unsupported
    verified = result.get_all_verified_facts()
    assert len(verified) == 1
    assert verified[0].text == "Verified fact"

    # Safe claims for writer should exclude unsupported
    safe = result.get_safe_claims_for_writer()
    assert len(safe) == 1


def test_research_gaps_recorded() -> None:
    """Test that research gaps are properly recorded when no sources found."""
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = [
        json.dumps({
            "questions": [
                {
                    "question": "What is the exact scoring algorithm?",
                    "priority": "high",
                    "required_source_types": ["first_party"],
                    "is_power_win_check": True
                }
            ],
            "required_power_win_checks": ["methodology page"],
            "required_external_checks": [],
            "claims_to_verify": []
        }),
        # _search_and_process_power_win will call LLM for sitemap sources
        json.dumps({
            "claims": []
        }),
    ]

    mock_search = Mock(spec=WebSearchTool)
    # No sources found for the Power.win check
    mock_search.search.return_value = []
    mock_search.close = Mock()

    mock_fetcher = Mock(spec=WebFetcher)
    mock_fetcher.close = Mock()

    # Mock sitemap_fetcher to return empty sources
    mock_sitemap = Mock(spec=SitemapFetcher)
    mock_sitemap.discover_first_party_sources.return_value = []
    mock_sitemap.close = Mock()

    researcher = Researcher(
        llm_client=mock_llm,
        search_tool=mock_search,
        fetcher=mock_fetcher,
        sitemap_fetcher=mock_sitemap,
    )
    result, _ = researcher.research("Test Topic")

    assert len(result.research_gaps) >= 1
    # Should have a gap for the question with no sources
    gap_questions = [g.question for g in result.research_gaps]
    assert any("scoring algorithm" in q for q in gap_questions)


def test_researcher_handles_json_parse_errors_gracefully() -> None:
    """Test that researcher handles invalid JSON from LLM gracefully."""
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.return_value = "This is not valid JSON {"

    researcher = Researcher(llm_client=mock_llm)
    plan = researcher.create_plan("Test Topic")

    # Should return deterministic fallback plan instead of crashing
    assert isinstance(plan, ResearchPlan)
    assert plan.topic == "Test Topic"
    assert len(plan.questions) <= 2
    assert len(plan.required_power_win_checks) <= 2
    assert len(plan.required_external_checks) <= 2

    # Research should also handle parse errors in extraction
    mock_llm.generate.side_effect = [
        # create_plan returns valid
        json.dumps({
            "questions": [{"question": "Test?", "priority": "medium", "required_source_types": [], "is_power_win_check": False}],
            "required_power_win_checks": [],
            "required_external_checks": [],
            "claims_to_verify": []
        }),
        # extraction returns invalid JSON
        "Not JSON either",
    ]

    mock_search = Mock(spec=WebSearchTool)
    mock_search.search.return_value = [
        Source(name="Test", url="https://example.com", source_type=SourceType.GENERAL)
    ]
    mock_search.close = Mock()

    mock_fetcher = Mock(spec=WebFetcher)
    mock_fetcher.fetch.return_value = "Some content"
    mock_fetcher.close = Mock()

    researcher2 = Researcher(
        llm_client=mock_llm,
        search_tool=mock_search,
        fetcher=mock_fetcher,
    )
    result, _ = researcher2.research("Test Topic")

    assert isinstance(result, ResearchResult)
    assert result.topic == "Test Topic"


def test_conflicting_information_captured() -> None:
    """Test that conflicting information from different sources is captured."""
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = [
        # create_plan
        json.dumps({
            "questions": [
                {
                    "question": "What scoring system does Power.win use?",
                    "priority": "critical",
                    "required_source_types": ["first_party"],
                    "is_power_win_check": True
                }
            ],
            "required_power_win_checks": ["methodology page"],
            "required_external_checks": [],
            "claims_to_verify": []
        }),
        # First source (old blog): claims 10-point scale
        json.dumps({
            "claims": [{
                "text": "Power.win uses 10-point scale",
                "status": "verified",
                "nature": "fact",
                "excerpt": "Our 10-point scale rates casinos",
                "confidence": 0.8
            }]
        }),
        # Second source (current page): claims letter grades
        json.dumps({
            "claims": [{
                "text": "Power.win uses letter grades A-F",
                "status": "verified",
                "nature": "fact",
                "excerpt": "Grades A through F are used",
                "confidence": 0.9
            }]
        }),
        # Third call: extract claims from sitemap source (_search_and_process_power_win)
        json.dumps({
            "claims": []
        }),
    ]

    mock_search = Mock(spec=WebSearchTool)
    mock_search.search.side_effect = [
        [Source(name="Old Blog", url="https://power.win/blog/old", source_type=SourceType.FIRST_PARTY)],
        [Source(name="Current Page", url="https://power.win/methodology", source_type=SourceType.FIRST_PARTY)],
    ]
    mock_search.close = Mock()

    mock_fetcher = Mock(spec=WebFetcher)
    mock_fetcher.fetch.side_effect = [
        "Our 10-point scale rates casinos from 1 to 10.",
        "Grades A through F are used for casino ratings.",
    ]
    mock_fetcher.close = Mock()

    # Mock sitemap_fetcher to return empty sources
    mock_sitemap = Mock(spec=SitemapFetcher)
    mock_sitemap.discover_first_party_sources.return_value = []
    mock_sitemap.close = Mock()

    researcher = Researcher(
        llm_client=mock_llm,
        search_tool=mock_search,
        fetcher=mock_fetcher,
        sitemap_fetcher=mock_sitemap,
    )
    result, _ = researcher.research("Test Topic")

    # Should have two facts with different claims from different sources
    assert len(result.power_win_facts) == 2
    texts = [c.text for c in result.power_win_facts]
    assert "Power.win uses 10-point scale" in texts
    assert "Power.win uses letter grades A-F" in texts


def test_claim_nature_distinction() -> None:
    """Test that facts, editorial interpretations, and opinions are distinguished."""
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = [
        # create_plan
        json.dumps({
            "questions": [],
            "required_power_win_checks": ["methodology page"],
            "required_external_checks": [],
            "claims_to_verify": []
        }),
        # Extract claims with different natures
        json.dumps({
            "claims": [
                {
                    "text": "Power.win checks licenses",
                    "status": "verified",
                    "nature": "fact",
                    "excerpt": "We verify all casino licenses",
                    "confidence": 0.95
                },
                {
                    "text": "This makes Power.win trustworthy",
                    "status": "verified",
                    "nature": "editorial_interpretation",
                    "excerpt": "Our verification process ensures trust",
                    "confidence": 0.8
                },
                {
                    "text": "Power.win is the best site",
                    "status": "verified",
                    "nature": "opinion",
                    "excerpt": "In my view, Power.win is the best",
                    "confidence": 0.7
                }
            ]
        }),
        # Third call: extract claims from sitemap source (_search_and_process_power_win)
        json.dumps({
            "claims": []
        }),
    ]

    mock_search = Mock(spec=WebSearchTool)
    mock_search.search.return_value = [
        Source(name="Power.win", url="https://power.win", source_type=SourceType.FIRST_PARTY)
    ]
    mock_search.close = Mock()

    mock_fetcher = Mock(spec=WebFetcher)
    mock_fetcher.fetch.return_value = (
        "We verify all casino licenses. "
        "Our verification process ensures trust. "
        "In my view, Power.win is the best."
    )
    mock_fetcher.close = Mock()

    # Mock sitemap_fetcher to return empty sources
    mock_sitemap = Mock(spec=SitemapFetcher)
    mock_sitemap.discover_first_party_sources.return_value = []
    mock_sitemap.close = Mock()

    researcher = Researcher(
        llm_client=mock_llm,
        search_tool=mock_search,
        fetcher=mock_fetcher,
        sitemap_fetcher=mock_sitemap,
    )
    result, _ = researcher.research("Test Topic")

    facts = [c for c in result.power_win_facts if c.nature == InformationNature.FACT]
    interpretations = [c for c in result.power_win_facts if c.nature == InformationNature.EDITORIAL_INTERPRETATION]
    opinions = [c for c in result.power_win_facts if c.nature == InformationNature.OPINION]

    assert len(facts) == 1
    assert len(interpretations) == 1
    assert len(opinions) == 1

    # Safe claims for writer should only include facts, not interpretations/opinions
    safe = result.get_safe_claims_for_writer()
    assert len(safe) == 1
    assert safe[0].text == "Power.win checks licenses"


def test_web_search_tool_returns_sources() -> None:
    """Test WebSearchTool returns Source objects."""
    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = """
        <html>
            <div class="result__body">
                <a class="result__snippet" href="https://power.win/editorial">Power.win Editorial Guidelines</a>
                <div class="result__snippet">Our editorial process ensures accurate reviews.</div>
            </div>
            <div class="result__body">
                <a class="result__snippet" href="https://ukgc.gov.uk/license">UKGC License Register</a>
                <div class="result__snippet">Search licensed operators.</div>
            </div>
        </html>
        """
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        tool = WebSearchTool()
        sources = tool.search("Power.win editorial methodology")

        assert len(sources) >= 1
        # Check first source is Power.win (first_party)
        power_win_sources = [s for s in sources if s.source_type == SourceType.FIRST_PARTY]
        assert len(power_win_sources) >= 1
        assert "power.win" in str(power_win_sources[0].url).lower()

        # Check regulatory source classification
        reg_sources = [s for s in sources if s.source_type == SourceType.REGULATORY]
        assert len(reg_sources) >= 1
        assert "ukgc.gov.uk" in str(reg_sources[0].url).lower()


def test_web_fetcher_extracts_text() -> None:
    """Test WebFetcher extracts readable text from HTML."""
    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <script>console.log('remove me');</script>
                <style>body { color: red; }</style>
                <nav>Navigation</nav>
                <main>
                    <h1>Main Content</h1>
                    <p>This is the article content we want to extract.</p>
                </main>
                <footer>Footer content</footer>
            </body>
        </html>
        """
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        fetcher = WebFetcher()
        text = fetcher.fetch("https://example.com/article")

        assert text is not None
        assert "Main Content" in text
        assert "article content we want to extract" in text
        assert "remove me" not in text  # Script removed
        assert "color: red" not in text  # Style removed
        assert "Navigation" not in text  # Nav removed
        assert "Footer" not in text  # Footer removed


def test_web_fetcher_handles_errors() -> None:
    """Test WebFetcher handles network errors gracefully."""
    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        import httpx
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")

        fetcher = WebFetcher()
        text = fetcher.fetch("https://example.com/slow")

        assert text is None


def test_power_win_source_classification() -> None:
    """Test that Power.win URLs are classified as FIRST_PARTY."""
    from power_win_content.research.tools.web_search import _classify_source_type

    assert _classify_source_type("https://power.win/reviews") == SourceType.FIRST_PARTY
    assert _classify_source_type("https://www.power.win/about") == SourceType.FIRST_PARTY
    assert _classify_source_type("https://blog.power.win/news") == SourceType.FIRST_PARTY


def test_regulatory_source_classification() -> None:
    """Test that regulatory URLs are classified correctly."""
    from power_win_content.research.tools.web_search import _classify_source_type

    assert _classify_source_type("https://www.ukgc.gov.uk/license") == SourceType.REGULATORY
    assert _classify_source_type("https://mga.org.mt/license") == SourceType.REGULATORY
    assert _classify_source_type("https://spillemyndigheden.dk/register") == SourceType.REGULATORY


def test_create_plan_timeout_uses_fallback() -> None:
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = httpx.ReadTimeout("timed out")

    topic = "How We Evaluate Online Casinos: Power.win Editorial & Review Methodology"
    researcher = Researcher(llm_client=mock_llm)
    plan = researcher.create_plan(topic)

    assert isinstance(plan, ResearchPlan)
    assert plan.topic == topic
    assert len(plan.questions) <= 2
    assert len(plan.required_power_win_checks) <= 2
    assert len(plan.required_external_checks) <= 2
    assert plan.questions[0].notes == "Fallback research question generated after planning LLM failure."


def test_create_plan_network_exception_uses_fallback() -> None:
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = httpx.ConnectError("network failed")

    researcher = Researcher(llm_client=mock_llm)
    plan = researcher.create_plan("Network Topic")

    assert plan.topic == "Network Topic"
    assert len(plan.questions) <= 2


def test_create_plan_empty_response_uses_fallback() -> None:
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.return_value = ""

    researcher = Researcher(llm_client=mock_llm)
    plan = researcher.create_plan("Empty Topic")

    assert plan.topic == "Empty Topic"
    assert len(plan.questions) <= 2
    assert len(plan.required_power_win_checks) <= 2


def test_research_continues_after_plan_failure() -> None:
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = [httpx.ReadTimeout("timed out"), json.dumps({"claims": []})]
    mock_search = Mock(spec=WebSearchTool)
    mock_search.search.return_value = []
    mock_fetcher = Mock(spec=WebFetcher)
    mock_sitemap = Mock(spec=SitemapFetcher)
    mock_sitemap.discover_first_party_sources.return_value = []

    researcher = Researcher(
        llm_client=mock_llm,
        search_tool=mock_search,
        fetcher=mock_fetcher,
        sitemap_fetcher=mock_sitemap,
    )

    result, _ = researcher.research("Fallback Topic")

    assert isinstance(result, ResearchResult)
    assert result.topic == "Fallback Topic"
    assert result.plan is not None
    assert result.plan.topic == "Fallback Topic"
    assert mock_search.search.called


def test_government_source_classification() -> None:
    """Test that government URLs are classified correctly."""
    from power_win_content.research.tools.web_search import _classify_source_type

    assert _classify_source_type("https://www.legislation.gov.uk/act") == SourceType.GOVERNMENT
    assert _classify_source_type("https://www.gov.uk/gambling-law") == SourceType.GOVERNMENT
    assert _classify_source_type("https://www.justice.gc.ca/eng") == SourceType.GOVERNMENT


def test_source_evidence_chain() -> None:
    """Test that Claim -> Evidence -> Source -> URL chain is complete."""
    source = Source(
        name="Test Source",
        url="https://example.com/page",
        source_type=SourceType.PRIMARY,
        title="Test Page"
    )
    evidence = Evidence(
        source=source,
        excerpt="Direct quote from the source page",
        notes="Supporting context"
    )
    claim = Claim(
        text="Test claim",
        status=ClaimStatus.VERIFIED,
        nature=InformationNature.FACT,
        evidence=[evidence],
        confidence=0.9
    )

    # Verify chain
    assert claim.evidence[0].source.name == "Test Source"
    assert str(claim.evidence[0].source.url) == "https://example.com/page"
    assert claim.evidence[0].source.source_type == SourceType.PRIMARY
    assert claim.evidence[0].excerpt == "Direct quote from the source page"
    assert claim.status == ClaimStatus.VERIFIED
    assert claim.nature == InformationNature.FACT


def test_research_returns_phase_status_success() -> None:
    from power_win_content.research.models import PhaseStatus
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = [
        json.dumps({
            "questions": [{"question": "Test Q?", "priority": "medium", "required_source_types": [], "is_power_win_check": False}],
            "required_power_win_checks": [],
            "required_external_checks": [],
            "claims_to_verify": [],
        }),
        json.dumps({"claims": []}),
    ]
    mock_search = Mock(spec=WebSearchTool)
    mock_search.search.return_value = []
    mock_fetcher = Mock(spec=WebFetcher)
    mock_sitemap = Mock(spec=SitemapFetcher)
    mock_sitemap.discover_first_party_sources.return_value = []

    researcher = Researcher(llm_client=mock_llm, search_tool=mock_search, fetcher=mock_fetcher, sitemap_fetcher=mock_sitemap)
    result, status = researcher.research("Test Topic")
    assert isinstance(status, PhaseStatus)
    assert status == PhaseStatus.DEGRADED


def test_research_returns_degraded_on_fallback_plan() -> None:
    from power_win_content.research.models import PhaseStatus
    mock_llm = Mock(spec=LLMClient)
    mock_llm.generate.side_effect = [httpx.ReadTimeout("timed out"), json.dumps({"claims": []})]
    mock_search = Mock(spec=WebSearchTool)
    mock_search.search.return_value = []
    mock_fetcher = Mock(spec=WebFetcher)
    mock_sitemap = Mock(spec=SitemapFetcher)
    mock_sitemap.discover_first_party_sources.return_value = []

    researcher = Researcher(llm_client=mock_llm, search_tool=mock_search, fetcher=mock_fetcher, sitemap_fetcher=mock_sitemap)
    result, status = researcher.research("Fallback Topic")
    assert status == PhaseStatus.DEGRADED