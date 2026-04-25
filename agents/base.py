"""Base agent class for all LLMS agents."""

import logging

logger = logging.getLogger("hive.agents.base")


class OllamaAgent:
    def __init__(self, ollama_client, model_config: dict):
        self.ollama_client = ollama_client
        self.model_config = model_config
        self.name = model_config.get("name", "unknown")
        self.role = model_config.get("role", "assistant")
        self.temperature = model_config.get("temperature", 0.7)
        self.max_tokens = model_config.get("max_tokens", 2048)

    async def execute(self, messages: list[dict], context: str = None, conversation_history: list[dict] = None, images: list = None) -> dict:
        """Execute the agent's main logic."""
        
        # Build the full message list
        full_messages = []
        
        # 1. System Prompt (Agent specific + Context)
        system_content = self.get_system_prompt()
        if context:
            system_content += f"\n\n## Context & Tool Results\n{context}"
            
        full_messages.append({"role": "system", "content": system_content})
        
        # 2. History (if provided)
        if conversation_history:
            # We filter out system messages from history to avoid confusion, 
            # and keep only the last N turns if needed, but for now we trust the caller.
            full_messages.extend(conversation_history)
            
        # 3. Current User Message (This is usually already in 'messages' or we append it)
        # The 'messages' argument typically contains the current turn [user_msg] 
        # or a list of recent turns. We'll simply extend.
        full_messages.extend(messages)

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
                "store_memory": None  # Subclasses/Prompt engineering can override to request memory storage
            }
            
        except Exception as e:
            logger.error(f"Agent '{self.name}' execution failed: {e}")
            return {
                "content": f"I encountered an error: {e}",
                "model": self.name,
                "error": str(e)
            }

    def get_system_prompt(self) -> str:
        """Return the default system prompt for this agent."""
        return f"You are a helpful AI assistant acting as: {self.role}."

    def get_model_name(self) -> str:
        return self.name

    def get_role(self) -> str:
        return self.role
