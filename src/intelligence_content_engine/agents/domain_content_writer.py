"""Target-domain writer facade."""

from intelligence_content_engine.agents.content_writer import ContentWriterAgent
from intelligence_content_engine.client import ClientConfig
from intelligence_content_engine.language import ContentLanguage


class DomainContentWriterAgent(ContentWriterAgent):
    """Writer bound to a configured target domain."""

    def __init__(
        self,
        llm_client,
        client_config: ClientConfig,
        language: ContentLanguage = ContentLanguage.ENGLISH,
    ) -> None:
        super().__init__(llm_client, language=language)
        self.client_config = client_config
