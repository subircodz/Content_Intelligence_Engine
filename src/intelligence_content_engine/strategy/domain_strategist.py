"""Target-domain strategy facade."""

from power_win_content.client import ClientConfig
from power_win_content.strategy.strategist import ContentStrategist


class DomainContentStrategist(ContentStrategist):
    """Content strategy generator bound to a configured target domain."""

    def __init__(self, llm_client, client_config: ClientConfig) -> None:
        super().__init__(llm_client)
        self.client_config = client_config
