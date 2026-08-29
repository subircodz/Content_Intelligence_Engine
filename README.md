# Content Intelligence Engine

A domain-independent content intelligence and production engine that turns a topic into research-backed content strategy and a human-reviewable article draft.

The engine researches the topic and its surrounding market, analyzes meaningful competitor coverage, identifies either competitive content opportunities or market whitespace, develops an SEO/AIO/GEO strategy, and generates the resulting article as a DOCX document.

> **Editorial boundary:** generated articles are drafts for human review. The engine does not publish content automatically.

---

## What It Does

A content job starts with two inputs:

- **Target domain** — the website or client the content is being produced for.
- **Topic** — the subject to research and turn into content.

The engine then runs the topic through a research and production pipeline:

```text
Topic + Target Domain
        |
        v
     Research
        |
        v
Market / Competitor Intelligence
        |
        v
Content Opportunity Detection
        |
        v
 Research Quality Gate
        |
        v
 Content Strategy
   |    |    |
  SEO  AIO  GEO
        |
        v
 Article Generation
        |
        v
      DOCX
```

The result is more than an article draft. The intermediate research and strategy stages provide the intelligence used to determine what the article should cover and how it should be positioned.

---

## Content Opportunity Detection

The engine distinguishes between two fundamentally different market conditions.

### Competitive Opportunity

When meaningful competitor content exists for the topic, the engine analyzes that coverage to identify opportunities for differentiation.

```text
Topic
  |
  v
Market Research
  |
  v
Meaningful Competitor Coverage
  |
  v
Coverage Analysis
  |
  v
Content Gaps + Differentiation Opportunities
  |
  v
SEO / AIO / GEO Strategy
  |
  v
Article Draft
```

Examples of opportunities include:

- important topics competitors omit
- unanswered user questions
- missing entities or concepts
- weak or shallow coverage
- repetitive approaches
- useful comparisons
- evidence or data opportunities
- underserved user concerns

Competitor analysis is used as planning intelligence. A competitor's inclusion of a claim does not make that claim authoritative or true.

### Market Whitespace

When sufficient research finds no meaningful competitor coverage, the engine treats the result as market whitespace rather than forcing a competitive-gap analysis.

```text
Topic
  |
  v
Market Research
  |
  v
No Meaningful Competitor Coverage
  |
  v
Market Whitespace
  |
  v
Independent Topic Research
  |
  v
SEO / AIO / GEO Strategy
  |
  v
Article Draft
```

The topic therefore remains a valid content opportunity even when competitors do not provide useful material to compare against.

---

## Research Outcomes

Market coverage and infrastructure health are represented separately.

| Outcome | Meaning |
|---|---|
| `TOPIC_FOUND` | Meaningful competitor coverage was identified. |
| `TOPIC_PARTIALLY_FOUND` | Some meaningful competitor coverage exists, but coverage is limited. |
| `TOPIC_NOT_FOUND` | Sufficient market research found no meaningful competitor coverage. |
| `INSUFFICIENT_DATA` | Available evidence is insufficient to determine market coverage confidently. |
| `SEARCH_FAILED` | Search or retrieval infrastructure failed. |

`TOPIC_NOT_FOUND` is a market finding, not an infrastructure failure. `SEARCH_FAILED` indicates that the engine could not reliably complete the required retrieval work.

---

## How the Engine Works

### 1. Research

The research layer collects information from first-party and external sources relevant to the topic.

It supports:

- multi-provider web search
- first-party sitemap discovery
- HTTP webpage retrieval
- Playwright fallback for JavaScript-heavy pages
- source normalization and URL handling
- claim and evidence extraction
- research-gap recording
- claim-status classification

### 2. Competitor Intelligence

Search results are treated as candidate sources rather than automatically accepted as competitors.

The competitor analysis process is:

```text
Search
  |
  v
Candidate URLs
  |
  v
Relevance / Competitor Filtering
  |
  v
Competitor Page Retrieval
  |
  v
Coverage Extraction
  |
  v
Market Coverage View
  |
  v
Coverage Classification
```

The configured target domain and first-party domains are excluded from competitor discovery.

A page is considered useful competitor coverage when it meaningfully addresses the requested topic; merely mentioning the topic is not sufficient.

### 3. Research Quality

Before strategy generation, the collected research passes through a quality gate.

The quality assessment considers factors such as:

- usable evidence available to the writer
- unsupported-claim proportion
- conflicting claims
- unresolved research gaps
- competitor coverage confidence
- whether competitor research completed successfully

The phase can complete as `SUCCESS`, `DEGRADED`, or `FAILED` depending on the quality and completeness of the available evidence.

### 4. Content Strategy

The strategy layer converts research and market intelligence into an article brief.

The brief can include:

- search intent
- primary and secondary keyword considerations
- semantic coverage
- article structure
- questions that should be answered directly
- important entities and relationships
- authoritative sources to consider
- competitive differentiation or whitespace opportunities

### 5. Article Generation

The content writer uses the research-backed strategy to produce an article draft.

The original user-supplied topic remains the article title in the generated document. An LLM-recommended SEO title is treated as a recommendation rather than silently replacing the requested title.

### 6. DOCX Output

The generated article is saved under `output/` as a Word document.

The document supports formatted headings, paragraphs, lists, emphasis, and supported Markdown structures. When competitor analysis is available, relevant competitor-gap planning information can also be included.

---

## Domain Independence

The engine is designed to work across clients, websites, and industries. A target domain is configuration, not a hard-coded part of the content intelligence pipeline.

```text
                    Content Intelligence Engine
                              |
             +----------------+----------------+
             |                |                |
          Client A         Client B         Client C
             |                |                |
         domain-a.com     domain-b.com     domain-c.com
```

Target configuration is represented by `ClientConfig`:

```text
ClientConfig
├── name
├── domain
└── first_party_sitemaps
```

Target-specific information can include:

- brand name
- target domain
- first-party domains and sitemaps
- editorial rules
- brand terminology
- genuinely necessary industry-specific source configuration

The research, competitor intelligence, evidence, strategy, writing, and output components are reusable across domains.

---

## SEO / AIO / GEO Strategy

The engine treats SEO, AIO, and GEO as complementary strategy components rather than separate content-generation systems.

### SEO

The strategy considers factors such as:

- search intent
- primary keyword
- secondary and semantic terms
- content structure
- title and metadata considerations
- related internal-content opportunities

### AIO

The strategy considers how information can be presented clearly for answer-oriented search experiences, including:

- direct answers
- concise definitions
- explicit question coverage
- answer-first structures
- factual clarity

### GEO

The strategy considers information useful to generative search systems, including:

- important entities
- authoritative sources
- entity relationships
- contextual completeness
- clearly supported factual information

These strategy components remain independent of any specific client or industry.

---

## Research and Evidence

The engine uses source-backed research as the foundation for content planning and generation.

Evidence is treated as more than text generated by an LLM. Retrieved source content and retrieval metadata form the audit trail.

Supporting text may be a faithful paraphrase or summary rather than a verbatim quotation. Evidence validation therefore focuses on whether the source semantically supports the associated claim.

Evidence can be classified as:

- **FULL SUPPORT** — the source clearly supports the claim.
- **PARTIAL SUPPORT** — the source supports only part of the claim.
- **WEAK / AMBIGUOUS** — support is uncertain and requires review.
- **UNSUPPORTED** — the source does not substantiate the claim.

LLM output by itself is not treated as proof of a factual claim.

---

## Architecture

At the application level, the pipeline is organized around distinct responsibilities:

```text
CLI / UI
   |
   v
Content Job + ClientConfig
   |
   v
Research
   |
   +-- First-party discovery
   +-- External search
   +-- Web retrieval
   +-- Evidence extraction
   |
   v
Competitor Intelligence
   |
   +-- Candidate discovery
   +-- Domain exclusion
   +-- Coverage extraction
   +-- Gap / whitespace analysis
   |
   v
Research Quality Gate
   |
   v
Content Strategy
   |
   +-- SEO
   +-- AIO
   +-- GEO
   |
   v
Content Writer
   |
   v
DOCX Output
```

Each major pipeline phase exposes a phase status:

| Status | Meaning |
|---|---|
| `SUCCESS` | The phase produced its expected output with sufficient data. |
| `DEGRADED` | The phase completed with known limitations or partial data. |
| `FAILED` | The phase could not produce usable output. |

This phase status is separate from business conclusions such as `TOPIC_NOT_FOUND`.

---

## LLM Integration

The LLM layer is provider-agnostic. `LLMClient` communicates with an OpenAI-compatible `/chat/completions` endpoint.

```text
LLMClient
   |
   v
LLM_BASE_URL + /chat/completions
   |
   v
Configured LLM_MODEL
```

The endpoint can represent a hosted provider, self-hosted model, gateway, router, or another compatible implementation.

The core engine therefore does not depend on a specific LLM vendor or model.

---

## Search Providers

The search layer supports multiple providers and fallback paths.

```text
Query
 |
 +--> DuckDuckGo
 |
 +--> Google API (when configured)
 |       |
 |       +--> Browser fallback
 |
 +--> Bing browser search
         |
         +--> Legacy API path (when configured)
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

Provider failures are isolated where possible so a failure in one search path does not automatically invalidate usable results from other paths.

---

## Configuration

The application loads `.env` from the project root through `python-dotenv`.

### Target

| Variable | Required | Purpose |
|---|---|---|
| `TARGET_DOMAIN` | Yes | Target website domain. |
| `TARGET_BRAND` | Optional | Human-readable target brand; defaults to the domain. |
| `TARGET_FIRST_PARTY_SITEMAPS` | Optional | Comma-separated first-party sitemap URLs. |

### LLM

| Variable | Required | Purpose |
|---|---|---|
| `LLM_BASE_URL` | Yes in production | OpenAI-compatible LLM API base URL. |
| `LLM_MODEL` | Yes in production | Model name sent to the configured endpoint. |

### Search

| Variable | Required | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | Optional | Google Custom Search API credential. |
| `GOOGLE_CSE_ID` | Optional | Google Custom Search Engine ID. |
| `BING_API_KEY` | Optional / legacy | Legacy Bing API path. Browser search remains available. |

DuckDuckGo search can operate without credentials.

---

## Installation

```bash
git clone https://github.com/subircodz/Content_Intelligence_Engine.git content-intelligence-engine
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

Run the automated tests:

```bash
venv/bin/pytest tests
```

---

## Running the Engine

The target domain can be supplied through environment configuration or overridden through the CLI.

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

### Interactive mode

```bash
venv/bin/python -m intelligence_content_engine.main
```

### Debug mode

```bash
venv/bin/python -m intelligence_content_engine.main --debug "Your Article Topic"
```

Generated article documents are written to `output/`.

---

## Repository Structure

```text
content-intelligence-engine/
├── pyproject.toml
├── README.md
├── .env
├── .gitignore
├── .claude/
│   └── CLAUDE.md
├── docs/
├── output/                      # Generated DOCX files
├── scripts/                     # Developer/live utilities
├── tests/                       # Automated tests
└── src/
    └── intelligence_content_engine/
        ├── main.py              # Pipeline orchestration / CLI
        ├── client.py            # Target-domain configuration
        ├── config.py            # Environment settings
        ├── ui.py
        ├── llm/
        │   └── client.py        # OpenAI-compatible LLM client
        ├── research/
        │   ├── models.py
        │   ├── quality.py       # Research quality assessment
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

## Testing

Run the deterministic automated suite with:

```bash
venv/bin/pytest tests
```

The test suite covers areas including:

- target-domain normalization
- first-party URL detection
- competitor target-domain exclusion
- search-provider fallback and isolation
- URL normalization and deduplication
- research fallback behavior
- phase-status propagation
- competitor coverage extraction
- topic coverage classification
- competitive vs. whitespace routing
- search failure vs. topic-not-found distinction
- research quality-gate paths
- semantic evidence-support validation
- source provenance
- strategy generation
- writing failure handling
- DOCX generation

Live smoke tests under `scripts/` can interact with external web services and are separate from deterministic unit tests.

---

## Project Boundaries

The engine is responsible for research, market intelligence, content strategy, and draft generation.

It does not treat generated text as automatically publishable content, and it does not require competitor coverage for every topic. Market findings, research evidence, infrastructure failures, and generated recommendations remain distinct throughout the pipeline.

---

## License

Licensed under the MIT License.
