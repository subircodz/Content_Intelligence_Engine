# Content Intelligence Engine — Project Handover & Operations Guide

**Release:** 0.2.0  
**Current commit:** 45478cae73e87f79daf22fe70d65b169a7a117a5  
**Repository:** `subircodz/Content_Intelligence_Engine`

## 1. Executive Summary

Content Intelligence Engine is a domain-independent content research, intelligence, strategy, and article-drafting application.

A user provides:
- a target website/client;
- an article topic;
- an optional output language.

The engine researches the topic, gathers first-party and external evidence, identifies meaningful competitor coverage, detects content gaps or market whitespace, evaluates research quality, creates an SEO/AIO/GEO content brief, generates an article draft with an OpenAI-compatible LLM, and saves the result as a DOCX file.

The generated article is intentionally a **human-reviewable draft**. The system does not automatically publish content.

## 2. What the Project Delivers

The system provides:
1. Topic research.
2. First-party website/sitemap research.
3. External web research.
4. Competitor discovery and coverage analysis.
5. Content-gap and market-whitespace identification.
6. Research quality gating.
7. SEO/AIO/GEO content strategy.
8. AI-assisted article drafting.
9. English, Telugu, and Tamil output.
10. DOCX document generation.
11. CLI operation.
12. Automated deterministic tests and CI checks.
13. Production/security guidance.

## 3. End-to-End Workflow

```text
Target + Topic + Language
          |
          v
       Research
          |
          v
 Competitor Intelligence
          |
          v
  Research Quality Gate
          |
          v
  SEO / AIO / GEO Brief
          |
          v
   Article Generation
          |
          v
       DOCX Output
```

### Research

The research layer can use:
- first-party sitemap discovery;
- external search providers;
- HTTP retrieval;
- Playwright/browser fallback for JavaScript-heavy pages;
- source normalization;
- evidence and claim extraction.

### Competitor Intelligence

Search results are treated as candidate sources. The engine filters out the configured target domain and identifies meaningful competitor coverage rather than treating every mention as a competitor.

If meaningful competitor coverage exists, the system looks for:
- missing topics;
- unanswered questions;
- missing entities;
- weak/shallow coverage;
- useful comparison opportunities;
- evidence opportunities;
- differentiation angles.

If meaningful competitor coverage does not exist, the system records market whitespace rather than inventing a competitor-gap analysis.

### Research Quality Gate

The quality gate evaluates evidence availability, unsupported claims, conflicts, research gaps, and competitor-analysis confidence.

Possible outcomes:
- PASS;
- DEGRADED;
- FAIL.

A failed quality gate prevents article generation.

### Strategy

The strategy phase produces an article brief covering search intent, keyword considerations, semantic coverage, structure, questions, entities, sources, and differentiation/whitespace opportunities.

### Writing

The writer generates the article from the research-backed brief. Verified facts, numbers, dates, names, entities, and evidence are instructed to be preserved.

LLM-generated prose is not treated as factual evidence by itself.

### DOCX

The final article is written to the `output/` directory. English, Telugu, and Tamil output use appropriate Unicode-capable font hints. Telugu files use a `-telugu.docx` suffix and Tamil files use a `-tamil.docx` suffix.

## 4. Supported Languages

- English — default.
- Telugu.
- Tamil.

Language can be selected using the CLI or environment configuration.

The language setting controls generated article/document language. Research and evidence validation remain conceptually language-independent.

## 5. Prerequisites

Recommended runtime:
- Python 3.13 or newer.
- Internet access for research/search.
- Chromium installed through Playwright.
- Access to an OpenAI-compatible LLM endpoint for article generation.
- Optional search API credentials.

## 6. Installation

```bash
git clone https://github.com/subircodz/Content_Intelligence_Engine.git content-intelligence-engine
cd content-intelligence-engine

python3 -m venv venv
source venv/bin/activate

pip install -e .
playwright install chromium
```

## 7. Configuration

Copy `.env.example` to `.env` and configure the target and LLM.

Example:

```text
TARGET_BRAND=Example
TARGET_DOMAIN=example.com
TARGET_FIRST_PARTY_SITEMAPS=https://example.com/sitemap.xml

CONTENT_LANGUAGE=english

LLM_BASE_URL=https://llm.example.com/v1
LLM_MODEL=your-model
LLM_API_KEY=
```

Optional search configuration:

```text
GOOGLE_API_KEY=
GOOGLE_CSE_ID=
BING_API_KEY=
```

Never commit real API keys or other secrets to Git.

## 8. How to Run

### Using environment configuration

```bash
venv/bin/python -m intelligence_content_engine.main "Your Article Topic"
```

### Specify target from the command line

```bash
venv/bin/python -m intelligence_content_engine.main \
  --target-domain example.com \
  --target-brand "Example" \
  --first-party-sitemap https://example.com/sitemap.xml \
  "Your Article Topic"
```

Repeat `--first-party-sitemap` when more than one sitemap is required.

### Telugu

```bash
venv/bin/python -m intelligence_content_engine.main \
  --language telugu "మీ ఆర్టికల్ అంశం"
```

### Tamil

```bash
venv/bin/python -m intelligence_content_engine.main \
  --language tamil "உங்கள் கட்டுரை தலைப்பு"
```

### Interactive mode

```bash
venv/bin/python -m intelligence_content_engine.main
```

The application prompts for a topic when no topic is supplied.

### Debug mode

```bash
venv/bin/python -m intelligence_content_engine.main --debug "Your Article Topic"
```

## 9. Output

Successful runs produce a Word document under:

```text
output/
```

The document contains the generated article with supported headings, paragraphs, lists, and emphasis.

A successful run exits with status 0. A failed pipeline returns a non-zero status, allowing a scheduler or automation platform to detect failure.

## 10. Important Configuration Variables

| Variable | Required | Purpose |
|---|---|---|
| TARGET_DOMAIN | Yes unless CLI target is supplied | Target website |
| TARGET_BRAND | Optional | Display/client brand |
| TARGET_FIRST_PARTY_SITEMAPS | Optional | First-party sitemap URLs |
| CONTENT_LANGUAGE | Optional | english, telugu, or tamil |
| LLM_BASE_URL | Required for production | OpenAI-compatible API base URL |
| LLM_MODEL | Required for production | Model name |
| LLM_API_KEY | Provider-dependent | LLM credential |
| GOOGLE_API_KEY | Optional | Google search |
| GOOGLE_CSE_ID | Optional | Google Custom Search Engine |
| BING_API_KEY | Optional/legacy | Legacy Bing path |

CLI `--language` overrides `CONTENT_LANGUAGE`.

## 11. Technology Stack

- Python 3.13+
- Pydantic
- httpx
- python-dotenv
- Playwright
- SeleniumBase
- BeautifulSoup
- python-docx
- Rich
- pytest
- pytest-asyncio
- Ruff
- setuptools

The LLM integration is provider-agnostic at the application boundary and expects an OpenAI-compatible chat-completions endpoint.

## 12. Repository Structure

```text
src/intelligence_content_engine/
├── main.py
├── client.py
├── config.py
├── language.py
├── ui.py
├── llm/
├── research/
├── competitors/
├── strategy/
├── agents/
└── output/

tests/
scripts/
docs/
output/
pyproject.toml
.env.example
SECURITY.md
```

## 13. Testing and CI

Deterministic tests can be run with:

```bash
venv/bin/pytest -q --ignore=tests/test_llm_client.py
```

Source compilation:

```bash
python -m compileall -q src
```

Ruff:

```bash
ruff check src
```

The separate LLM smoke test requires a reachable compatible LLM service and real runtime configuration, so it is not part of deterministic CI.

## 14. Security and Operational Controls

The application includes:
- outbound URL safety checks;
- bounded LLM retries/backoff;
- response validation;
- controlled prompt length;
- resource cleanup;
- non-zero failure exits;
- separation of secrets from source configuration.

For production:
- inject secrets through the deployment platform;
- restrict outbound network egress where practical;
- apply CPU, memory, timeout, and job limits;
- centralize logs;
- isolate jobs;
- retain human editorial review before publication.

Do not expose the CLI directly as an unauthenticated public web service without an API/authentication layer, request quotas, resource limits, and job isolation.

## 15. Failure Handling

The system distinguishes business findings from infrastructure failures.

Examples:
- `TOPIC_NOT_FOUND` means research found no meaningful competitor coverage.
- `SEARCH_FAILED` means retrieval infrastructure failed.
- `INSUFFICIENT_DATA` means available evidence was not sufficient for a confident conclusion.

A failed quality gate blocks article generation.

Transient LLM errors are retried with bounded backoff. Empty or malformed LLM responses are not silently accepted.

## 16. Human Review Requirement

The system is an AI-assisted drafting tool, not an autonomous publishing system.

Before publication, a human should review:
1. factual accuracy;
2. claims and source support;
3. numerical values;
4. names and dates;
5. legal/regulatory statements;
6. brand claims;
7. language quality;
8. SEO/title suitability;
9. originality and editorial quality;
10. final formatting.

This is especially important for Telugu and Tamil output because language generation quality can vary by model and domain.

## 17. Production Validation Procedure

Before moving the project to a new production environment or changing the LLM/provider/browser version, perform a controlled end-to-end run.

Verify:
1. target configuration loads;
2. research returns usable sources;
3. quality gate behaves correctly;
4. competitor analysis handles partial failures;
5. strategy generation completes;
6. article generation returns non-empty content;
7. DOCX opens correctly;
8. requested language is used;
9. successful jobs exit 0;
10. failed jobs exit non-zero.

Record the LLM/provider/model versions used for validation.

## 18. Known Limitations

1. Real-world research quality depends on search-provider availability, target websites, network conditions, and the configured LLM.
2. Browser fallback can be slower and can fail on sites with strong anti-bot controls.
3. The application cannot guarantee that generated prose is factually correct merely because it was produced from research; human review remains required.
4. Telugu and Tamil output are supported, but language quality depends partly on the selected LLM.
5. The deterministic CI suite does not prove that a live external LLM provider is reachable.
6. A production acceptance test should therefore include a live provider-backed end-to-end run.

## 19. Handover Procedure

The incoming project owner should:

### Step 1 — Obtain repository access
Open the repository and verify the current main branch.

### Step 2 — Prepare runtime
Install Python 3.13+, create a virtual environment, install the package, and install Chromium.

### Step 3 — Configure secrets
Create `.env` from `.env.example`. Do not commit it.

### Step 4 — Configure client
Set target brand, target domain, and first-party sitemaps.

### Step 5 — Configure LLM
Set the OpenAI-compatible base URL, model, and required API key.

### Step 6 — Run a controlled English test
Generate one known test topic and verify the DOCX.

### Step 7 — Run Telugu/Tamil tests
Run one topic in Telugu and one in Tamil if those outputs are required.

### Step 8 — Review logs and output
Check research counts, competitor results, warnings, quality status, and generated document.

### Step 9 — Establish operational ownership
Define who owns:
- LLM credentials;
- search credentials;
- target-domain configuration;
- deployment environment;
- output storage;
- editorial approval;
- incident handling.

## 20. Final Project Status

Release 0.2.0 contains multilingual content output and localized project documentation.

The current main branch includes the final CLI syntax repair after the multilingual release work.

**Current commit:** `45478cae73e87f79daf22fe70d65b169a7a117a5`

The project has deterministic automated validation and production-operation documentation. A live provider-backed end-to-end production run still needs to be performed in the receiving environment before operational acceptance.

## 21. Reference Documentation

- `README.md` — project overview and developer usage.
- `docs/LANGUAGES.md` — multilingual output contract.
- `docs/PRODUCTION.md` — production operations.
- `SECURITY.md` — security guidance.
- `docs/README.te.md` — Telugu project documentation.
- `docs/README.ta.md` — Tamil project documentation.
