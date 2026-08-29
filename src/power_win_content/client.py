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
        domain = self.domain.strip()
        if not domain:
            raise ValueError("domain must not be empty")
        object.__setattr__(self, "domain", self._normalize_host(domain))

        domains = set(self.first_party_domains)
        domains.add(self.domain)
        object.__setattr__(self, "first_party_domains", tuple(sorted(d.lower().lstrip("www.") for d in domains)))

    @staticmethod
    def _normalize_host(value: str) -> str:
        parsed = urlparse(value if "://" in value else f"https://{value}")
        host = parsed.hostname
        if not host:
            raise ValueError(f"Invalid domain: {value!r}")
        return host.lower().lstrip("www.")

    def is_first_party_url(self, url: str) -> bool:
        """Return True only for the configured host or its subdomains."""
        host = urlparse(url).hostname
        if not host:
            return False
        host = host.lower().lstrip("www.")
        return any(host == domain or host.endswith(f".{domain}") for domain in self.first_party_domains)

    @property
    def base_url(self) -> str:
        return f"https://{self.domain}"
