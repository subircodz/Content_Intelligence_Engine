"""Domain-independent strategy facade."""

from power_win_content.client import ClientConfig
from power_win_content.strategy.strategist import ContentStrategist


class DomainContentStrategist(ContentStrategist):
    """Content strategy generator bound to a configured target, not a fixed brand."""

    def __init__(self, llm_client, client_config: ClientConfig) -> None:
        super().__init__(llm_client)
        self.client_config = client_config

    def _build_context(self, *args, **kwargs):
        return super()._build_context(*args, **kwargs).replace("Power.win", self.client_config.name)

    def _build_seo_prompt(self, topic: str, context: str) -> str:
        return super()._build_seo_prompt(topic, context).replace("Power.win", self.client_config.name)

    def _build_geo_prompt(self, topic: str, context: str) -> str:
        return super()._build_geo_prompt(topic, context).replace("Power.win", self.client_config.name)
