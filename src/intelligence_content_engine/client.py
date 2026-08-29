"""Client/domain configuration for the content intelligence engine.

The engine itself must not assume a particular brand or website. A ClientConfig
contains the target site's identity and optional first-party knowledge sources.
"""

from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass(frozen=True)
class ClientConfig:
    """Configuration describing the site for which content is being produced."""

    name: str
    domain: str
    first_party_sitemaps: tuple[str, ...] = field(default_factory=tuple)
    first_party_domains: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        normalized_domain = self._normalize_host(self.domain)
        object.__setattr__(self, "domain", normalized_domain)

        domains = {self._normalize_host(value) for value in self.first_party_domains}
        domains.add(normalized_domain)
        object.__setattr__(self, "first_party_domains", tuple(sorted(domains)))

    @staticmethod
    def _normalize_host(value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("domain must not be empty")
        parsed = urlparse(value if "://" in value else f"https://{value}")
        host = parsed.hostname
        if not host:
            raise ValueError(f"Invalid domain: {value!r}")
        return host.lower().removeprefix("www.")

    def is_first_party_url(self, url: str) -> bool:
        """Return True only for a configured host or one of its subdomains."""
        host = urlparse(url).hostname
        if not host:
            return False
        host = host.lower().removeprefix("www.")
        return any(host == domain or host.endswith(f".{domain}") for domain in self.first_party_domains)

    @property
    def base_url(self) -> str:
        return f"https://{self.domain}"
