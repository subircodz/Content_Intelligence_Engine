# CLAUDE.md — Content Intelligence Engine

Engineering guide for coding agents working on this repository.

## Project Objective

Transform a user-provided article topic/title into a research-backed, SEO/AIO/GEO-optimized DOCX document through market research, competitor analysis, strategy generation, and LLM article writing. The platform is an **editorial production assistant** — every output requires human editorial review before publication.

## Business Goal

Given a target domain and topic:

1. Research the market and competitors.
2. Determine whether the topic is meaningfully covered.
3. If covered, identify genuine competitive content gaps.
4. If not covered, identify market whitespace and research the topic independently.
5. Produce an SEO/AIO/GEO content strategy.
6. Generate a human-reviewable article draft and DOCX.

Never confuse `TOPIC_NOT_FOUND` with search/retrieval failure.

## Domain Independence

The core engine must not assume a specific brand, domain, client, or industry.

Target-specific information belongs in `ClientConfig` or explicit adapters/configuration:

- target brand
- target domain
- first-party domains
- first-party sitemaps
- editorial rules
- brand terminology
- genuinely necessary industry-specific source rules

The core engine owns generic research, competitor discovery, coverage analysis, evidence handling, strategy, writing, and output generation.

## LLM Provider Independence

The engine uses a generic `LLMClient` against an OpenAI-compatible `/chat/completions` endpoint.

Configuration:

- `LLM_BASE_URL`
- `LLM_MODEL`

Do not introduce dependencies on a named LLM provider, router, gateway, or model service into the core engine.

## Core Deliverables

1. Research package: questions, first-party facts, external facts, gaps, claim statuses.
2. Competitor market intelligence and coverage analysis.
3. SEO/AIO/GEO strategy brief (`ContentBrief`).
4. Markdown-formatted article draft.
5. DOCX file in `output/`.

## Pipeline Flow

```text
Content Job + Target Configuration
        ↓
Market / First-Party Research
        ↓
Competitor Discovery
        ↓
Topic Coverage Assessment
        ├── FOUND / PARTIAL → Competitive Gap Analysis
        └── NOT FOUND       → Market Whitespace Analysis
        ↓
SEO / AIO / GEO Strategy
        ↓
Content Writing
        ↓
DOCX
```

Orchestrated by `run_pipeline()` in `src/power_win_content/main.py`.

## Package Layout

| Package/File | Responsibility |
|---|---|
| `main.py` | CLI entry point and phase orchestration |
| `client.py` | `ClientConfig` for target-domain configuration |
| `config.py` | Runtime environment settings |
| `ui.py` | Rich terminal UI |
| `llm/client.py` | Generic OpenAI-compatible LLM client |
| `research/models.py` | Source, claim, evidence, research, and status models |
| `research/researcher.py` | Domain-independent research orchestration |
| `research/domain_researcher.py` | Target-domain research adapter |
| `research/tools/` | Search, fetch, browser, hybrid, and sitemap tools |
| `competitors/` | Competitor discovery and market content analysis |
| `strategy/` | SEO/AIO/GEO content strategy generation |
| `agents/` | Article generation |
| `output/` | DOCX generation |

The Python import package currently retains its historical name. This is separate from product/domain logic and may be renamed later as a package cleanup.

## Research Architecture

- `SourceType.FIRST_PARTY` means a source belongs to the configured target site.
- Claims carry `ClaimStatus`: VERIFIED / PARTIALLY_SUPPORTED / UNSUPPORTED / CONFLICTING / UNCERTAIN.
- First-party facts and external facts are separate collections.
- Inaccessible sources are recorded as research gaps.
- Search/fetch failures must be represented explicitly.
- Research execution remains bounded by source, question, and time limits.

## Competitor Analysis

Competitor analysis must be domain-independent.

The configured target domain and configured first-party domains are excluded from competitor discovery. Do not hard-code a target hostname.

A search result that merely mentions the topic is not sufficient to classify a page as meaningful competitor coverage.

The intended market model is:

```text
Search Results
    ↓
Relevant Competitor Pages
    ↓
Structured Coverage
    ↓
Topic Coverage Assessment
    ↓
FOUND / PARTIAL / NOT FOUND / INSUFFICIENT DATA / SEARCH FAILED
```

Competitor gaps are editorial planning signals, not factual evidence.

## Phase Status

- **SUCCESS** — expected output with sufficient data.
- **DEGRADED** — partial output or known limitations.
- **FAILED** — unusable phase output.

Business coverage status is separate from infrastructure status. `TOPIC_NOT_FOUND` and `SEARCH_FAILED` are not interchangeable.

## Evidence Integrity

LLM-generated excerpts are proposals, not proof.

Before evidence is treated as verified provenance, the system must deterministically validate that the excerpt occurs in the fetched source content and belongs to the claimed source.

Do not rely solely on an LLM prompt to guarantee provenance.

## Search Providers

Search providers are interchangeable infrastructure. Provider failures must be isolated.

Current infrastructure may use DuckDuckGo, Google, and Bing through API/browser paths. CAPTCHA/challenge pages are detected and treated as unavailable. Never bypass CAPTCHA, authentication, anti-bot systems, or access controls.

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `TARGET_DOMAIN` | Yes | Target domain |
| `TARGET_BRAND` | Optional | Target brand name |
| `TARGET_FIRST_PARTY_SITEMAPS` | Optional | First-party sitemap URLs |
| `LLM_BASE_URL` | Yes in production | OpenAI-compatible LLM endpoint |
| `LLM_MODEL` | Yes in production | Model name |
| `GOOGLE_API_KEY` | Optional | Google Custom Search API key |
| `GOOGLE_CSE_ID` | Optional | Google Custom Search Engine ID |
| `BING_API_KEY` | Optional / legacy | Legacy Bing API credential |

Secrets live only in `.env` (gitignored). Never commit, print, or hardcode keys.

## Commands

```bash
venv/bin/pytest tests
venv/bin/python -m power_win_content.main
venv/bin/python -m power_win_content.main "Topic"
venv/bin/python -m power_win_content.main --debug "Topic"
playwright install chromium
```

## Development Rules

1. Run the automated tests before and after changes.
2. Do not add target-specific assumptions to core modules.
3. Do not add named LLM-provider assumptions to the LLM abstraction.
4. Update tests when changing provider, research, model, strategy, or writer behaviour.
5. Preserve the user's original requested title end-to-end.
6. Keep degraded operation visible; never silently convert failure into success.
7. Do not print generated articles to the terminal.
8. Do not expose API keys.
9. Do not bypass access controls.
10. Add tests for every critical invariant introduced or changed.

## Critical Constraints

- **Domain independence is mandatory.**
- **LLM provider independence is mandatory.**
- **Competitor findings are editorial planning information, not evidence.**
- **Search failure must never become confirmed market whitespace.**
- **Insufficient competitor coverage must never be presented as a confident market conclusion.**
- **Generated content requires human editorial review.**
