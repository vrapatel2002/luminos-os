from .agent_base import HiveAgent, AgentResponse
class Eye(HiveAgent):
    "Vision and screen"
    def __init__(self):
        super().__init__("Eye",
            "~/.local/share/luminos/models/qwen3-8b")
    def process(self, input):
        raise NotImplementedError("Phase 4")