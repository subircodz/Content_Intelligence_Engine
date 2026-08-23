# CLAUDE.md — Power.win Content Intelligence Platform

Engineering guide for coding agents working on this repository.

## Project Objective

Transform a user-provided article topic/title into a research-backed, SEO/AIO/GEO-optimized DOCX document through automated research, competitor gap analysis, strategy generation, and LLM article writing. The platform is an **editorial production assistant** — every output requires human editorial review before publication.

## Business Goal

A repeatable content-production system for Power.win that reduces manual research while maintaining: verified evidence, SEO alignment, AIO (AI answer engine) alignment, GEO (generative engine) alignment, competitor-gap awareness, consistent DOCX output, and human editorial control.

## Core Deliverables

1. Research package (questions, first-party facts, external facts, gaps, claim statuses)
2. Competitor content-gap analysis
3. SEO / AIO / GEO strategy brief (`ContentBrief`)
4. Markdown-formatted article draft (user's original title preserved)
5. DOCX file in `output/` with competitor-gap appendix

## Pipeline Flow

```
User Topic → Multi-Engine Research → First-Party Evidence → Competitor Discovery
→ Competitor Content Gap Analysis → SEO/AIO/GEO Strategy → Content Writing → DOCX
```

Orchestrated by `run_pipeline()` in `src/power_win_content/main.py`:
Research → Competitors → Strategy → Writing → DOCX, each phase producing a
`PhaseStatus` (SUCCESS / DEGRADED / FAILED). Overall pipeline status is the
minimum of all phase statuses (FAILED < DEGRADED < SUCCESS).

## Package Layout (`src/power_win_content/`)

| Package/File | Responsibility |
|---|---|
| `main.py` | CLI entry point (`python -m power_win_content.main [topic] [--debug]`), phase orchestration |
| `config.py` | `Settings` — loads env vars via python-dotenv |
| `ui.py` | Rich terminal UI: banner, prompts, phase results, summary tables |
| `llm/client.py` | `LLMClient` — OpenAI-compatible `/chat/completions` HTTP client; null/empty response safety |
| `research/models.py` | Pydantic models: `Source`, `Claim`, `Evidence`, `ResearchResult`, `ResearchGap`, enums `SourceType`, `ClaimStatus`, `PhaseStatus`, `InformationNature` |
| `research/researcher.py` | Bounded research orchestration (plan → search → fetch → extract claims); deterministic fallback plan when planning LLM fails |
| `research/tools/web_search.py` | Multi-engine search: DuckDuckGo, Google, Bing providers + Playwright browser manager + dedup |
| `research/tools/web_fetcher.py` | Plain HTTP fetcher |
| `research/tools/hybrid_fetcher.py` | HTTP + Playwright fallback fetcher with failed-URL caching |
| `research/tools/browser_fetcher.py` | Playwright renderer with SPA early-exit protection |
| `research/tools/sitemap_fetcher.py` | First-party source discovery from Power.win sitemaps |
| `competitors/analyzer.py`, `models.py` | Competitor discovery (excludes power.win/social/search domains), page analysis, `ContentGap` models |
| `strategy/strategist.py`, `models.py` | `ContentBrief` generation: `SEOStrategy`, `AIOStrategy`, `GEOStrategy`; defaults on parse failure → DEGRADED |
| `agents/content_writer.py` | Markdown article generation from `ContentBrief` + research evidence |
| `output/docx_writer.py` | Markdown→DOCX conversion, slug filenames, competitor appendix |

Empty placeholder directories (`documents/`, `editorial/`, `fact_check/`, `seo/`) are reserved for future work — do not assume they contain code.

## Research Architecture & Source Classification

- Sources classified by `_classify_source_type()` in `web_search.py`: FIRST_PARTY (power.win), REGULATORY (gambling regulators), GOVERNMENT, PRIMARY, AUTHORITATIVE, SECONDARY, GENERAL, UNKNOWN.
- Claims carry `ClaimStatus`: VERIFIED / PARTIALLY_SUPPORTED / UNSUPPORTED / CONFLICTING / UNCERTAIN.
- Inaccessible sources (403, SPA shells, timeouts) are recorded as `ResearchGap`s — never retried endlessly, never bypassed.
- Research is bounded: max 3 plan questions, 2 sources/question, 12 total sources, ~55 s wall clock.

## Search Providers

| Provider | Method | Credentials | Fallback |
|---|---|---|---|
| DuckDuckGo | HTML scraping | None required | Always available |
| Google | Custom Search API primary | `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` | Playwright browser search on missing/failing API |
| Bing | Legacy API path only (API retired 2025-08-11) | `BING_API_KEY` optional/legacy | Playwright is the primary Bing method |

- Google API success ⇒ Playwright NOT called. API failure/missing creds ⇒ Playwright attempted.
- CAPTCHA/challenge/consent pages are detected (`_is_search_challenge_page`) and return empty results. NEVER bypass them.
- Results deduplicated across providers by URL normalization (lowercase scheme/host, strip fragments/trailing slashes); max 10/provider, 15 combined.
- Provider attribution preserved in `Source.provider` (e.g. `duckduckgo`, `google_api`, `google_playwright`, `bing_api`, `bing_playwright`).
- One provider failing must never terminate search or the pipeline.

## PhaseStatus Semantics

- **SUCCESS** — phase produced expected results.
- **DEGRADED** — partial results (fallback research plan used, zero competitors found, default strategy values, limited evidence). Pipeline continues.
- **FAILED** — phase unusable (strategy/writing/DOCX failure stops pipeline; research failure yields no result object).

Degraded operation must be visibly reported in CLI output — never silently swallowed.

## Competitor Analysis Behaviour

Discovers candidate competitor URLs via search (excluding power.win, social media, search engines), fetches pages, uses LLM to extract coverage (headings, questions, entities, statistics, angles), then produces `ContentGap` lists. Gaps feed the strategist as **editorial planning signals only — they are NOT verified evidence**.

## DOCX Generation

`save_article_docx(article_markdown, title, output_dir="output", competitor_analysis=None)`:
filename = slugified title (lowercase, hyphens). Title becomes document Heading 0.
Markdown headings/bullets/numbered lists/bold/italic/code/blockquotes supported.
Competitor gap appendix added on a separate page when analysis provided.
Returns `None` on empty article or write failure.

## LLM Abstraction

`LLMClient(base_url, model)` posts to `{base_url}/chat/completions` (OpenAI-compatible).
Configured via `Settings`: `OMNIROUTE_BASE_URL`, `OMNIROUTE_MODEL`.
Timeout 60 s, retries disabled by default. Null/empty LLM content is converted to empty string safely.

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `OMNIROUTE_BASE_URL` | Yes (has localhost default) | LLM API base URL (OpenAI-compatible) |
| `OMNIROUTE_MODEL` | Yes (default `auto`) | Model name |
| `GOOGLE_API_KEY` | Optional | Google Custom Search API key |
| `GOOGLE_CSE_ID` | Optional | Google Custom Search Engine ID |
| `BING_API_KEY` | Optional/legacy | Pre-retirement Bing key; not expected |

Secrets live only in `.env` (gitignored). Never commit, print, or hardcode keys.

## Commands

```bash
venv/bin/pytest tests                          # run full test suite
venv/bin/python -m power_win_content.main      # interactive mode
venv/bin/python -m power_win_content.main "Topic"   # CLI topic
venv/bin/python -m power_win_content.main --debug "Topic"  # verbose diagnostics
playwright install chromium                    # one-time browser install
```

Normal CLI mode suppresses module logging; `--debug` enables detailed diagnostics.

## Development Rules

1. Run `venv/bin/pytest tests` before and after changes; keep it green.
2. Do not redesign architecture without explicit instruction.
3. Match existing code style; no comments unless requested.
4. Update tests when changing provider behaviour; keep provider isolation guarantees.

## Critical Constraints

- **Never fabricate Power.win first-party facts.** First-party evidence must come from fetched power.win sources.
- **Competitor findings are editorial planning information, not evidence.**
- **Preserve the user's original title** end-to-end; SEO recommended title is secondary only.
- **Do not print generated articles to the terminal** — only the DOCX path.
- **Do not expose API keys** in logs, output, docs, or tests.
- **Do not bypass CAPTCHA/challenge/auth/access controls** — detect and degrade gracefully.
- **Report degraded operation clearly** — never silently swallow failures.
