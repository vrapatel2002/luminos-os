"""Coder agent for programming tasks."""

import logging
from .base import OllamaAgent

logger = logging.getLogger("hive.agents.coder")


class CoderAgent(OllamaAgent):
    def get_system_prompt(self) -> str:
        try:
            import yaml
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.yaml")
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            return config.get("system_prompts", {}).get(self.name, "You are an expert coder.")
        except Exception as e:
            logger.error(f"Failed to load system prompt from config: {e}")
            return "You are an expert coder."
