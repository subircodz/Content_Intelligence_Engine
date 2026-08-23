from unittest.mock import MagicMock, patch

from power_win_content.config import Settings
from power_win_content.llm.client import LLMClient


def test_llm_client_generates_response() -> None:
    settings = Settings()

    llm = LLMClient(
        base_url=settings.omniroute_base_url,
        model=settings.omniroute_model,
    )

    response = llm.generate(
        "What is 2 + 2? Answer with only the number."
    )

    assert response.strip() == "4"


def test_llm_client_handles_null_content() -> None:
    llm = LLMClient(base_url="http://localhost:20128/v1", model="auto")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                }
            }
        ]
    }
    mock_response.raise_for_status.return_value = None

    with patch("httpx.post", return_value=mock_response):
        res = llm.generate("test prompt")
        assert res == ""