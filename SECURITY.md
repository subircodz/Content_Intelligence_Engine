# Security

## Threat model
The engine consumes untrusted URLs from search results and sitemaps and sends retrieved content to an LLM. It is intended to run as a controlled CLI process, not as an unauthenticated public HTTP endpoint.

## Network safety
Research fetchers accept only HTTP(S) URLs and reject localhost, loopback, private, link-local, multicast, reserved and unspecified destinations. HTTP redirects are validated before the next request. Browser fetches validate the final navigation destination.

Run the engine with normal outbound network egress controls. For deployments inside a cloud or corporate network, add an egress firewall/proxy that blocks cloud metadata services and internal address ranges as a second layer.

## Secrets
- Never commit .env, API keys, cookies, or generated credentials.
- Supply secrets through the deployment secret store or environment.
- Do not put credentials in target URLs.
- Do not log authorization headers or API keys.

## LLM safety
The LLM is an untrusted component from a correctness perspective. Generated content is a draft and must pass the research quality gate and human editorial review before publication.

The client enforces a maximum prompt size and validates the expected OpenAI-compatible response structure.

## Operational controls
- Set an explicit LLM endpoint and model in production.
- Keep outbound network access restricted to what the workload requires.
- Monitor LLM and web-provider error rates, latency and spend.
- Keep browser dependencies patched.
- Run the deterministic test suite before every release.
- Run live smoke tests in an isolated environment with real provider credentials.

## Reporting
If you find a security issue, do not publish credentials or exploit details in a public issue. Contact the repository owner privately first.
