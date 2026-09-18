import logging
import time

import httpx

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for an OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        max_retries: int = 2,
        request_timeout: float = 60.0,
        max_prompt_length: int = 100_000,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.max_retries = max(0, max_retries)
        self.request_timeout = request_timeout
        self.max_prompt_length = max_prompt_length

    def generate(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        if len(prompt) > self.max_prompt_length:
            raise ValueError(
                f"prompt exceeds the configured limit of {self.max_prompt_length} characters"
            )

        for attempt in range(self.max_retries + 1):
            try:
                return self._send_request(prompt)
            except (httpx.HTTPError, httpx.ReadTimeout) as exc:
                if attempt == self.max_retries:
                    raise
                wait_time = min(2 ** attempt, 5)
                logger.warning(
                    "LLM request failed (attempt %d/%d): %s; retrying in %.1fs",
                    attempt + 1,
                    self.max_retries + 1,
                    exc,
                    wait_time,
                )
                time.sleep(wait_time)

        raise RuntimeError("LLM request failed after retries")

    def _send_request(self, prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        timeout = httpx.Timeout(self.request_timeout, connect=min(self.request_timeout, 10.0))
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=timeout,
        )
        response.raise_for_status()

        try:
            data = response.json()
            content = data["choices"][0]["message"].get("content")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ValueError("LLM response did not contain a valid chat completion") from exc

        if not isinstance(content, str):
            raise ValueError("LLM response content was not text")
        return content


