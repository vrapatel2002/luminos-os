"""Base class for all tools."""

import logging

logger = logging.getLogger("hive.tools.base")


class Tool:
    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("enabled", True)

    async def execute(self, params: dict) -> dict:
        """Execute the tool's main logic."""
        raise NotImplementedError("Subclasses must implement execute")

    def is_enabled(self) -> bool:
        return self.enabled

    def get_name(self) -> str:
        raise NotImplementedError("Subclasses must implement get_name")

    def get_description(self) -> str:
        raise NotImplementedError("Subclasses must implement get_description")
