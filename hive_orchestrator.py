"""
title: HIVE Orchestrator
author: vratik
version: 1.1
description: Nexus-brained router. SearXNG web browsing. Smart web skip. Async image support.
"""

from pydantic import BaseModel, Field
from typing import Optional, Union, AsyncGenerator
import requests
import json
import re
import base64


class Pipe:

    # ============================================================
    # SECTION 1: SETTINGS
    # ============================================================

    class Valves(BaseModel):
        GPU_SERVER: str = Field(
            default="http://host.docker.internal:11434",
            description="Ollama GPU server (port 11434)",
        )
        CPU_SERVER: str = Field(
            default="http://host.docker.internal:11435",
            description="Ollama CPU server (port 11435)",
        )
        NEXUS_MODEL: str = Field(
            default="nexus", description="Coordinator (dolphin3:8b) on GPU"
        )
        NOVA_MODEL: str = Field(
            default="nova", description="Deep thinker (deepseek-r1:7b) on CPU"
        )
        BOLT_MODEL: str = Field(
            default="bolt", description="Expert coder (qwen2.5-coder:7b) on GPU"
        )
        EYE_MODEL: str = Field(default="eye", description="Vision (llava:7b) on GPU")
        DEBUG_MODE: bool = Field(
            default=True, description="Shows raw message format for debugging"
        )
        SHOW_THINKING: bool = Field(
            default=True, description="Shows Nova thinking process live"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.type = "manifold"

    def pipes(self) -> list[dict]:
        return [{"id": "hive", "name": "HIVE Orchestrator"}]

    # ============================================================
    # SECTION 2: IMAGE DETECTION
    # ============================================================

    def _check_for_images(self, messages):
        result = {"found": False, "where": "none", "debug_info": []}
        if not messages:
            return result

        last = messages[-1]

        if last.get("images"):
            result["found"] = True
            result["where"] = "message.images"

        content = last.get("content", "")
        if isinstance(content, list):
            for i, part in enumerate(content):
                if isinstance(part, dict):
                    pt = part.get("type", "NO_TYPE")
                    if pt in ("image_url", "image"):
                        result["found"] = True
                        result["where"] = f"content[{i}].type={pt}"

        return result

    # ============================================================
    # SECTION 2.5: WEB BROWSING (SEARXNG + TRAFILATURA)
    # ============================================================

    def _quick_web_skip(self, text: str) -> bool:
        """Return True if this message OBVIOUSLY does not need web search.
        Saves an LLM call for greetings, chat, math, code requests."""
        text_lower = text.strip().lower()

        # Exact match short chat — no web needed ever
        short_chat = [
            "hi", "hey", "hello", "hola", "sup", "yo", "hii", "hiii",
            "hey nexus", "hi nexus", "hello nexus", "hey hive", "hi hive",
            "whats up", "what's up", "wassup", "how are you", "how r u",
            "good morning", "good evening", "good night", "gm", "gn",
            "thanks", "thank you", "thx", "ty", "ok", "okay", "cool",
            "bye", "goodbye", "see ya", "later", "gtg",
            "yes", "no", "yeah", "yep", "nope", "nah",
            "lol", "lmao", "haha", "nice", "wow", "damn",
            "who are you", "what are you", "what can you do",
            "help", "help me", "what is hive", "who is nexus",
            "tell me about yourself", "introduce yourself",
        ]
        if text_lower in short_chat:
            return True

        # Messages under 4 words with no web-trigger keywords
        words = text_lower.split()
        if len(words) <= 3:
            web_triggers = [
                "price", "cost", "worth", "rate", "exchange", "weather",
                "news", "score", "stock", "crypto", "bitcoin", "btc",
                "eth", "gold", "silver", "oil", "usd", "inr", "eur",
                "cad", "gbp", "jpy", "rupee", "dollar", "pound",
                "today", "current", "latest", "recent", "now", "live",
                "trending", "update", "happened", "election", "war",
                "temperature", "forecast", "rain", "snow",
            ]
            if not any(trigger in text_lower for trigger in web_triggers):
                return True

        # Obvious code/math requests — never need web
        code_math_starters = [
            "write", "code", "implement", "create a function", "create a class",
            "build a", "make a script", "fix this", "debug this", "refactor",
            "explain this code", "what does this code", "how does this code",
            "solve", "calculate", "compute", "simplify", "derive", "integrate",
            "differentiate", "prove", "evaluate", "factor", "expand",
            "convert this", "translate this code",
        ]
        for starter in code_math_starters:
            if text_lower.startswith(starter):
                return True

        # Contains code blocks — definitely not a web query
        if "```" in text or "def " in text or "function " in text:
            return True
        if "class " in text and (":" in text or "{" in text):
            return True
        if "import " in text and "\n" in text:
            return True

        # Obvious concept/definition questions — never need web
        concept_starters = [
            "what is a ", "what is an ", "what are ", "what is the difference",
            "explain ", "describe how ", "how does ", "how do ",
            "teach me", "help me understand", "tell me about ",
            "define ", "meaning of ",
        ]
        # BUT exclude questions that sneak in time-sensitive words
        time_words = ["price", "cost", "today", "current", "latest", "now", "worth", "rate"]
        for starter in concept_starters:
            if text_lower.startswith(starter):
                if not any(tw in text_lower for tw in time_words):
                    return True

        return False

    def web_search(self, query: str) -> str:
        """Search using local SearXNG instance."""
        try:
            response = requests.get(
                "http://host.docker.internal:8888/search",
                params={"q": query, "format": "json", "language": "en"},
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            if not results:
                return "No search results found."
            formatted = []
            for r in results[:7]:
                formatted.append(
                    f"Title: {r.get('title', 'N/A')}\n"
                    f"Snippet: {r.get('content', 'N/A')}\n"
                    f"URL: {r.get('url', 'N/A')}"
                )
            return "\n\n".join(formatted)
        except Exception as e:
            return f"Search failed: {type(e).__name__}: {str(e)}"

    def read_url(self, url: str) -> str:
        """Extract main text content from a URL using trafilatura."""
        try:
            import trafilatura

            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return f"Could not download: {url}"
            text = trafilatura.extract(downloaded)
            if not text:
                return f"Could not extract text from: {url}"
            if len(text) > 4000:
                text = text[:4000] + "\n\n[... content truncated at 4000 chars ...]"
            return text
        except ImportError:
            return "URL reading unavailable (trafilatura not installed)."
        except Exception as e:
            return f"Could not read URL: {type(e).__name__}: {str(e)}"

    def _check_web_needed(self, user_message):
        """Ask Nexus if this question needs live web data."""
        prompt = f"""Decide if this question needs LIVE web data to answer accurately.

Say WEB_SEARCH if the question asks about:
- Current prices, stock prices, crypto, exchange rates
- Today's news, recent events, latest updates, what happened
- Weather, sports scores, election results
- Anything that changes daily/weekly and you're unsure about
- Any question with "current", "today", "latest", "right now", "recent"
- Real people's current status, age, net worth
- Reviews or opinions about recent products/movies/games
- Job listings, store hours, event dates

Say WEB_NONE if:
- Math problems, equations, calculations
- Coding help, explanations, tutorials, writing code
- How-to guides, concepts, definitions that don't change
- Opinions, advice, casual conversation, greetings
- Creative writing, brainstorming, jokes
- History (events before 2024)
- Science concepts, laws of physics, chemistry
- General knowledge that does not change over time

IMPORTANT: Only say WEB_SEARCH if the answer would genuinely be WRONG
without current data. Do NOT search for general knowledge questions.

USER MESSAGE: \"\"\"{user_message}\"\"\"

When writing search queries, follow these rules:
- Add the current year (2026) to any query about prices, news, or events
- Add specific units (USD, per ounce, per kg, etc.) for prices
- Make it specific so the search snippet contains the ACTUAL answer
- Think like a Google power user

Reply in EXACTLY this format, nothing else:
WEB_SEARCH: <your optimized search query>
OR just:
WEB_NONE

Examples:
"what's the gold price" → WEB_SEARCH: gold spot price per ounce USD today 2026
"explain bubble sort" → WEB_NONE
"latest Python news" → WEB_SEARCH: Python programming latest news 2026
"write me a for loop" → WEB_NONE
"how's Tesla doing" → WEB_SEARCH: Tesla TSLA stock price USD today 2026
"what is 2+2" → WEB_NONE
"hi" → WEB_NONE
"hello how are you" → WEB_NONE
"weather in Toronto" → WEB_SEARCH: Toronto Ontario weather today temperature 2026
"who is Elon Musk" → WEB_NONE
"what did Elon Musk say today" → WEB_SEARCH: Elon Musk latest news today 2026
"1 USD to INR" → WEB_SEARCH: 1 USD to INR exchange rate today 2026
"bitcoin price" → WEB_SEARCH: bitcoin BTC price USD today 2026
"tell me gold price" → WEB_SEARCH: gold spot price per ounce USD today 2026
"what is recursion" → WEB_NONE
"help me with my code" → WEB_NONE
"who are you" → WEB_NONE"""

        try:
            response = requests.post(
                f"{self.valves.GPU_SERVER}/api/chat",
                json={
                    "model": self.valves.NEXUS_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0, "num_predict": 30},
                },
                timeout=(10, 15),
            )
            response.raise_for_status()
            data = response.json()
            answer = data.get("message", {}).get("content", "").strip()

            if "WEB_SEARCH" in answer.upper():
                if ":" in answer:
                    query = answer.split(":", 1)[1].strip().strip("\"'")
                    if len(query) > 2:
                        return True, query
                return True, user_message
            return False, ""
        except Exception:
            return False, ""

    # ============================================================
    # SECTION 3: TEXT EXTRACTION
    # ============================================================

    def _get_text_content(self, message):
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(part.get("text", ""))
                elif isinstance(part, str):
                    parts.append(part)
            return " ".join(parts)
        return str(content)

    # ============================================================
    # SECTION 4: FETCH IMAGE FROM OPEN WEBUI
    # ============================================================

    def _fetch_image_by_id(self, file_id, auth_token=None):
        """Fetch image from Open WebUI file storage via direct read, return base64 string"""
        import os

        try:
            from open_webui.models.files import Files

            file_info = Files.get_file_by_id(file_id)
            if file_info:
                file_path = None
                if hasattr(file_info, "meta") and isinstance(file_info.meta, dict):
                    file_path = file_info.meta.get("path")
                if not file_path and hasattr(file_info, "path"):
                    file_path = file_info.path

                if file_path and os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode("utf-8")
                    return encoded
        except ImportError:
            pass
        except Exception:
            pass

        upload_paths = [
            f"/app/backend/data/uploads/{file_id}",
            f"/app/backend/data/uploads/{file_id}.png",
            f"/app/backend/data/uploads/{file_id}.jpg",
            f"/app/backend/data/uploads/{file_id}.jpeg",
            f"/app/backend/data/uploads/{file_id}.webp",
            f"/app/backend/data/cache/files/{file_id}",
        ]

        for fpath in upload_paths:
            try:
                if os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode("utf-8")
                    return encoded
            except Exception:
                continue

        return None

    def _is_uuid(self, value):
        """Check if a string looks like a UUID file reference"""
        if not isinstance(value, str):
            return False
        return bool(
            re.match(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                value.lower(),
            )
        )

    # ============================================================
    # SECTION 5: MESSAGE CONVERTER
    # ============================================================

    def _convert_messages_for_ollama(self, messages, auth_token=None):
        converted = []
        for msg in messages:
            content = msg.get("content", "")

            if isinstance(content, str):
                new_msg = {"role": msg["role"], "content": content}
                if msg.get("images"):
                    new_msg["images"] = msg["images"]
                converted.append(new_msg)
                continue

            if isinstance(content, list):
                text_parts = []
                image_parts = []
                for part in content:
                    if not isinstance(part, dict):
                        text_parts.append(str(part))
                        continue
                    if part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif part.get("type") == "image_url":
                        image_url = part.get("image_url", {})
                        url = (
                            image_url.get("url", "")
                            if isinstance(image_url, dict)
                            else str(image_url)
                        )

                        is_uuid_val = self._is_uuid(url)

                        if url.startswith("data:"):
                            base64_data = url.split(",", 1)[-1]
                            image_parts.append(base64_data)
                        elif is_uuid_val:
                            fetched = self._fetch_image_by_id(url, auth_token)
                            if fetched:
                                image_parts.append(fetched)
                        elif url.startswith("http"):
                            try:
                                resp = requests.get(url, timeout=10)
                                if resp.status_code == 200:
                                    image_parts.append(
                                        base64.b64encode(resp.content).decode("utf-8")
                                    )
                            except Exception:
                                pass
                        elif url:
                            image_parts.append(url)

                new_msg = {
                    "role": msg["role"],
                    "content": (
                        " ".join(text_parts)
                        if text_parts
                        else "Describe this image in detail."
                    ),
                }
                if image_parts:
                    new_msg["images"] = image_parts
                converted.append(new_msg)
                continue

            converted.append({"role": msg["role"], "content": str(content)})
        return converted

    # ============================================================
    # SECTION 6: NEXUS SMART ROUTER
    # ============================================================

    def _ask_nexus_to_route(self, user_message):
        routing_prompt = f"""You are Nexus, coordinator of HIVE. Decide who handles this message.

YOU handle most things yourself:
- Conversation, greetings, opinions, general knowledge
- Simple math (2+2, percentages, basic algebra, derivatives)
- Simple code (short functions, loops, basic scripts)
- Explanations, summaries, translations
- Simple advice and basic planning
- Web search result presentation

ONLY delegate when genuinely outmatched:

BOLT — ONLY when:
- COMPLEX algorithms with specific constraints
- FULL programs, applications, multi-file projects
- Real buggy code to debug (tracebacks, error logs)
- Advanced computational math SOLVED WITH CODE

NOVA — ONLY when:
- DEEP multi-step logical reasoning needed
- Advanced theoretical math (proofs, symbolic calculus)
- Complex strategic analysis with multiple tradeoffs
- Understanding genuinely NEW complex topics

EYE — ONLY when:
- User mentions an image, picture, photo, screenshot
- User says "describe this", "what's in this", "look at this"
- ANY mention of seeing or analyzing visuals

EXAMPLES:
"what is 2+2" → NEXUS
"write a for loop" → NEXUS
"explain bubble sort" → NEXUS
"hi how are you" → NEXUS
"what is gold price" → NEXUS
"describe this image" → EYE
"what's in this picture" → EYE
"implement quicksort O(1) space" → BOLT
"build me a full REST API" → BOLT
"prove sqrt(2) is irrational" → NOVA
"derive the Navier-Stokes equations" → NOVA

USER MESSAGE: \"\"\"{user_message}\"\"\"

One word only: NEXUS, BOLT, NOVA, or EYE"""

        try:
            response = requests.post(
                f"{self.valves.GPU_SERVER}/api/chat",
                json={
                    "model": self.valves.NEXUS_MODEL,
                    "messages": [{"role": "user", "content": routing_prompt}],
                    "stream": False,
                    "options": {"temperature": 0, "num_predict": 10},
                },
                timeout=(10, 30),
            )
            response.raise_for_status()
            data = response.json()
            answer = data.get("message", {}).get("content", "").strip().upper()

            if "BOLT" in answer:
                return (
                    self.valves.BOLT_MODEL,
                    self.valves.GPU_SERVER,
                    "Bolt (Nexus decided: expert coding needed)",
                )
            elif "NOVA" in answer:
                return (
                    self.valves.NOVA_MODEL,
                    self.valves.CPU_SERVER,
                    "Nova (Nexus decided: deep reasoning needed)",
                )
            elif "EYE" in answer:
                return (
                    self.valves.EYE_MODEL,
                    self.valves.GPU_SERVER,
                    "Eye (Nexus decided: visual analysis needed)",
                )
            else:
                return (
                    self.valves.NEXUS_MODEL,
                    self.valves.GPU_SERVER,
                    "Nexus (handling it himself)",
                )

        except Exception as e:
            return (
                self.valves.NEXUS_MODEL,
                self.valves.GPU_SERVER,
                f"Nexus (routing fallback — {type(e).__name__})",
            )

    # ============================================================
    # SECTION 7: MAIN HANDLER — ASYNC
    # ============================================================

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __request__=None,
    ) -> Union[str, AsyncGenerator]:

        # --- Get RAW body from request (contains images) ---
        raw_body = body
        if __request__:
            try:
                raw_body = await __request__.json()
            except Exception:
                raw_body = body

        raw_messages = raw_body.get("messages", [])
        stream = body.get("stream", False)

        # --- Extract auth token for image fetching ---
        auth_token = None
        if __request__:
            auth_header = __request__.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                auth_token = auth_header[7:]
            elif hasattr(__request__, "cookies"):
                auth_token = __request__.cookies.get("token")

        # --- Image detection on RAW messages ---
        image_check = self._check_for_images(raw_messages)

        # ===========================================================
        # WEB BROWSING DETECTION — runs BEFORE routing
        # Layer 1: _quick_web_skip() — instant keyword check, no LLM call
        # Layer 2: _check_web_needed() — asks Nexus (only if Layer 1 didn't skip)
        # Layer 3: URL regex — always reads URLs if user pastes one
        # ===========================================================
        web_context = ""
        if not image_check["found"] and raw_messages:
            last_msg_content = self._get_text_content(raw_messages[-1])

            # Layer 3: Check for URLs in user message (regex — always works)
            url_pattern = r"https?://[^\s<>\"\')\]]+"
            urls_in_message = re.findall(url_pattern, last_msg_content)
            if urls_in_message:
                for url in urls_in_message[:2]:
                    content = self.read_url(url)
                    if content and "unavailable" not in content.lower():
                        web_context += (
                            f"\n\n--- Content from {url} ---\n{content}\n--- End ---\n"
                        )

            # Layer 1: Quick keyword skip — no LLM call needed
            elif self._quick_web_skip(last_msg_content):
                # Obviously not a web query — skip entirely, save time
                pass

            # Layer 2: Not obviously skippable — ask Nexus if web is needed
            else:
                needs_web, query = self._check_web_needed(last_msg_content)
                if needs_web and query:
                    query = re.sub(
                        r"^(search for|search|look up|find|google)\s+",
                        "",
                        query,
                        flags=re.IGNORECASE,
                    ).strip()
                    if not any(y in query for y in ["2025", "2026", "2027"]):
                        query += " 2026"
                    if any(
                        w in query.lower()
                        for w in ["price", "cost", "worth", "rate", "exchange"]
                    ):
                        if "today" not in query.lower():
                            query += " today"
                    results = self.web_search(query)
                    if results and "unavailable" not in results.lower():
                        web_context = f"\n\n--- Web Search Results for '{query}' ---\n{results}\n--- End Search Results ---\n"

                        # Also read the top result's actual page for deeper data
                        try:
                            first_url_match = re.search(
                                r"URL: (https?://[^\s]+)", results
                            )
                            if first_url_match:
                                top_url = first_url_match.group(1)
                                page_content = self.read_url(top_url)
                                if (
                                    page_content
                                    and "unavailable" not in page_content.lower()
                                    and "Could not" not in page_content
                                ):
                                    web_context += f"\n\n--- Full Page Content from {top_url} ---\n{page_content}\n--- End Full Page ---\n"
                        except Exception:
                            pass

        # Inject web context into messages if found
        web_header = ""
        if web_context:
            snippets = re.findall(r"Snippet: (.+)", web_context)
            urls_found = re.findall(r"URL: (https?://[^\s]+)", web_context)

            # Build clean summary the USER sees directly (before Nexus responds)
            web_header = "🌐 **Live Web Results:**\n\n"
            for i, snippet in enumerate(snippets[:3]):
                source = urls_found[i] if i < len(urls_found) else ""
                domain = re.search(r"https?://(?:www\.)?([^/]+)", source)
                domain_name = domain.group(1) if domain else "unknown"
                web_header += f"**{domain_name}:** {snippet.strip()}\n\n"
            web_header += "---\n\n"

            # Inject web data into system message for Nexus to read
            system_injection = (
                "LIVE WEB DATA — QUOTE EXACTLY, DO NOT CHANGE ANY NUMBERS:\n"
                + web_context
                + "\n\nRULES:\n"
                "1. ONLY state numbers that appear EXACTLY in the web data above\n"
                "2. If you cannot find an exact number in the data, say 'the search results did not contain an exact figure'\n"
                "3. DO NOT round, estimate, or generate any numbers yourself\n"
                "4. Copy-paste the exact price/rate from the snippets\n"
                "5. Name the source website\n"
            )
            system_found = False
            for msg in raw_messages:
                if msg["role"] == "system":
                    if isinstance(msg["content"], str):
                        msg["content"] += "\n\n" + system_injection
                    system_found = True
                    break
            if not system_found:
                raw_messages.insert(0, {"role": "system", "content": system_injection})

        # --- Routing decision ---
        if image_check["found"]:
            model_name = self.valves.EYE_MODEL
            server_url = self.valves.GPU_SERVER
            reason = "Eye (image detected — routed directly)"
        else:
            last_message = raw_messages[-1] if raw_messages else {}
            user_text = self._get_text_content(last_message)
            model_name, server_url, reason = self._ask_nexus_to_route(user_text)

        # --- Convert RAW messages to Ollama format (with image fetching) ---
        ollama_messages = self._convert_messages_for_ollama(raw_messages, auth_token)

        # --- Build payload ---
        payload = {
            "model": model_name,
            "messages": ollama_messages,
            "stream": stream,
        }

        if model_name == self.valves.EYE_MODEL:
            payload["stream"] = False
            stream = False

        if model_name == self.valves.NOVA_MODEL:
            payload["think"] = True

        if "options" in body:
            payload["options"] = body["options"]

        url = f"{server_url}/api/chat"

        # --- Send to model ---
        try:
            if stream:

                async def stream_gen():
                    yield f"**🐝 HIVE → {reason}**\n\n"
                    if web_header:
                        yield web_header

                    is_nova = model_name == self.valves.NOVA_MODEL
                    show_thinking = is_nova and self.valves.SHOW_THINKING
                    thinking_started = False
                    answer_started = False

                    response = requests.post(
                        url, json=payload, stream=True, timeout=(10, 300)
                    )
                    response.raise_for_status()

                    for line in response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)

                                thinking = data.get("message", {}).get("thinking", "")
                                if thinking and show_thinking:
                                    if not thinking_started:
                                        yield "💭 **Nova is thinking...**\n\n*"
                                        thinking_started = True
                                    yield thinking

                                content = data.get("message", {}).get("content", "")
                                if content:
                                    if thinking_started and not answer_started:
                                        yield "*\n\n📝 **Answer:**\n\n"
                                        answer_started = True
                                    yield content

                                if data.get("done", False):
                                    if thinking_started and not answer_started:
                                        yield "*\n\n"
                                    break
                            except json.JSONDecodeError:
                                continue

                return stream_gen()

            else:
                response = requests.post(url, json=payload, timeout=(10, 300))
                response.raise_for_status()
                data = response.json()
                content = data.get("message", {}).get("content", "")
                thinking = data.get("message", {}).get("thinking", "")

                result = f"**🐝 HIVE → {reason}**\n\n"
                if web_header:
                    result += web_header

                if thinking and self.valves.SHOW_THINKING:
                    result += (
                        f"💭 **Nova's thinking:**\n\n*{thinking}*\n\n📝 **Answer:**\n\n"
                    )
                result += content
                return result

        except requests.exceptions.HTTPError as e:
            error_body = ""
            try:
                error_body = e.response.text[:500]
            except:
                error_body = "Could not read error body"
            return f"❌ **HIVE Error (HTTP {e.response.status_code}):**\n```\n{error_body}\n```"
        except requests.exceptions.ConnectionError:
            return f"❌ **HIVE Error:** Cannot connect to `{server_url}`."
        except Exception as e:
            return f"❌ **HIVE Error:** {type(e).__name__}: {str(e)}"