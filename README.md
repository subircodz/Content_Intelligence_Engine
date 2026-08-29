# Content Intelligence Engine

An AI-assisted, domain-independent content intelligence and production engine for researching a topic, understanding the competitive market, identifying content opportunities, creating an SEO/AIO/GEO strategy, and producing a human-reviewable article draft.

> **Editorial requirement:** generated content is an editorial draft. Human review is required before publication.

---

## Product Objective

Given a **target domain** and a **topic**, the engine should determine whether the topic is meaningfully covered by the competitor market and then choose the correct content-opportunity path.

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

The goal is to understand what the market covers, where coverage is weak or incomplete, and what useful differentiation opportunities exist.

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

The system must not manufacture competitor gaps when meaningful competitor coverage does not exist. **Case 2 is a valid successful content opportunity and must continue through independent research, SEO/AIO/GEO strategy, and article generation.**

### Coverage status must be explicit

The system must distinguish:

- `TOPIC_FOUND` — meaningful competitor coverage was identified
- `TOPIC_PARTIALLY_FOUND` — some meaningful coverage exists, but market coverage is limited
- `TOPIC_NOT_FOUND` — sufficient market research was completed and meaningful competitor coverage was not identified
- `INSUFFICIENT_DATA` — the evidence collected is not sufficient to determine market coverage
- `SEARCH_FAILED` — search/retrieval infrastructure failed

`TOPIC_NOT_FOUND` must never mean merely "the search returned nothing".

---

## Architecture

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

The engine separates **market intelligence** from **target-domain configuration**. The core research, competitor, strategy, and writing components must not assume a particular brand, website, or industry.

---

## Domain Independence

The target site is represented by configuration:

```text
ClientConfig
├── name
├── domain
├── first_party_domains
└── first_party_sitemaps
```

Examples:

```text
Target A
  Brand: Example
  Domain: example.com
  First-party sources: configured sitemaps

Target B
  Brand: Another Example
  Domain: another.example
  First-party sources: configured sitemaps
```

Both use the same engine.

### Design rule

**Target-specific behavior belongs in client configuration or adapters, not in the core engine.**

Examples of target-specific configuration:

- target brand name
- target domain
- first-party domains
- first-party sitemaps
- editorial rules
- brand terminology
- genuinely necessary industry-specific source rules

Examples of domain-independent functionality:

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
Research Quality Gate
    |-- Research completeness
    |-- Safe/unsupported claim balance
    |-- Conflict/gap warnings
    |-- Competitor evidence sufficiency
    |-- Blocks failed research
    |-- Allows valid Case 2 whitespace to continue
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
├── .env                         # Local secrets
├── .gitignore
├── .claude/
│   └── CLAUDE.md
├── docs/
├── output/                      # Generated DOCX files
├── scripts/                     # Developer/live utilities
├── tests/                       # Automated tests
└── src/
    └── intelligence_content_engine/       # Historical Python import package name
        ├── main.py              # Pipeline orchestration / CLI
        ├── client.py            # Target-domain ClientConfig
        ├── config.py             # Environment settings
        ├── ui.py
        ├── llm/
        │   └── client.py        # OpenAI-compatible LLM client
        ├── research/
        │   ├── models.py
        │   ├── quality.py       # Research quality gate
        │   ├── researcher.py
        │   ├── domain_researcher.py
        │   └── tools/
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

### Target

| Variable | Required | Purpose |
|---|---|---|
| `TARGET_DOMAIN` | Yes | Target domain for which content is being produced |
| `TARGET_BRAND` | Optional | Human-readable target brand name; defaults to `TARGET_DOMAIN` |
| `TARGET_FIRST_PARTY_SITEMAPS` | Optional | Comma-separated first-party sitemap URLs |

### LLM

The engine is **provider-agnostic** at the LLM layer. It requires an OpenAI-compatible chat-completions endpoint; the endpoint may be hosted by any compatible provider or locally.

| Variable | Required | Purpose |
|---|---|---|
| `LLM_BASE_URL` | Yes in production | OpenAI-compatible LLM API base URL |
| `LLM_MODEL` | Yes in production | Model name sent to the endpoint |

The engine does not contain a dependency on a specific LLM vendor, gateway, router, or model provider.

### Search

| Variable | Required | Purpose |
|---|---|---|
| None | No | DuckDuckGo can operate without credentials |
| `GOOGLE_API_KEY` | Optional | Google Custom Search API credential |
| `GOOGLE_CSE_ID` | Optional | Google Custom Search Engine ID |
| `BING_API_KEY` | Optional / legacy | Legacy Bing API path; browser search remains available |

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

Configure `.env`:

```text
TARGET_BRAND=Example
TARGET_DOMAIN=example.com
TARGET_FIRST_PARTY_SITEMAPS=https://example.com/sitemap.xml

LLM_BASE_URL=https://llm.example.com/v1
LLM_MODEL=your-model
```

Run tests:

```bash
venv/bin/pytest tests
```

---

## Running the Engine

The target domain is part of every content job. It can come from environment configuration or be overridden through the CLI.

### Environment-configured target

```bash
venv/bin/python -m intelligence_content_engine.main "Your Article Topic"
```

### Explicit target

```bash
venv/bin/python -m intelligence_content_engine.main \
  --target-domain example.com \
  --target-brand "Example" \
  --first-party-sitemap https://example.com/sitemap.xml \
  "Your Article Topic"
```

Multiple first-party sitemaps can be supplied by repeating `--first-party-sitemap`.

Interactive mode:

```bash
venv/bin/python -m intelligence_content_engine.main
```

Debug mode:

```bash
venv/bin/python -m intelligence_content_engine.main --debug "Your Article Topic"
```

The generated article is written as a DOCX under `output/`.

---

## Competitor Market Research

Competitor research is not simply a list of search results. The intended process is:

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

The configured target domain and configured first-party domains are excluded from competitor discovery.

---

## Case 1 — Competitive Content Gap

When meaningful competitor coverage exists, the engine should identify opportunities such as:

- topics competitors omit
- questions competitors fail to answer
- entities competitors miss
- comparisons that improve decision-making
- statistics or evidence opportunities
- user concerns that are poorly addressed
- weak, shallow, or repetitive angles
- useful differentiation opportunities

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

---

## Research Quality Gate

The quality gate sits between research/competitor analysis and strategy generation.

```text
Research + Competitor Intelligence
              |
              v
       Research Quality Gate
              |
       +------+------+
       |             |
       v             v
      FAIL      PASS / DEGRADED
       |             |
       v             v
      STOP        Strategy
                     |
              +------+------+
              |             |
          Case 1         Case 2
          Gap             Whitespace
              |             |
              +------+------+
                     |
                SEO/AIO/GEO
                     |
                  Article
```

The gate evaluates:

- number of safe claims available to the writer
- unsupported-claim proportion
- conflicting claims
- unresolved research gaps
- competitor coverage confidence
- whether competitor research actually succeeded

### Blocking conditions

The gate blocks strategy generation when research is unusable, for example:

- no usable research result
- insufficient safe claims
- excessive unsupported claims
- competitor search actually failed

### Non-blocking conditions

The gate can mark research `DEGRADED` without stopping article generation when limitations are known and manageable.

Most importantly:

> **`TOPIC_NOT_FOUND` is not a failure. It is a valid Case 2 outcome.**

A valid `TOPIC_NOT_FOUND` result continues through independent research, SEO/AIO/GEO strategy, and article generation.

`INSUFFICIENT_DATA` is different: it means the engine must not claim confirmed market whitespace. The article may proceed only when the remaining research is otherwise usable and the strategy layer is explicitly prevented from treating the topic as confirmed whitespace.

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

The optimization layers are strategy components. They are not coupled to a particular client or industry.

---

## Research and Evidence

The research layer supports content strategy with source-backed information.

Current capabilities include:

- first-party sitemap discovery
- multi-provider web search
- HTTP webpage fetching
- Playwright fallback for JavaScript-heavy pages
- claim/evidence extraction through the LLM
- research-gap recording
- claim status classification

### Evidence integrity requirement

LLM-generated supporting text is **not required to be a verbatim quotation** from the source. It may be a faithful paraphrase or summary.

Evidence validation must therefore evaluate **semantic support**, not exact string equality. The source must actually contain information that supports the claim represented by the supporting text.

The intended evidence states are:

- **FULL SUPPORT** — the source clearly supports the claim
- **PARTIAL SUPPORT** — the source supports only part of the claim
- **WEAK / AMBIGUOUS** — support is uncertain and needs review
- **UNSUPPORTED** — the source does not substantiate the claim

The original retrieved source content and retrieval metadata remain the audit trail. LLM output alone is never treated as proof.

---

## LLM Abstraction

`LLMClient` communicates with any OpenAI-compatible `/chat/completions` endpoint:

```text
LLMClient
   |
   v
LLM_BASE_URL + /chat/completions
   |
   v
Configured LLM_MODEL
```

The core engine does not know whether the endpoint is a hosted API, self-hosted model, gateway, router, or another compatible service.

---

## Search Provider Behaviour

Current search infrastructure supports multiple providers and fallbacks.

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

Provider failures should be isolated so one failed provider does not automatically invalidate all available search data.

---

## Phase Status

Each major phase reports:

| Status | Meaning |
|---|---|
| `SUCCESS` | Expected output was produced with sufficient data |
| `DEGRADED` | The phase completed with known limitations or partial data |
| `FAILED` | The phase could not produce usable output |

Business conclusions and infrastructure status are separate concepts. For example, `TOPIC_NOT_FOUND` is a market/research conclusion, while `SEARCH_FAILED` is an infrastructure outcome. They must never be conflated.

---

## DOCX Output

Generated documents are placed in `output/`.

The output contains the article draft with Word formatting for headings, paragraphs, lists, emphasis, and supported Markdown structures. Where competitor analysis is available, internal competitor-gap planning information may be included as an appendix.

The original user-supplied topic/title remains the article title. An LLM-recommended SEO title is advisory and must not silently replace the user's requested title.

---

## Testing

Run the automated suite with:

```bash
venv/bin/pytest tests
```

Tests covers:

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
- research quality gate pass/degraded/fail paths
- semantic evidence-support validation
- source provenance
- strategy generation
- writing failure handling
- DOCX generation

Live smoke tests under `scripts/` may hit external web services and are separate from deterministic unit tests.

---

## LICENSE

Licensed under MIT License

