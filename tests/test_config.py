"""Tests for application Settings configuration."""

import os
from unittest.mock import patch

from power_win_content.config import Settings


class TestSettingsLLM:
    def test_omniroute_base_url_default(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.omniroute_base_url == "http://localhost:20128/v1"

    def test_omniroute_model_default(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.omniroute_model == "auto"

    def test_omniroute_base_url_from_env(self):
        with patch.dict(os.environ, {"OMNIROUTE_BASE_URL": "https://llm.example.com/v1"}):
            settings = Settings()
            assert settings.omniroute_base_url == "https://llm.example.com/v1"

    def test_omniroute_model_from_env(self):
        with patch.dict(os.environ, {"OMNIROUTE_MODEL": "gpt-4o"}):
            settings = Settings()
            assert settings.omniroute_model == "gpt-4o"


class TestSettingsGoogle:
    def test_google_api_key_default_none(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.google_api_key is None

    def test_google_cse_id_default_none(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.google_cse_id is None

    def test_google_api_key_from_env(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key-123"}):
            settings = Settings()
            assert settings.google_api_key == "test-key-123"

    def test_google_cse_id_from_env(self):
        with patch.dict(os.environ, {"GOOGLE_CSE_ID": "test-cx-456"}):
            settings = Settings()
            assert settings.google_cse_id == "test-cx-456"

    def test_google_credentials_together(self):
        env = {"GOOGLE_API_KEY": "key", "GOOGLE_CSE_ID": "cx"}
        with patch.dict(os.environ, env):
            settings = Settings()
            assert settings.google_api_key == "key"
            assert settings.google_cse_id == "cx"


class TestSettingsBing:
    def test_bing_api_key_default_none(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.bing_api_key is None

    def test_bing_api_key_from_env(self):
        with patch.dict(os.environ, {"BING_API_KEY": "bing-key-789"}):
            settings = Settings()
            assert settings.bing_api_key == "bing-key-789"


class TestSettingsIntegration:
    def test_all_settings_populated(self):
        env = {
            "OMNIROUTE_BASE_URL": "https://llm.example.com/v1",
            "OMNIROUTE_MODEL": "gpt-4o",
            "GOOGLE_API_KEY": "gkey",
            "GOOGLE_CSE_ID": "gcx",
            "BING_API_KEY": "bkey",
        }
        with patch.dict(os.environ, env):
            settings = Settings()
            assert settings.omniroute_base_url == "https://llm.example.com/v1"
            assert settings.omniroute_model == "gpt-4o"
            assert settings.google_api_key == "gkey"
            assert settings.google_cse_id == "gcx"
            assert settings.bing_api_key == "bkey"

    def test_partial_credentials(self):
        """Only Google credentials set; Bing remains None."""
        env = {
            "GOOGLE_API_KEY": "gkey",
            "GOOGLE_CSE_ID": "gcx",
        }
        with patch.dict(os.environ, env):
            settings = Settings()
            assert settings.google_api_key == "gkey"
            assert settings.google_cse_id == "gcx"
            assert settings.bing_api_key is None

    def test_empty_string_credentials_are_truthy(self):
        """Empty strings are truthy but indicate no real credential."""
        env = {"GOOGLE_API_KEY": "", "GOOGLE_CSE_ID": "", "BING_API_KEY": ""}
        with patch.dict(os.environ, env):
            settings = Settings()
            assert settings.google_api_key == ""
            assert settings.google_cse_id == ""
            assert settings.bing_api_key == ""
