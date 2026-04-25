"""Vision agent for image understanding."""

import logging
from .base import OllamaAgent

logger = logging.getLogger("hive.agents.vision")


class VisionAgent(OllamaAgent):
    def get_system_prompt(self) -> str:
        try:
            import yaml
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.yaml")
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            return config.get("system_prompts", {}).get(self.name, "You are a vision specialist.")
        except Exception as e:
            logger.error(f"Failed to load system prompt from config: {e}")
            return "You are a vision specialist."

    async def execute(self, messages: list[dict], context: str = None, conversation_history: list[dict] = None, images: list = None) -> dict:
        """Execute with special handling for images."""
        
        full_messages = []
        
        # 1. System Prompt
        system_content = self.get_system_prompt()
        if context:
            system_content += f"\n\n## Context\n{context}"
        full_messages.append({"role": "system", "content": system_content})

        # 2. Conversation History (if needed, but usually vision is single-turn focused)
        if conversation_history:
             full_messages.extend(conversation_history)

        # 3. The User Message with Images
        # Ollama expects images in the 'images' field of the message dict (list of base64 strings)
        current_msg = messages[-1].copy() # Assume the last message is the user's current request
        
        if images:
            current_msg["images"] = images
        
        full_messages.append(current_msg)

        try:
            response = await self.ollama_client.chat(
                model=self.name,
                messages=full_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            return {
                "content": response.get("message", {}).get("content", ""),
                "model": self.name,
                "tokens_used": response.get("eval_count", 0),
                "store_memory": None
            }
            
        except Exception as e:
            logger.error(f"Vision Agent execution failed: {e}")
            return {
                "content": f"I had trouble analyzing the image: {e}",
                "model": self.name,
                "error": str(e)
            }
