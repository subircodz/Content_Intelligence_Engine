"""Target-domain writer facade."""

from intelligence_content_engine.agents.content_writer import ContentWriterAgent
from intelligence_content_engine.client import ClientConfig


class DomainContentWriterAgent(ContentWriterAgent):
    """Writer bound to a configured target domain."""

    def __init__(self, llm_client, client_config: ClientConfig) -> None:
        super().__init__(llm_client)
        self.client_config = client_config
