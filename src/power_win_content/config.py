import os

from dotenv import load_dotenv

from power_win_content.client import ClientConfig

load_dotenv()


class Settings:
    """Runtime settings. Client identity is configuration, never engine code."""

    def __init__(self) -> None:
        self.omniroute_base_url = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")
        self.omniroute_model = os.getenv("OMNIROUTE_MODEL", "auto")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_cse_id = os.getenv("GOOGLE_CSE_ID")
        self.bing_api_key = os.getenv("BING_API_KEY")

        domain = os.getenv("TARGET_DOMAIN", "").strip()
        name = os.getenv("TARGET_BRAND", domain).strip()
        sitemap_values = os.getenv("TARGET_FIRST_PARTY_SITEMAPS", "")
        sitemaps = tuple(url.strip() for url in sitemap_values.split(",") if url.strip())

        if not domain:
            raise ValueError(
                "TARGET_DOMAIN is required. The content intelligence engine is domain-independent; "
                "configure the target site through environment variables."
            )

        self.client = ClientConfig(
            name=name or domain,
            domain=domain,
            first_party_sitemaps=sitemaps,
        )
