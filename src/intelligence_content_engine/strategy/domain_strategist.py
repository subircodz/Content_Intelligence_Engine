"""Target-domain strategy facade."""

from intelligence_content_engine.client import ClientConfig
from intelligence_content_engine.strategy.strategist import ContentStrategist


class DomainContentStrategist(ContentStrategist):
    """Content strategy generator bound to a configured target domain."""

    def __init__(self, llm_client, client_config: ClientConfig) -> None:
        super().__init__(llm_client)
        self.client_config = client_config
