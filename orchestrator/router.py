"""Router: Simplified coordinator pass-through."""

import logging

logger = logging.getLogger("hive.orchestrator.router")

class Router:
    def __init__(self, ollama_client, models_config: dict):
        self.ollama_client = ollama_client
        self.models_config = models_config
        # Mapping from model names to agent keys
        self.model_agent_map = {
            "nexus": "chat",
            "bolt": "coder",
            "nova": "planner",
            "eye": "vision",
            # Legacy
            "llama3.1:8b": "chat",
            "qwen2.5-coder:7b": "coder",
            "deepseek-r1:7b": "planner",
            "llava:7b": "vision"
        }

    async def route(
        self, 
        message: str, 
        conversation_history: list[dict] = None,
        current_model: str = None,
        images: list = None
    ) -> dict:
        """
        Route message to the appropriate agent.
        Logic:
        1. If images present -> Vision
        2. If current_model set -> Stay with current model (Agent)
        3. Else -> Coordinator (Chat/Llama)
        """
        reasoning = "Coordinator default"
        agent = "chat"
        
        # 1. Image Check
        if images:
            return {
                "agent": "vision",
                "needs_memory": False,
                "needs_tools": [],
                "reasoning": "Image input detected"
            }

        # 2. Current Model Stickiness
        if current_model:
            agent = self.model_agent_map.get(current_model, "chat")
            reasoning = f"Staying with current model: {current_model}"
            
        return {
            "agent": agent,
            "needs_memory": True,
            "needs_tools": [], # Coordinator decides tool use
            "reasoning": reasoning,
        }



