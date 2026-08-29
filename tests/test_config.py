"""Tests for application Settings configuration."""

import os
from unittest.mock import patch

from power_win_content.config import Settings


class TestSettingsLLM:
    def test_llm_base_url_default(self):
        with patch.dict(os.environ, {"TARGET_DOMAIN": "example.com"}, clear=True):
            settings = Settings()
            assert settings.llm_base_url == "http://localhost:20128/v1"

    def test_llm_model_default(self):
        with patch.dict(os.environ, {"TARGET_DOMAIN": "example.com"}, clear=True):
            settings = Settings()
            assert settings.llm_model == "auto"

    def test_llm_base_url_from_env(self):
        env = {"TARGET_DOMAIN": "example.com", "LLM_BASE_URL": "https://llm.example.com/v1"}
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.llm_base_url == "https://llm.example.com/v1"

    def test_llm_model_from_env(self):
        env = {"TARGET_DOMAIN": "example.com", "LLM_MODEL": "test-model"}
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.llm_model == "test-model"


class TestSettingsTarget:
    def test_target_domain_required(self):
        with patch.dict(os.environ, {}, clear=True):
            try:
                Settings()
                assert False, "Settings should require TARGET_DOMAIN"
            except ValueError as exc:
                assert "TARGET_DOMAIN" in str(exc)

    def test_target_configuration(self):
        env = {
            "TARGET_DOMAIN": "example.com",
            "TARGET_BRAND": "Example",
            "TARGET_FIRST_PARTY_SITEMAPS": "https://example.com/sitemap.xml,https://docs.example.com/sitemap.xml",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.client.name == "Example"
            assert settings.client.domain == "example.com"
            assert settings.client.first_party_sitemaps == (
                "https://example.com/sitemap.xml",
                "https://docs.example.com/sitemap.xml",
            )


class TestSettingsGoogle:
    def test_google_credentials(self):
        env = {"TARGET_DOMAIN": "example.com", "GOOGLE_API_KEY": "key", "GOOGLE_CSE_ID": "cx"}
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.google_api_key == "key"
            assert settings.google_cse_id == "cx"


class TestSettingsBing:
    def test_bing_api_key(self):
        env = {"TARGET_DOMAIN": "example.com", "BING_API_KEY": "bing-key"}
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.bing_api_key == "bing-key"
