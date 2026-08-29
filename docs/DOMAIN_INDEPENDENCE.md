# Domain Independence

The engine is now configured around a target site rather than hard-coded to a single brand.

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

`ClientConfig` is the only configuration object the pipeline needs to know the target brand/domain. Core research, competitor discovery, strategy, and writing are expected to consume this configuration rather than embed a client domain.

First-party knowledge is optional. A client may provide zero, one, or multiple sitemaps and additional first-party domains.

## Current transition

The existing research model retains the legacy `power_win_*` field names for compatibility with the current codebase. `DomainResearcher` is the domain-independent facade used by the pipeline. Those legacy model names are technical debt and should be removed in a later dedicated model migration.
