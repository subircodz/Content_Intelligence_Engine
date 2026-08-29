# Domain Independence

The engine is configured around a target site rather than a hard-coded brand or industry.

## Configuration

Set the target through environment variables:

```env
TARGET_BRAND=Example
TARGET_DOMAIN=example.com
TARGET_FIRST_PARTY_SITEMAPS=https://example.com/sitemap.xml,https://docs.example.com/sitemap.xml
```

Or provide the target at runtime:

```bash
python -m power_win_content.main --target-brand Example --target-domain example.com \
  --first-party-sitemap https://example.com/sitemap.xml \
  "Article topic"
```

## Boundary

`ClientConfig` is the configuration boundary for target identity. Core research, competitor discovery, strategy, and writing must consume target configuration rather than embed a client domain or brand.

First-party knowledge is optional. A target may provide zero, one, or multiple sitemaps and additional first-party domains.

## LLM Boundary

The LLM layer is provider-independent. Configure any OpenAI-compatible `/chat/completions` endpoint through:

```env
LLM_BASE_URL=https://llm.example.com/v1
LLM_MODEL=your-model
```

No named LLM provider, gateway, router, or model service belongs in the core engine.

## Engineering Rule

A new target should require configuration or an explicit adapter, not modifications to the core research, competitor, strategy, or writing modules.
