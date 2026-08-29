# Content Intelligence Engine

An AI-assisted content intelligence and production engine for researching a topic, understanding the competitive market, identifying content opportunities, creating an SEO/AIO/GEO content strategy, and producing a human-reviewable article draft.

The engine is **domain-independent**. A target brand/domain is supplied as configuration. Power.win is currently the first configured client/use case, but the core pipeline is designed to work with other domains without changing the research, competitor, strategy, or writing engine.

> **Editorial requirement:** generated content is an editorial draft. Human review is required before publication.

---

## Product Objective

Given a target domain and a topic, the engine should answer:

> **Is this topic already meaningfully covered by the competitor market?**

It then follows one of two content-opportunity paths.

### Case 1 — Topic found in the competitor market

```text
Topic
  |
  v
Market / Competitor Research
  |
  v
Meaningful competitor coverage found
  |
  v
Competitive Coverage Analysis
  |
  v
Content Gap Analysis
  |
  v
Content Differentiation Strategy
  |
  v
SEO + AIO + GEO Strategy
  |
  v
Article Draft
```

The goal is to understand what competitors cover, where their coverage is weak or incomplete, and what useful content opportunities can produce a stronger article.

### Case 2 — Topic not found in the competitor market

```text
Topic
  |
  v
Market / Competitor Research
  |
  v
No meaningful competitor coverage
  |
  v
Market Whitespace / Topic Opportunity
  |
  v
Independent Topic Research
  |
  v
SEO + AIO + GEO Strategy
  |
  v
Article Draft
```

The system must **not manufacture competitor gaps** when meaningful competitor coverage does not exist. This is a market-whitespace opportunity and requires a different content strategy.

### Important distinction

`NOT_FOUND` must never mean merely "the search returned nothing". The system must distinguish between:

- `TOPIC_FOUND` — meaningful competitor coverage was identified
- `TOPIC_PARTIALLY_FOUND` — some meaningful coverage exists, but market coverage is limited
- `TOPIC_NOT_FOUND` — sufficient market research was completed and meaningful competitor coverage was not identified
- `INSUFFICIENT_DATA` — the evidence collected is not sufficient to determine market coverage
- `SEARCH_FAILED` — the search/retrieval infrastructure failed

This distinction is fundamental to Case 1 vs Case 2.

---

## Product Architecture

```text
                         CONTENT JOB
                             |
          +------------------+------------------+
          |                                     |
          v                                     v
   Target Domain                              Topic
          |                                     |
          +------------------+------------------+
                             |
                             v
                    MARKET RESEARCH
                             |
                  Competitor Discovery
                             |
                  Topic Coverage Assessment
                             |
               +-------------+-------------+
               |                           |
               v                           v
       TOPIC FOUND / PARTIAL         TOPIC NOT FOUND
               |                           |
               v                           v
       Competitive Gap              Market Whitespace
          Analysis                    Analysis
               |                           |
               +-------------+-------------+
                             |
                             v
                     Content Strategy
                             |
                    +--------+--------+
                    |        |        |
                    v        v        v
                   SEO      AIO      GEO
                    |        |        |
                    +--------+--------+
                             |
                             v
                         Writing
                             |
                             v
                    Human-reviewable Draft
                             |
                             v
                           DOCX
```

The engine separates **market intelligence** from **target-domain configuration**. The market research layer can therefore be reused for any target domain.

---

## Domain Independence

The core engine must not assume that the target is Power.win, a gambling company, or any other specific industry.

The target is represented through configuration:

```text
ClientConfig
├── name
├── domain
├── first_party_domains
└── first_party_sitemaps
```

For example:

```text
Client A
  Brand: Power.win
  Domain: power.win
  First-party sources: configured Power.win sitemaps
```

and:

```text
Client B
  Brand: Example
  Domain: example.com
  First-party sources: configured Example sitemaps
```

use the same core research, competitor, strategy, and writing engine.

### Design rule

**Power.win-specific behavior belongs in client configuration/adapters, not in the core engine.**

Examples of domain-specific configuration include:

- target brand name
- target domain
- first-party domains
- first-party sitemaps
- editorial rules
- brand terminology
- industry-specific source rules, where genuinely necessary

Examples of domain-independent functionality include:

- search
- webpage retrieval
- source normalization
- competitor discovery
- topic coverage analysis
- gap/whitespace analysis
- evidence extraction
- content strategy
- SEO/AIO/GEO planning
- article generation
- DOCX generation

---

## Current Pipeline

```text
CLI / UI
    |
    v
Content Job + ClientConfig
    |
    v
Research
    |-- Multi-provider Web Search
    |-- First-party Sitemap Discovery
    |-- HTTP Fetching
    |-- Playwright Fallback
    |-- Evidence / Claim Extraction
    |
    v
Competitor Intelligence
    |-- Candidate Discovery
    |-- Target-domain Exclusion
    |-- Competitor Fetching
    |-- Competitor Coverage Extraction
    |-- Coverage / Gap Analysis
    |
    v
Content Strategy
    |-- Search Intent
    |-- SEO
    |-- AIO
    |-- GEO
    |-- Competitive Differentiation / Whitespace
    |
    v
Content Writer
    |
    v
DOCX Output
```

Each pipeline phase reports `SUCCESS`, `DEGRADED`, or `FAILED`.

---

## Repository Structure

```text
content-intelligence-engine/
├── pyproject.toml
├── README.md
├── .env                         # Local secrets; never commit
├── .gitignore
├── .claude/
│   └── CLAUDE.md
├── output/                      # Generated DOCX files
├── scripts/                     # Developer/live utilities
├── tests/                       # Automated tests
└── src/
    └── power_win_content/       # Python package; package rename is a follow-up cleanup
        ├── main.py              # Pipeline orchestration / CLI
        ├── client.py            # Domain-independent ClientConfig
        ├── config.py            # Environment settings
        ├── ui.py
        ├── llm/
        │   └── client.py
        ├── research/
        │   ├── models.py
        │   ├── researcher.py
        │   ├── domain_researcher.py
        │   └── tools/
        │       ├── web_search.py
        │       ├── web_fetcher.py
        │       ├── hybrid_fetcher.py
        │       ├── browser_fetcher.py
        │       └── sitemap_fetcher.py
        ├── competitors/
        │   ├── analyzer.py
        │   └── models.py
        ├── strategy/
        │   ├── strategist.py
        │   ├── domain_strategist.py
        │   └── models.py
        ├── agents/
        │   ├── content_writer.py
        │   └── domain_content_writer.py
        └── output/
            └── docx_writer.py
```

The current Python import package retains its historical `power_win_content` name during the transition. The distribution/project identity has been changed to **`content-intelligence-engine`**. Removing the remaining package-level legacy name is a separate cleanup step and should not change behavior.

---

## Prerequisites

| Requirement | Detail |
|---|---|
| Python | >= 3.13 |
| Network access | Required for web search, webpage fetching, and the LLM API |
| LLM provider | Any OpenAI-compatible `/chat/completions` endpoint |
| Playwright Chromium | Required for browser-based search/fetch fallbacks |

Install Chromium once:

```bash
playwright install chromium
```

---

## Environment Configuration

The application loads `.env` from the project root through `python-dotenv`.

### Target-domain configuration

The target site is configurable rather than hard-coded.

| Variable | Required | Purpose |
|---|---|---|
| `TARGET_DOMAIN` | Optional/configurable | Target domain being researched for content production |
| `TARGET_BRAND` | Optional/configurable | Human-readable target brand name |
| `TARGET_FIRST_PARTY_SITEMAPS` | Optional | Comma-separated first-party sitemap URLs |

The target domain can also be supplied through the CLI configuration supported by the application.

### LLM

| Variable | Required | Purpose |
|---|---|---|
| `OMNIROUTE_BASE_URL` | Yes in production | OpenAI-compatible LLM endpoint |
| `OMNIROUTE_MODEL` | Yes in production | Model name sent to the endpoint |

### Search

| Variable | Required | Purpose |
|---|---|---|
| None | No | DuckDuckGo can operate without credentials |
| `GOOGLE_API_KEY` | Optional | Google Custom Search API credential |
| `GOOGLE_CSE_ID` | Optional | Google Custom Search Engine ID |
| `BING_API_KEY` | Optional / legacy | Legacy Bing API path; normal Bing search uses browser rendering |

---

## Installation

```bash
git clone <repository-url> content-intelligence-engine
cd content-intelligence-engine

python3 -m venv venv
source venv/bin/activate

pip install -e .
playwright install chromium
```

Configure `.env` with the target and LLM settings.

Example:

```text
TARGET_BRAND=Example
TARGET_DOMAIN=example.com
TARGET_FIRST_PARTY_SITEMAPS=https://example.com/sitemap.xml

OMNIROUTE_BASE_URL=https://llm.example.com/v1
OMNIROUTE_MODEL=your-model
```

Run tests:

```bash
venv/bin/pytest tests
```

---

## Running the Engine

The application accepts a topic and uses the configured target domain/brand.

```bash
venv/bin/python -m power_win_content.main "Your Article Topic"
```

Interactive mode:

```bash
venv/bin/python -m power_win_content.main
```

Debug mode:

```bash
venv/bin/python -m power_win_content.main --debug "Your Article Topic"
```

The generated article is written as a DOCX under `output/`.

---

## Competitor Market Research

Competitor research is not simply a list of pages returned by a search engine. The intended process is:

```text
Topic
  |
  v
Multi-engine discovery
  |
  v
Candidate pages
  |
  v
Relevance / competitor filtering
  |
  v
Fetch competitor pages
  |
  v
Extract structured coverage
  |
  v
Build market coverage view
  |
  v
Determine topic coverage status
  |
  +-----------------------------+
  |                             |
  v                             v
FOUND / PARTIAL             NOT FOUND
  |                             |
  v                             v
Gap Analysis               Whitespace
```

A competitor is useful only when its page meaningfully addresses the requested topic. A search result merely mentioning the topic is not sufficient.

### Target-domain exclusion

The configured target domain and its configured first-party domains are excluded from competitor discovery. This is intentionally domain-independent; the engine does not contain a special `power.win` competitor exclusion rule.

### Competitor coverage

The long-term target is a structured coverage model rather than relying entirely on an LLM to infer gaps from prose:

```text
                    Competitor A  B  C  D  E
Topic / subtopic          yes     yes no yes no
Question                  yes     no  no yes no
Entity                    yes     yes yes no no
Comparison                no      yes no  no yes
Statistic                 yes     no  no  no no
```

This allows the system to distinguish common market coverage from under-covered and missing topics.

---

## Case 1 — Competitive Content Gap

When meaningful competitor coverage exists, the engine should identify opportunities such as:

- topics competitors omit
- questions competitors fail to answer
- entities competitors miss
- comparisons that would improve decision-making
- statistics or evidence opportunities
- user concerns that are poorly addressed
- weak, shallow, or repetitive angles
- useful differentiation opportunities

The objective is not to copy competitors. It is to understand the market and produce a more useful, authoritative, differentiated article.

Competitor gaps are **planning intelligence**, not proof that a competitor's claims are true.

---

## Case 2 — Market Whitespace

When sufficient research shows that meaningful competitor coverage does not exist, the engine must switch from competitive-gap analysis to whitespace analysis.

The system should then:

1. Record that the topic is currently underserved/not meaningfully covered.
2. Record the evidence and limitations supporting that conclusion.
3. Research the topic independently using appropriate authoritative sources.
4. Determine search intent and user questions.
5. Build the SEO/AIO/GEO strategy from the topic itself rather than invented competitor weaknesses.
6. Generate the article.

A search failure, fetch failure, CAPTCHA, API outage, or insufficient sample must **never** be represented as confirmed market whitespace.

---

## SEO / AIO / GEO Strategy

The strategy layer translates research and market intelligence into an article plan.

### SEO

Examples of strategy inputs:

- search intent
- primary keyword
- secondary keywords
- semantic coverage
- heading structure
- title/meta considerations
- useful internal content opportunities

### AIO

Examples of strategy inputs:

- questions requiring direct answers
- concise definitions
- answer-first structures
- explicit question/answer coverage
- factual clarity

### GEO

Examples of strategy inputs:

- important entities
- authoritative sources
- entity relationships
- contextual completeness
- information useful to generative search systems

The optimization layers are strategy components. They should not be tightly coupled to any particular client or industry.

---

## Research and Evidence

The research layer supports the content strategy with source-backed information.

Current capabilities include:

- first-party sitemap discovery
- multi-provider web search
- HTTP webpage fetching
- Playwright fallback for JavaScript-heavy pages
- claim/evidence extraction through the LLM
- research-gap recording
- claim status classification

The engine records phase degradation when research is incomplete rather than pretending that missing sources were successfully retrieved.

### Evidence integrity requirement

LLM-generated excerpts are proposed evidence, not automatically trustworthy evidence. A production-quality implementation must deterministically verify that an extracted excerpt actually occurs in the fetched source content before treating it as verified provenance.

This is an engineering invariant and must not depend solely on an LLM prompt.

---

## Search Provider Behaviour

Current search infrastructure supports multiple providers and fallbacks.

General flow:

```text
Query
 |
 +--> DuckDuckGo
 |
 +--> Google API (when configured)
 |       |
 |       +--> browser fallback when required
 |
 +--> Bing browser search
         |
         +--> legacy API path when configured
 |
 v
Normalize
 |
 v
Deduplicate
 |
 v
Candidate URLs
```

Provider failures should be isolated so that one failed provider does not automatically invalidate all available search data.

CAPTCHA/challenge pages are treated as unavailable results. The application does not bypass CAPTCHAs, anti-bot systems, authentication, or access controls.

---

## Phase Status

Each major phase reports:

| Status | Meaning |
|---|---|
| `SUCCESS` | Expected output was produced with sufficient data |
| `DEGRADED` | The phase completed with known limitations or partial data |
| `FAILED` | The phase could not produce usable output |

A future market-coverage model should additionally expose a **coverage assessment** separately from infrastructure phase status. For example, `TOPIC_NOT_FOUND` is a business/research conclusion, while `SEARCH_FAILED` is an infrastructure outcome.

These must never be conflated.

---

## DOCX Output

Generated documents are placed in `output/`.

The output contains the article draft with Word formatting for headings, paragraphs, lists, emphasis, and other supported Markdown structures. Where competitor analysis is available, internal competitor-gap planning information may be included as an appendix.

The original user-supplied topic/title remains the article title. An LLM-recommended SEO title is advisory and must not silently replace the user's requested title.

---

## Testing

Run the automated suite with:

```bash
venv/bin/pytest tests
```

Tests should cover both ordinary functionality and the system's critical invariants, including:

- target-domain normalization
- first-party URL detection
- competitor target-domain exclusion
- search-provider fallback and isolation
- URL normalization/deduplication
- research fallback behaviour
- phase-status propagation
- competitor coverage extraction
- topic coverage classification
- Case 1 vs Case 2 routing
- search failure vs topic-not-found distinction
- evidence excerpt verification
- source provenance
- strategy generation
- writing failure handling
- DOCX generation

Live smoke tests under `scripts/` may hit external web services and are separate from deterministic unit tests.

---

## Production Engineering Principles

The following principles govern further development.

### 1. Domain independence

Core code must not contain assumptions about Power.win or any other single client.

### 2. Market intelligence before writing

The article should be generated from structured market/topic intelligence, not simply from a search result list.

### 3. Case 1 and Case 2 are different products paths

Competitive gaps and market whitespace must remain separate concepts.

### 4. Search failure is not market whitespace

Insufficient research cannot be presented as evidence that competitors do not cover a topic.

### 5. Deterministic validation at trust boundaries

LLM output may propose claims, excerpts, classifications, and plans, but critical invariants must be validated by software.

### 6. Preserve provenance

Where factual claims influence an article, the system should preserve the relationship:

```text
Article Claim
    |
    v
Research Claim
    |
    v
Evidence
    |
    v
Source
    |
    v
Source URL
```

### 7. Human editorial control

The system produces an editorial draft, not an autonomous publishing decision.

---

## Current Refactoring State

The first domain-independence refactor has been started and the active pipeline now accepts a target configuration instead of assuming Power.win as the target.

Completed in the current refactor:

- domain-aware `ClientConfig`
- configurable target brand/domain
- configurable first-party domains and sitemaps
- domain-aware target-domain exclusion in competitor discovery
- domain-independent research/strategy/writer facades
- configurable target-related environment variables
- project/distribution identity moved toward `content-intelligence-engine`

Remaining cleanup is intentionally separate from this first milestone:

- remove the historical `power_win_content` Python package name
- remove remaining legacy Power.win terminology from compatibility models/APIs
- make Case 1 / Case 2 topic-coverage assessment a first-class competitor-analysis result
- implement deterministic evidence excerpt verification
- strengthen automated coverage/provenance tests

**Do not add new major features before the domain-independence boundary and the Case 1/Case 2 market-coverage model are stable.**

---

## Development Direction

The intended development order is:

```text
1. Domain Independence
       |
       v
2. Market Coverage Assessment
       |
       +--> Case 1: Competitive Gap
       |
       +--> Case 2: Market Whitespace
       |
       v
3. Evidence / Provenance Hardening
       |
       v
4. SEO / AIO / GEO Strategy Refinement
       |
       v
5. Content Quality / Writing Refinement
       |
       v
6. Production Observability, Cost and Reliability
```

The system should evolve from a Power.win-specific content generator into a reusable **content intelligence engine** with Power.win as one client configuration.