import logging
import time

import httpx

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for any OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        max_retries: int = 0,
        request_timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_retries = max_retries
        self.request_timeout = request_timeout

    def generate(self, prompt: str) -> str:
        for attempt in range(self.max_retries + 1):
            try:
                return self._send_request(prompt)
            except (httpx.HTTPError, httpx.ReadTimeout) as exc:
                if attempt == self.max_retries:
                    raise
                wait_time = min(2 ** attempt, 5)
                logger.debug(
                    "LLM request failed (attempt %d/%d): %s; retrying in %.1fs",
                    attempt + 1,
                    self.max_retries + 1,
                    exc,
                    wait_time,
                )
                time.sleep(wait_time)

        raise RuntimeError("LLM request failed after retries")

    def _send_request(self, prompt: str) -> str:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=self.request_timeout,
        )
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"].get("content")
        return content if content is not None else ""
