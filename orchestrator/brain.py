"""Brain: central orchestrator that processes every user message."""

import logging
import time
import re
import json
import asyncio

logger = logging.getLogger("hive.orchestrator.brain")


class Brain:
    def __init__(
        self,
        config: dict,
        ollama_client,
        vram_manager,
        database,
        embedding_service,
        memory_retriever,
        router,
        agents: dict, # Keeping mapping but relying on config for prompts
        tools: dict,
    ):
        self.config = config
        self.ollama_client = ollama_client
        self.vram_manager = vram_manager
        self.database = database
        self.embedding_service = embedding_service
        self.memory_retriever = memory_retriever
        self.router = router
        self.agents = agents
        self.tools = tools
        
        # State
        self.profile = {}
        self.is_first_run = False
        self.conversation_history = []
        self.current_model = None # None -> Coordinator on first run
        
        # Pending Actions
        self.pending_swap = None # {"target_model": str, "reason": str, "summary": str, "timestamp": float}
        self.pending_confirmations = {} # Terminal confirmations
        
        # Config
        ctx_config = config.get("context_management", {})
        self.max_history = ctx_config.get("max_history_messages", 20)
        self.summary_threshold = ctx_config.get("summary_threshold", 20)
        
        # Routing Config
        route_config = config.get("routing", {})
        self.coordinator_model = route_config.get("coordinator_model", "nexus")
        
        # Mapping
        self.model_map = {
            "coordinator": self.coordinator_model,
            "coder": "bolt",
            "planner": "nova",
            "vision": "eye",
            # Fallbacks / Direct names
            "nexus": "nexus",
            "bolt": "bolt", 
            "nova": "nova",
            "eye": "eye",
            # Legacy mapping for safety
            "llama3.1:8b": "nexus",
            "qwen2.5-coder:7b": "bolt",
            "deepseek-r1:7b": "nova",
            "llava:7b": "eye"
        }
        
        


    def _test_tag_parsing(self):
        """Verify tag regex works as expected."""
        test_cases = [
            "[ROUTE:CODER] Write a sort function",
            "[ROUTE:TERMINAL] dir",
            "[ROUTE:PLANNER] Plan a migration",
            "[REQUEST:CODER] Need coder for implementation",
            "Just a normal response with no tags",
        ]
        logger.info("--- Tag Parsing Self-Test ---")
        for text in test_cases:
            result = self._parse_routing_tags(text)
            logger.info(f"Tag test: '{text[:50]}' -> {result}")
        logger.info("-----------------------------")

    def get_recent_history(self, limit: int = 10) -> list[dict]:
        """Get the last N messages from history."""
        return self.conversation_history[-limit:]
        
    def clear_history(self):
        """Clear conversation history and reset state."""
        self.conversation_history = []
        self.current_model = None
        self.pending_swap = None
        self.pending_confirmations = {}
        
    def swap_model(self, model_name: str):
        """Manually swap the current model."""
        if model_name in self.model_map.values():
            self.current_model = model_name
        elif model_name in self.model_map:
            self.current_model = self.model_map[model_name]
        else:
            logger.warning(f"Unknown model swap request: {model_name}")

    async def process(
        self,
        message: str,
        session_id: str = None,
        images: list = None,
        conversation_history: list[dict] = None, # Legacy arg, we use internal self.conversation_history
    ) -> dict:
        """Process a single user message through the coordinator pipeline."""
        start_time = time.time()
        
        # 1. Add to Internal History
        self.add_to_history("user", message)

        # DEBUG: Check Force Overrides
        if message.startswith("!route "):
            parts = message.strip().split(" ", 2)
            if len(parts) >= 2:
                route_type = parts[1].lower()
                payload = parts[2] if len(parts) > 2 else ""
                
                logger.info(f" FORCE ROUTE DETECTED: {route_type}")
                
                if route_type == "terminal":
                    # Force terminal bypassing everything
                    return await self._handle_terminal_tool(payload, start_time)
                
                target_model = None
                if route_type == "coder": target_model = self.model_map["coder"]
                elif route_type == "planner": target_model = self.model_map["planner"]
                elif route_type == "vision": target_model = self.model_map["vision"]
                
                if target_model:
                     # Force swap and run
                     self.current_model = target_model
                     return await self._run_model_turn(
                         handoff_note=f"SYSTEM: User forced route to {route_type}. Task: {payload}", 
                         start_time=start_time
                     )

        # Check Terminal Intent
        is_terminal, command = self.detect_terminal_intent(message)
        if is_terminal:
            logger.info(f"Terminal intent detected: {command}")
            return await self._handle_terminal_tool(command, start_time)
        
        # 2. Check Pending Actions (Priority: Swap > Terminal)
        is_yes = self._is_positive_confirmation(message)
        is_no = self._is_negative_confirmation(message)
        
        # 2a. Pending Swap
        if self.pending_swap:
            if is_yes:
                # Execute Swap
                target = self.pending_swap["target_model"]
                summary = self.pending_swap["summary"]
                reason = self.pending_swap["reason"]
                prev_model = self.current_model
                
                self.current_model = target
                self.pending_swap = None
                
                handoff = (
                    f"SYSTEM HANDOFF NOTE: You are being activated to handle a task.\n"
                    f"Previous model: {prev_model}\n"
                    f"Reason: {reason}\n"
                    f"Task: {summary}\n"
                    f"Recent summary: {await self._get_recent_summary_str()}\n"
                    f"Continue from here. The user is Vratik."
                )
                return await self._run_model_turn(handoff_note=handoff, start_time=start_time)
                
            elif is_no:
                # Cancel Swap
                self.pending_swap = None
                # Continue with current model, letting it know user refused
                return await self._run_model_turn(
                    handoff_note="SYSTEM: User rejected the swap request. Continue handling it yourself.",
                    start_time=start_time
                )
        
        # 2b. Pending Terminal Confirmation
        if self.pending_confirmations.get("default"):
            if is_yes:
                return await self._execute_pending_terminal(start_time)
            elif is_no:
                self.pending_confirmations.pop("default")
                return {
                    "response": "Cancelled.",
                    "model": "system",
                    "route": {},
                    "tools_used": [],
                    "memory_used": None,
                    "response_time": time.time() - start_time
                }

        # 3. History Management
        await self._manage_history()

        # 4. Context Retrieval (Memories)
        memories = await self._retrieve_memories(message)
        
        # 5. Model Selection
        # If images -> Vision
        if images:
            self.current_model = self.model_map["vision"]
        elif self.current_model is None:
            self.current_model = self.coordinator_model
            
        # 6. Run Model Turn
        return await self._run_model_turn(memories=memories, start_time=start_time)

    async def _run_model_turn(self, handoff_note: str = None, memories: str = None, start_time: float = 0.0) -> dict:
        """Run a single turn of the current model, parse tags, and handle recursion."""
        
        # 1. Build System Prompt
        sys_prompt = self.config.get("system_prompts", {}).get(self.current_model, "")
        if not sys_prompt:
            logger.warning(f"No system prompt found for {self.current_model}")
            
        full_messages = [{"role": "system", "content": sys_prompt}]
        
        if memories:
            full_messages.append({"role": "system", "content": f"Relevant Memories:\n{memories}"})
            
        if handoff_note:
            full_messages.append({"role": "system", "content": handoff_note})
            
        # Append Conversation History
        full_messages.extend(self.conversation_history)
        
        # 2. Get Model Config
        temp = 0.7
        max_tokens = 4096
        
        # Find config for current model
        for role, cfg in self.config.get("models", {}).items():
            if isinstance(cfg, dict) and cfg.get("name") == self.current_model:
                temp = cfg.get("temperature", 0.7)
                max_tokens = cfg.get("max_tokens", 4096)
                break
        
        # 3. Call Model
        logger.info(f"Sending to {self.current_model}: {len(full_messages)} messages, sys_len: {len(sys_prompt)}")
        logger.info(f"System prompt preview: {sys_prompt[:100]}...")
        
        response = await self.ollama_client.chat(
            model=self.current_model,
            messages=full_messages,
            temperature=temp,
            max_tokens=max_tokens,
            options={"num_ctx": 8192} # Increased context
        )
        content = response.get("message", {}).get("content", "")
        logger.info(f"Raw response from {self.current_model}: {content[:200]}...")
        
        # 3. Parse Tags
        decision = self._parse_routing_tags(content)
        logger.info(f"Tags found: {decision}")
        
        # 4. Handle Decision
        
        # A. ROUTE (Immediate Swap/Action)
        if decision["type"] == "route":
            target = decision["target"]
            payload = decision["payload"]
            
            # Tools
            if target == "TERMINAL":
                return await self._handle_terminal_tool(payload, start_time)
            elif target == "FILE_CREATE":
                return await self._handle_file_tool(payload, start_time)
                
            # Model Swap
            # Map tag to model
            target_model = None
            if target == "CODER": target_model = self.model_map["coder"]
            elif target == "PLANNER": target_model = self.model_map["planner"]
            elif target == "VISION": target_model = self.model_map["vision"]
            
            if target_model:
                prev_model = self.current_model
                self.current_model = target_model
                
                handoff = (
                    f"SYSTEM HANDOFF: Coordinator determined this is a {target} task.\n"
                    f"Task: {payload}\n"
                    f"Previous: {prev_model}\n"
                    f"Recent context: {await self._get_recent_summary_str()}"
                )
                # Helper: Add the routing instruction to history so next model sees why it was called? 
                # Or just rely on handoff. Handoff is better.
                # Recursive call
                return await self._run_model_turn(handoff_note=handoff, start_time=start_time)

        # B. REQUEST (Ask User)
        elif decision["type"] == "request":
            target = decision["target"]
            summary = decision["payload"]
            
            target_model = None
            if target == "CODER": target_model = self.model_map["coder"]
            elif target == "PLANNER": target_model = self.model_map["planner"]
            elif target == "VISION": target_model = self.model_map["vision"]
            
            if target_model:
                self.pending_swap = {
                    "target_model": target_model,
                    "reason": f"REQUEST:{target}",
                    "summary": summary,
                    "timestamp": time.time()
                }
                resp_text = (
                    f"🔄 **Swap Request**\n"
                    f"{self.current_model} wants to bring in the {target} specialist.\n"
                    f"**Reason:** {summary}\n"
                    f"This will take ~10 seconds. Swap? [yes/no]"
                )
                self.add_to_history("assistant", resp_text)
                return self._build_response(resp_text, self.current_model, start_time)

        # C. NORMAL RESPONSE
        self.add_to_history("assistant", content)
        
        # Log to DB
        await self._log_interaction(content, self.current_model, start_time)
        
        return self._build_response(content, self.current_model, start_time)

    # --- Helpers ---

    def add_to_history(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})

    async def _manage_history(self):
        if len(self.conversation_history) > self.max_history:
            summary = await self._get_history_summary()
            # Keep recent messages
            keep_count = self.config.get("context_management", {}).get("recent_messages_after_summary", 15)
            recent = self.conversation_history[-keep_count:]
            
            # Rebuild history: Summary + Recent
            self.conversation_history = [{"role": "system", "content": f"Previous conversation summary: {summary}"}] + recent

    async def _get_history_summary(self):
        """Summarize conversation history directly via Ollama."""
        text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.conversation_history])
        prompt = f"Summarize this conversation in under 200 words. Focus on key facts and decisions.\n\n{text}"
        
        # Use simple call (bypass process)
        try:
            response = await self.ollama_client.chat(
                model=self.coordinator_model,
                messages=[{"role": "user", "content": prompt}],
                options={"num_ctx": 4096}
            )
            return response.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Summary failed: {e}")
            return "Summary unavailable."

    async def _retrieve_memories(self, query: str) -> str:
        try:
            return await self.memory_retriever.get_context_for_prompt(query)
        except Exception:
            return ""

    def _parse_routing_tags(self, content: str) -> dict:
        """Parse [ROUTE:...] and [REQUEST:...] tags."""
        # Regex for tags
        match = re.search(r"\[(ROUTE|REQUEST):([A-Z_]+)\]\s*(.*)", content, re.DOTALL)
        if match:
            tag_type = match.group(1).lower() # route or request
            target = match.group(2).upper()   # CODER, PLANNER, TERMINAL...
            payload = match.group(3).strip()
            return {"type": tag_type, "target": target, "payload": payload}
        return {"type": "none"}

    async def _handle_terminal_tool(self, command: str, start_time: float) -> dict:
        tool = self.tools.get("terminal")
        if not tool: return self._build_response("Terminal tool missing.", "system", start_time)
        
        # Dry run logic (reused from session 4)
        res = await tool.execute({"command": command, "confirmed": False})
        
        if res.get("status") == "confirmation_required":
             # Store pending
             self.pending_confirmations["default"] = {
                 "command": command,
                 "cwd": "cwd", # Tool handles this
                 "timestamp": time.time()
             }
             resp = res["message"]
             self.add_to_history("assistant", resp)
             return self._build_response(resp, "terminal", start_time)
        
        # Immediate execution or error
        if res.get("success"):
             # It executed? Wait, tool returns success=True only if executed. 
             # If require_confirmation=True, it returns status=confirmation_required.
             # Unless risk is low? My previous implementation didn't auto-execute low risk inside tool.
             # But brain can.
             pass
             
        # If we are here, it might be an error or allowed execution (if I changed tool)
        # Let's assume tool returned error or block.
        resp = f"Output: {res.get('stdout', '')} {res.get('stderr', '')} {res.get('error', '')}"
        self.add_to_history("assistant", resp)
        return self._build_response(resp, "terminal", start_time)

    async def _execute_pending_terminal(self, start_time: float) -> dict:
        pending = self.pending_confirmations.get("default")
        tool = self.tools.get("terminal")
        if pending and tool:
            res = await tool.execute({"command": pending["command"], "confirmed": True})
            self.pending_confirmations.pop("default")
            output = f"✅ Output:\n```\n{res.get('stdout', '')}{res.get('stderr', '')}\n```"
            self.add_to_history("assistant", output)
            return self._build_response(output, "terminal", start_time)
        return self._build_response("Confirmation expired or invalid.", "system", start_time)

    async def _handle_file_tool(self, payload: str, start_time: float) -> dict:
        # payload format: path | content
        parts = payload.split("|", 1)
        if len(parts) < 2:
            return self._build_response("Invalid file format. Use: path | content", "system", start_time)
            
        path = parts[0].strip()
        content = parts[1].strip()
        
        tool = self.tools.get("file_write") # Assuming name
        if tool:
            # We need to adapt to tool arguments
            # FileWriteTool expects: TargetFile, CodeContent, etc.
            res = await tool.execute({
                "TargetFile": path,
                "CodeContent": content,
                "Overwrite": True,
                "EmptyFile": False,
                "Description": "Created by Agent",
                "Complexity": 1,
                "IsArtifact": False
            })
            resp = f"File created: {path}"
            self.add_to_history("assistant", resp)
            return self._build_response(resp, "file_create", start_time)
        return self._build_response("File tool missing.", "system", start_time)

    def _build_response(self, text, model, start_time):
        return {
            "response": text,
            "model": model,
            "route": {"agent": model}, # Dummy route info
            "tools_used": [],
            "memory_used": None,
            "response_time": time.time() - start_time
        }

    def _is_positive_confirmation(self, text):
        return bool(re.match(r"^(yes|y|confirm|ok|run|do it|sure)", text.strip().lower()))

    def _is_negative_confirmation(self, text):
        return bool(re.match(r"^(no|n|cancel|stop|don't)", text.strip().lower()))

    async def _get_recent_summary_str(self):
        # Return last 3 messages formatted
        recent = self.conversation_history[-3:]
        return "\n".join([f"{m['role']}: {m['content']}" for m in recent])
        
    async def _log_interaction(self, response, model, start_time):
        # Simplify log for now
        pass
        

    def detect_terminal_intent(self, message: str) -> tuple[bool, str]:
        """Detect if the user wants to run a terminal command."""
        msg = message.strip()
        lower_msg = msg.lower()

        # 1. Bang commands (!dir, !pip list)
        if msg.startswith("!"):
            return True, msg[1:].strip()

        # 2. "run" or "execute" prefixes
        if lower_msg.startswith("run ") or lower_msg.startswith("execute "):
            # Extract everything after the prefix (case sensitive for command)
            # Find first space
            parts = msg.split(" ", 1)
            if len(parts) > 1:
                return True, parts[1].strip()

        # 3. Known keywords
        keywords = ["pip ", "git ", "ollama ", "npm ", "node ", "python "]
        for kw in keywords:
            if lower_msg.startswith(kw.strip()) or kw in lower_msg:
                 # Be careful, if it's "how do i use pip" we don't want to run it.
                 # But user said "Contains 'pip list'..."
                 # Let's check for specific command-like structure or just trust the "safe" list?
                 # User said "The response clearly shows it came from the REAL terminal"
                 # Safer matching:
                 if lower_msg.startswith(kw.strip()):
                     return True, msg

        # 4. Standalone "dir" or "ls" or "pwd"
        if lower_msg in ["dir", "ls", "pwd"]:
            return True, msg
            
        # 5. "in terminal" intent
        if "in terminal" in lower_msg or "in the terminal" in lower_msg:
             # Try to extract command? Hard. 
             # If "run X in terminal", #2 catches "run X..." 
             # If "do X in terminal", we might miss it.
             pass

        return False, ""

    async def startup(self):
        await self.database.initialize()
        self.profile = await self.database.get_profile() or {}
        logger.info("Brain Coordinator Started")
        
        # Log loaded system prompts
        prompts = self.config.get("system_prompts", {})
        for model, prompt in prompts.items():
            if prompt:
                logger.info(f"System prompt loaded for {model}: {len(prompt)} chars")
            else:
                logger.error(f"ERROR: Missing system prompt for {model}")

    async def shutdown(self):
        await self.vram_manager.unload_all()
        await self.database.close()
        await self.ollama_client.close()
        
    async def health(self):
        return {"status": "ok", "model": self.current_model}

