from .agent_base import HiveAgent, AgentResponse
class Nexus(HiveAgent):
    "Planning and coordination. Phase 4."
    def __init__(self):
        super().__init__("Nexus",
            "~/.local/share/luminos/models/hive/dolphin3.0-llama3.1-8b-Q4_K_M.gguf")
    def process(self, input):
        raise NotImplementedError("Phase 4")