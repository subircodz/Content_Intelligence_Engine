# Power.win Content Intelligence Platform

An AI-assisted content production system for Power.win. It takes an article topic or title and produces a research-backed DOCX draft with competitor gap analysis and an SEO/AIO/GEO strategy brief.

The platform is an editorial production assistant. Every generated document requires human editorial review before publication.

---

## Objective

Reduce manual research and content preparation for Power.win articles while maintaining:

- Research-backed writing with verifiable sources
- SEO alignment (keywords, headings, search intent)
- AIO alignment (questions and direct answers for AI answer engines)
- GEO alignment (entities and authoritative sources for generative engines)
- Competitor content-gap awareness
- Consistent DOCX output
- Human editorial control at every step

## Business Goal

An editor provides one input — the article title — and receives research, evidence, competitor gaps, strategy, and a formatted article draft ready for human editing and publication.

## What the Application Does

```
User Topic
    |
Multi-Engine Web Search (DuckDuckGo + Google + Bing)
    |
First-Party Source Discovery (power.win sitemaps)
    |
Webpage Fetching (HTTP with Playwright fallback)
    |
Evidence Extraction & Claim Classification (LLM)
    |
Competitor Discovery & Content Gap Analysis
    |
SEO / AIO / GEO Strategy Brief (LLM)
    |
Article Generation (LLM, Markdown)
    |
DOCX Document (+ competitor-gap appendix)
```

## Key Deliverables

| Deliverable | Description |
|---|---|
| Research package | Research questions, first-party Power.win facts, external facts, research gaps, claim statuses |
| First-party evidence | Facts fetched from power.win properties, never fabricated |
| External evidence | Facts from regulatory, government, authoritative, and general web sources |
| Competitor analysis | Discovered competitor pages and their content coverage |
| Content gaps | Missing topics, questions, entities, comparisons, statistics, concerns, angles |
| SEO strategy | Recommended title (secondary), primary keyword, secondary keywords, heading structure, search intent |
| AIO strategy | Questions requiring direct answers, concise definitions |
| GEO strategy | Entities to mention, authoritative sources to reference |
| Article draft | Markdown-formatted article; the user's original title is preserved exactly |
| DOCX document | Word file with proper headings, lists, formatting, and a competitor-gap appendix |
| Phase status reporting | SUCCESS / DEGRADED / FAILED for each pipeline phase |

## Complete Pipeline Architecture

```
CLI / UI  (main.py, ui.py)
    |
    v
Researcher  (research/researcher.py)
    |
    |-- Search Providers  (research/tools/web_search.py)
    |     |-- DuckDuckGoProvider   (HTML scraping, no key)
    |     |-- GoogleSearchProvider (API primary, Playwright fallback)
    |     |-- BingSearchProvider   (Playwright primary, legacy API path)
    |
    |-- SitemapFetcher   (first-party discovery)
    |-- HybridFetcher    (HTTP + Playwright fallback)
    |-- BrowserFetcher   (SPA rendering)
    |
    v
ResearchResult  (claims, evidence, gaps)
    |
    v
CompetitorAnalyzer  (competitors/analyzer.py)
    |
    v
ContentStrategist  (strategy/strategist.py)  ->  ContentBrief
    |
    v
ContentWriterAgent  (agents/content_writer.py)
    |
    v
DOCX Writer  (output/docx_writer.py)
    |
    v
output/<slugified-title>.docx
```

Each phase returns `(result, PhaseStatus)`. A phase failing does not always stop the pipeline; degraded phases continue with whatever data is available.

## Repository Structure

```
power_win_content/
├── pyproject.toml              # Project metadata and dependencies
├── README.md                   # This file
├── .env                        # Local secrets (never committed)
├── .gitignore
├── .claude/
│   └── CLAUDE.md               # Engineering guide for coding agents
├── output/                     # Generated DOCX files (created at runtime)
├── scripts/                    # Developer utilities (not part of the app)
├── tests/                      # Test suite (pytest)
└── src/power_win_content/
    ├── main.py                 # CLI entry point, pipeline orchestration
    ├── config.py               # Settings from environment variables
    ├── ui.py                   # Rich terminal UI
    ├── llm/client.py           # OpenAI-compatible LLM HTTP client
    ├── research/
    │   ├── models.py           # Source, Claim, ResearchResult, enums
    │   ├── researcher.py       # Bounded research orchestration
    │   └── tools/
    │       ├── web_search.py   # Multi-engine search + dedup
    │       ├── web_fetcher.py  # Plain HTTP fetcher
    │       ├── hybrid_fetcher.py
    │       ├── browser_fetcher.py
    │       └── sitemap_fetcher.py
    ├── competitors/
    │   ├── analyzer.py         # Discovery + coverage extraction
    │   └── models.py           # CompetitorSource, ContentGap, CompetitorAnalysis
    ├── strategy/
    │   ├── strategist.py       # ContentBrief generation
    │   └── models.py           # SEO/AIO/GEO strategy models
    ├── agents/
    │   └── content_writer.py   # Markdown article generation
    └── output/
        └── docx_writer.py      # Markdown -> DOCX conversion
```

## Prerequisites

| Requirement | Detail |
|---|---|
| Python | >= 3.13 |
| pip | Bundled with Python |
| Network access | Required for search, fetching, and the LLM API |
| LLM provider | Any OpenAI-compatible `/chat/completions` endpoint |
| Playwright Chromium | Installed once via `playwright install chromium` |

Dependencies (installed automatically): `httpx`, `python-docx`, `python-dotenv`, `pydantic`, `playwright`, `rich`; dev group adds `pytest`.

## Python / Virtual Environment Setup

The project uses a standard virtual environment named `venv` in the project root.

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

## Playwright Browser Installation

One-time install of the Chromium browser used for SPA rendering and search fallback:

```bash
playwright install chromium
```

## Environment Configuration

The application loads a `.env` file from the project root via python-dotenv. Every variable below exists in the actual configuration code (`config.py`, `research/tools/web_search.py`).

## Required API Credentials

There is exactly one required external dependency at runtime: a reachable LLM API. Without it, research planning falls back to deterministic defaults, strategy degrades to defaults, and article writing fails.

## LLM Provider Configuration

The application calls any OpenAI-compatible chat completions endpoint. Configure it through these variables (actual names used by the code):

| Variable | Required | Purpose | Example placeholder |
|---|---|---|---|
| `OMNIROUTE_BASE_URL` | Yes (has a localhost default) | Base URL of the OpenAI-compatible LLM API | `https://llm.example.com/v1` |
| `OMNIROUTE_MODEL` | Yes (default `auto`) | Model name sent in requests | `gpt-4o` |

Security note: the base URL may embed authentication depending on your provider. Treat it like a secret — do not commit real values.

## Search Provider Configuration

| Variable | Required | Purpose |
|---|---|---|
| *(none)* | — | DuckDuckGo works with no credentials |
| `GOOGLE_API_KEY` | Optional | Google Custom Search JSON API key |
| `GOOGLE_CSE_ID` | Optional | Google Custom Search Engine ID (both values needed for Google API search) |
| `BING_API_KEY` | Optional / legacy | The Bing Search API was retired on 2025-08-11. Bing search uses the built-in Playwright method; only configure this if you hold a pre-retirement key that still works |

No provider other than the LLM is mandatory. With zero search credentials the pipeline runs using DuckDuckGo alone.

## Step-by-Step First Run

Copy-paste these commands in order. Linux/macOS assumed; adapt paths for Windows.

```bash
# 1. Get the project
git clone <repository-url> power_win_content
cd power_win_content

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install the project and dependencies
pip install -e .

# 4. Install the Playwright Chromium browser
playwright install chromium

# 5. Create your .env file (placeholders shown — use your own values)
cat > .env << 'EOF'
OMNIROUTE_BASE_URL=https://llm.example.com/v1
OMNIROUTE_MODEL=gpt-4o
# Optional Google Custom Search:
# GOOGLE_API_KEY=your-google-api-key
# GOOGLE_CSE_ID=your-search-engine-id
EOF

# 6. Run the test suite (should pass fully)
venv/bin/pytest tests

# 7. Generate an article
venv/bin/python -m power_win_content.main "How We Evaluate Online Casinos"
```

When the run finishes, the DOCX path is printed under `[SUCCESS] DOCX Generation ...`. Files land in:

```bash
ls output/
```

## How to Generate an Article

Interactive mode (prompts for the topic):

```bash
venv/bin/python -m power_win_content.main
```

Command-line topic:

```bash
venv/bin/python -m power_win_content.main "How We Evaluate Online Casinos: Power.win Editorial & Review Methodology"
```

The generated article is **not** printed to the terminal. Only the DOCX file path is displayed.

## How Competitor Content Gap Analysis Works

1. Search engines are queried for the topic.
2. Candidate URLs are filtered (power.win itself, social media, and search-engine domains are excluded).
3. Top candidate pages are fetched.
4. An LLM extracts each page's coverage: headings, questions answered, entities, statistics, sections, angles.
5. Coverage across competitors is compared to produce gap lists: missing topics, questions, entities, comparisons, statistics, user concerns, recommended angles, and topics competitors cover that ours does not.
6. Gaps flow into the strategy brief and influence heading structure and editorial angles.

**Gaps are planning intelligence, not verified facts.** They describe what competitors cover — not whether those claims are true.

## How Research Works

1. An LLM drafts a small research plan (up to 3 questions). If planning fails/times out, a deterministic fallback plan is used and the phase is marked DEGRADED.
2. First-party sources are discovered from power.win sitemaps; external sources come from multi-engine search.
3. Pages are fetched over HTTP first, with a Playwright-rendered fallback for JavaScript-heavy sites. Failed URLs are cached and skipped.
4. An LLM extracts claims with evidence snippets and classifies each claim: `verified`, `partially_supported`, `unsupported`, `conflicting`, or `uncertain`.
5. Sources that block automation (HTTP 403), render empty SPA shells, time out, or contain insufficient content are recorded as **research gaps** — the pipeline continues without them.
6. Execution is bounded (~55 s wall clock, max ~12 sources) so research always terminates.

## How Search Provider Fallback Works

Order per query:

1. **DuckDuckGo** — always queried; HTML scraping, no credentials needed.
2. **Google** — if `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` are set, the Custom Search API is called. Valid results end here (Playwright is not invoked). On missing credentials, HTTP errors, timeouts, or empty responses, the Playwright browser fallback renders google.com/search.
3. **Bing** — the public Bing Search API was retired (2025-08-11), so Playwright rendering of bing.com/search is the normal path. A legacy API attempt happens only if `BING_API_KEY` is set.

Then:

- Results from all providers are merged, normalized (lowercase scheme/host, fragments/trailing slashes stripped), and deduplicated — the same URL appears once regardless of how many providers returned it.
- Limits: 10 results per provider, 15 combined.
- Each result keeps its origin in `Source.provider` (`duckduckgo`, `google_api`, `google_playwright`, `bing_api`, `bing_playwright`).
- If any single provider fails or throws, the others still run. Search never aborts the pipeline.

**CAPTCHA/challenge policy:** when Google or Bing serve a CAPTCHA, consent wall, or block page instead of results, the application detects it, records nothing, and returns no results for that provider. It does **not** solve, bypass, or circumvent CAPTCHAs, anti-bot systems, logins, or access controls of any kind. In practice this means browser-based Google/Bing search can return zero results on challenged queries; configured APIs and DuckDuckGo remain the reliable paths.

## Understanding SUCCESS / DEGRADED / FAILED

Every phase reports one status:

| Status | Meaning | Examples |
|---|---|---|
| **SUCCESS** | Phase produced expected results | Evidence extracted, competitors analyzed, DOCX written |
| **DEGRADED** | Phase completed with partial/limited results; pipeline continues | Fallback research plan used; zero competitor sources found; strategy fell back to default values; limited evidence collected |
| **FAILED** | Phase could not produce usable output | Strategy brief missing; writer produced no text; DOCX could not be written |

Overall pipeline status equals the worst phase status. A DEGRADED result is not a crash — it means some capability was unavailable and the output has known holes. Review degraded output extra carefully before publication.

## DOCX Output

- Location: `output/` directory (created automatically).
- Filename: the title slugified — lowercased, non-alphanumeric characters replaced with hyphens, duplicates collapsed. Example: `"How We Evaluate Online Casinos"` → `how-we-evaluate-online-casinos.docx`.
- Title handling: the user's original title becomes the document Heading 0 and is never replaced. The SEO "recommended title" inside the strategy brief is a suggestion only.
- Contents: Word headings (H1–H6 from Markdown `#` levels), paragraphs, bullet and numbered lists, bold/italic inline formatting, inline code in Courier New, blockquotes.
- Appendix: when competitor analysis succeeded, a final page titled "Appendix: Competitor Content Gap" lists analyzed competitors and all identified gaps. It is explicitly marked as internal editorial planning material.

## Debug Mode

```bash
venv/bin/python -m power_win_content.main --debug "Your Topic"
```

Normal mode sets logging to WARNING and silences research/fetch/LLM/competitor/strategy loggers plus `httpx`/`httpcore`, keeping the terminal clean (spinners, phase lines, tables).

`--debug` enables DEBUG-level logging: search queries and per-provider results, HTTP fetch attempts and status codes, Playwright operations, LLM request failures, strategy parsing steps. Use it to diagnose why sources or providers returned nothing.

## Testing

```bash
venv/bin/pytest tests
```

Current verified state: **195 passed, 0 failed**.

Coverage highlights: multi-provider search and fallback ordering, API-success-skips-Playwright assertions, CAPTCHA/challenge detection and graceful empty results, cross-provider deduplication, provider failure isolation, Playwright context lifecycle and cleanup, research plan fallback, PhaseStatus propagation (research/competitor/strategy/writing/DOCX), Markdown→DOCX conversion, LLM client null-safety, UI display functions.

## Live Smoke Tests

Developer utilities live in `scripts/` and are not required for production use:

- `scripts/test_e2e.py` — end-to-end pipeline exercise
- `scripts/test_live_research.py` — research-layer exercise against live web sources
- `scripts/browser_fetch_demo.py` — single-page fetch demonstration

Run them only when you intend to hit live network services.

## Troubleshooting

| Problem | Likely Cause | Solution |
|---|---|---|
| Writing phase fails / pipeline ends without DOCX | LLM endpoint unreachable, slow, or returning empty content | Verify `OMNIROUTE_BASE_URL` reachability and model name; retry; check with `--debug` |
| Strategy/research marked DEGRADED | Planning or parsing LLM call timed out; fallbacks used | Expected under LLM instability; rerun, or check endpoint health |
| Google API results absent | Credentials missing — or the API key's cloud project lacks Custom Search JSON API enabled (observed as HTTP 403 "project does not have access") | Set both `GOOGLE_API_KEY` and `GOOGLE_CSE_ID`; enable the Custom Search JSON API for the key's project |
| Google/Bing Playwright returns zero results | CAPTCHA or challenge page detected | Expected behaviour; protections are never bypassed. Rely on DuckDuckGo and/or configured APIs |
| Bing API ignored entirely | API retired 2025-08-11; Playwright is the supported path | Do not obtain a new Bing key; configure Google instead if you need a second API provider |
| Many HTTP 403 fetch warnings visible | Running with `--debug` (normal mode suppresses them) | None needed; blocked sites are recorded as research gaps automatically |
| SPA pages yield no evidence | Page requires heavy JS hydration; renderer exited early or content stayed empty | Recorded as research gaps; try a different topic phrasing |
| `ModuleNotFoundError: playwright` | Dependencies not installed | `pip install -e .` inside the activated venv |
| `playwright install` fails | Missing system libraries for Chromium | Install OS dependencies (e.g. `playwright install-deps chromium` on Debian/Ubuntu) and retry |
| `Executable doesn't exist` from Playwright | Chromium browser not installed | `playwright install chromium` |
| Zero research facts overall | All providers blocked AND LLM unavailable, or topic too narrow | Check LLM health first, then rerun; inspect with `--debug` |
| DOCX not created despite writing success | `output/` not writable | Fix permissions on the output directory |
| Empty topic prompt loops | Blank input at interactive prompt | Type a non-empty title; Ctrl+C cancels cleanly |

## Security / Secrets

- Secrets belong in `.env` only. `.env` is gitignored — never commit it.
- Never hardcode keys in source, tests, scripts, or documentation.
- Never print secrets; error paths report status codes and safe messages only.
- The application never bypasses CAPTCHA, anti-bot measures, authentication, or access controls, and respects provider rate limits and robots/access restrictions.
- Generated content is a draft: human editorial review and fact verification are mandatory before publication.

## Production Deployment Checklist

- [ ] Python >= 3.13 available on the host
- [ ] Virtual environment created; `pip install -e .` completed
- [ ] `playwright install chromium` completed (plus OS deps if headless Linux)
- [ ] `.env` present with working `OMNIROUTE_BASE_URL` / `OMNIROUTE_MODEL`
- [ ] LLM endpoint reachable from the host
- [ ] Optional: `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` configured and the Custom Search JSON API enabled for the key's project
- [ ] `venv/bin/pytest tests` fully green on the host
- [ ] `output/` directory writable by the runtime user
- [ ] `.env` excluded from backups/images where feasible; no secrets in logs
- [ ] Editorial review process defined for generated documents

## Future Extension Points

- Additional search providers (pluggable provider list in `web_search.py`)
- Persistent caching of search results and fetched pages
- Source-quality scoring ahead of claim extraction
- Richer competitor comparison views
- CMS/publication integrations consuming the generated DOCX or Markdown
- Editorial approval workflow states around `PhaseStatus`
- Multilingual content support
