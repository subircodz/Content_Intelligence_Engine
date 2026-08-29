"""Domain-independent content writer facade."""

from power_win_content.agents.content_writer import ContentWriterAgent
from power_win_content.client import ClientConfig


class DomainContentWriterAgent(ContentWriterAgent):
    """Writer that injects the configured target brand instead of a hard-coded client."""

    def __init__(self, llm_client, client_config: ClientConfig) -> None:
        super().__init__(llm_client)
        self.client_config = client_config

    def _build_brief_prompt(self, brief):
        return super()._build_brief_prompt(brief).replace("Power.win", self.client_config.name)

    def _build_legacy_prompt(self, title: str) -> str:
        return super()._build_legacy_prompt(title).replace("Power.win", self.client_config.name)
