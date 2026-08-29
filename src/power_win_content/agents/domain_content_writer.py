"""Target-domain writer facade."""

from power_win_content.agents.content_writer import ContentWriterAgent
from power_win_content.client import ClientConfig


class DomainContentWriterAgent(ContentWriterAgent):
    """Writer bound to a configured target domain."""

    def __init__(self, llm_client, client_config: ClientConfig) -> None:
        super().__init__(llm_client)
        self.client_config = client_config
