from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class AgentResponse:
    agent: str
    content: str
    confidence: float
    latency_ms: float

class HiveAgent(ABC):
    """
    Base for all HIVE agents.
    Runs on dGPU (RTX 4050) via llama.cpp.
    Never on NPU (Sentinel/Router only).
    Never on iGPU (desktop rendering only).
    Phase 4 implementation.
    [CHANGE: gemini-cli | 2026-04-23]
    """
    def __init__(self, name, model_path):
        self.name = name
        self.model_path = model_path
        self.model = None

    @abstractmethod
    def process(self, input: str) -> AgentResponse:
        pass

    def is_ready(self):
        return self.model is not None