# Production Runbook

## Scope
The application is a production-oriented CLI/content pipeline. It produces human-reviewable DOCX drafts; it does not publish content automatically.

## Required configuration
Set:
- TARGET_DOMAIN
- LLM_BASE_URL
- LLM_MODEL

Set TARGET_BRAND and TARGET_FIRST_PARTY_SITEMAPS when applicable.

Use `.env.example` as the configuration template. Store real credentials in the runtime secret manager, not in Git.

## Installation
Use a supported Python 3.13 runtime:

    python -m venv .venv
    . .venv/bin/activate
    pip install -e .
    playwright install chromium

The SeleniumBase/Chrome fallback also requires a compatible Chrome/Chromium runtime on systems where the Cloudflare fetcher is exercised.

## Pre-release checks

    python -m compileall -q src
    pytest -q --ignore=tests/test_llm_client.py

The excluded LLM smoke test requires a reachable compatible LLM service. Run it separately in an environment that provides that service.

## Runtime
Example:

    content-intelligence-engine --target-domain example.com --target-brand Example "Your article topic"

A successful run produces a DOCX under `output/`. A failed pipeline exits with a non-zero status so schedulers and automation can detect failure.

## Failure policy
- A failed research quality gate stops generation.
- Empty or malformed LLM responses fail rather than being silently accepted.
- Transient LLM failures are retried with bounded backoff.
- One failed search provider does not automatically invalidate other providers.
- Unsafe outbound URLs are rejected.
- Browser and HTTP resources are closed after use.

## Production deployment guidance
Run the CLI as a short-lived job or worker with:
- restricted outbound network egress
- explicit CPU/memory/time limits
- a writable output volume
- secret injection through the platform
- centralized logs
- job-level retry policy outside the application
- a human editorial review step before publication

Do not expose the CLI directly as a public web endpoint without adding an authenticated API layer, request quotas, per-job isolation, and stronger resource controls.

## Live validation
Before accepting a new provider/model/browser version, execute a controlled end-to-end run against a test target and verify:
1. research returns sources;
2. the quality gate behaves as expected;
3. competitor analysis handles failures/degraded coverage;
4. strategy generation completes;
5. article generation returns non-empty text;
6. the DOCX opens and contains the expected headings/content;
7. the process exits 0 on success and non-zero on failure.

Record the model/provider versions used for the validation run.
