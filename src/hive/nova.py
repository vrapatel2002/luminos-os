from .agent_base import HiveAgent, AgentResponse
class Nova(HiveAgent):
    "Research and knowledge"
    def __init__(self):
        super().__init__("Nova",
            "~/.local/share/luminos/models/qwen3-8b")
    def process(self, input):
        raise NotImplementedError("Phase 4")