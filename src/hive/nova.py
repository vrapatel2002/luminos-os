from .agent_base import HiveAgent, AgentResponse
class Nova(HiveAgent):
    "Research and knowledge"
    def __init__(self):
        super().__init__("Nova",
            "~/.local/share/luminos/models/hive/DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf")
    def process(self, input):
        raise NotImplementedError("Phase 4")