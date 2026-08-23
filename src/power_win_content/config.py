import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.omniroute_base_url = os.getenv(
            "OMNIROUTE_BASE_URL",
            "http://localhost:20128/v1",
        )

        self.omniroute_model = os.getenv(
            "OMNIROUTE_MODEL",
            "auto",
        )

        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_cse_id = os.getenv("GOOGLE_CSE_ID")
        # Legacy: Bing Search API retired 2025-08-11; Bing search uses Playwright.
        self.bing_api_key = os.getenv("BING_API_KEY")