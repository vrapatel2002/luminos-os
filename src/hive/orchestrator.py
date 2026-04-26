"""
HIVE Orchestrator — Central Reasoning Plane
[CHANGE: gemini-cli | 2026-04-26]
Coordinates between specialist agents and manages the model lifecycle.
"""

import os
import sys
import logging
import json
import time
import threading
from llama_cpp import Llama

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from gpu_manager.model_manager import HIVE_MODELS

logger = logging.getLogger("hive.orchestrator")

class HIVEOrchestrator:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(HIVEOrchestrator, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.models_dir = os.path.expanduser("~/.local/share/luminos/models")
        self.active_model_name = None
        self.llm = None
        self._initialized = True
        logger.info("HIVE Orchestrator initialized")

    def _get_model_path(self, model_alias):
        if model_alias not in HIVE_MODELS:
            return None
        rel_path = HIVE_MODELS[model_alias].get("path")
        if not rel_path:
            return None
        return os.path.join(self.models_dir, rel_path)

    def _ensure_model(self, model_alias):
        """Load a model if not already active."""
        if self.active_model_name == model_alias and self.llm is not None:
            return True

        path = self._get_model_path(model_alias)
        if not path or not os.path.exists(path):
            logger.error(f"Model path not found for {model_alias}: {path}")
            return False

        logger.info(f"Loading model: {model_alias} from {path}")
        
        # Unload current
        self.llm = None
        
        # Load new
        try:
            # Using TurboQuant turbo4 (type_k=12, type_v=12) if GPU
            # For now, standard llama.cpp load
            self.llm = Llama(
                model_path=path,
                n_gpu_layers=-1, # Auto detect
                n_ctx=4096,
                use_mmap=True,
                verbose=False
            )
            self.active_model_name = model_alias
            return True
        except Exception as e:
            logger.error(f"Failed to load model {model_alias}: {e}")
            return False

    def chat(self, prompt, model="nexus"):
        """Main chat interface for HIVE."""
        t0 = time.time()
        
        if not self._ensure_model(model):
            return {
                "response": f"Error: Could not load model {model}",
                "model_used": "none",
                "tokens_per_sec": 0
            }

        try:
            # Get system prompt
            sys_prompt = HIVE_MODELS[model].get("prompt", "You are a helpful assistant.")
            
            output = self.llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500
            )
            
            response = output['choices'][0]['message']['content']
            usage = output.get('usage', {})
            total_tokens = usage.get('completion_tokens', 0)
            duration = time.time() - t0
            tps = round(total_tokens / duration, 2) if duration > 0 else 0
            
            return {
                "response": response,
                "model_used": model,
                "tokens_per_sec": tps
            }
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {
                "response": f"HIVE error: {e}",
                "model_used": model,
                "tokens_per_sec": 0
            }

if __name__ == "__main__":
    # Minimal CLI for the service
    logging.basicConfig(level=logging.INFO)
    orchestrator = HIVEOrchestrator()
    logger.info("HIVE Orchestrator service running (stub)")
    # Keep alive
    while True:
        time.sleep(3600)
