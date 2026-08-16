#!/usr/bin/env python
"""Translate model-native tool-call text into real OpenAI tool_calls.
[CHANGE: claude-code | 2026-08-05] Phase 0b — makes agent frameworks work locally.

GEMMA SPEAKS A DIFFERENT DIALECT, AND THIS FILE ONLY KNEW QWEN'S
---------------------------------------------------------------
[CHANGE: claude-code | 2026-08-16] BUG-133. When DECISION 74 put gemma-4-26B on
the port and DECISION 75 replaced Qwen3-4B with gemma-4-E4B, tool calling stopped
working and nothing said so. Gemma does not emit Qwen's `<tool_call>{json}`; it
emits its own syntax, which fell straight through the parser below as prose:

    content:    '<|tool_call>call:get_weather{city:<|"|>Toronto<|"|>}<tool_call|>'
    tool_calls: null
    finish_reason: 'stop'          <- looks like a perfectly normal answer

Both dialects are parsed now. The Qwen half is kept because it costs nothing and
is already proven; nothing on this box currently serves a Qwen.

THE ROUND TRIP IS THE HARD PART, AND THE TWO LAYERS CONTRADICT EACH OTHER
------------------------------------------------------------------------
MEASURED against llama-cpp-python 0.3.34 with the Gemma 4 template:

  * assistant.tool_calls with arguments as a **dict**   -> 500, request schema
    rejects it (ChatCompletionMessageToolCall.function.arguments must be a str)
  * assistant.tool_calls with arguments as a **string** -> 500, the GGUF template
    itself raises: "arguments must be a JSON object (mapping), not a string"

So there is NO way to hand structured tool calls back to this server: the schema
demands a string and the template demands a dict. Replaying history therefore has
to go back as TEXT, in the model's own dialect — which is what `normalize_request`
does, and why it is not merely a workaround for `content: null`.

A second trap rides along. A standalone `role: "tool"` message VALIDATES fine but
is then **silently dropped by the template** — its message loop opens with
`{% if message['role'] != 'tool' %}`, and tool results are only rendered by a
forward-scan from an assistant turn that still carries `tool_calls`. Strip the
tool_calls (as we must, above) and the tool's answer vanishes with no error at
all. So the tool responses are folded into the same assistant text as the calls.
Verified: a hand-built flattened turn came back "The weather in Toronto is 18C and
sunny."

THE ORIGINAL PROBLEM THIS SOLVES
--------------------------------
Qwen3 emits perfectly correct tool calls. llama-cpp-python's server just does not
parse them. Ask it for a tool and you get back:

    content: "<tool_call>\\n{\"name\": \"get_weather\", ...}\\n</tool_call>"
    tool_calls: (absent)

An OpenAI client sees prose, not a tool call, so the agent stalls waiting for a
result it never requested. The two built-in alternatives both fail differently:
  - --chat_format chatml                  -> no tool support; model narrates in markdown
  - --chat_format chatml-function-calling -> returns EMPTY content (6 tokens, stop)
Only the model's own built-in template produces a correct call, and that is the
one path whose output nothing parses. Hence this shim.

The real fix is llama.cpp's own llama-server with --jinja, which parses this
natively — but that binary is unstartable here (BUG-097). Revisit then; this file
should be deleted, not maintained, once BUG-097 is fixed.

WHY IT COLLAPSES STREAMING
--------------------------
A tool call cannot be classified until its closing </tool_call> arrives, so a
faithful streaming translator would have to buffer to the end anyway. This asks
upstream for a non-streamed reply and re-emits it as a single SSE chunk. Clients
see valid SSE; they just do not see it token by token. Tool calls are short, and
correctness beats typewriter effect for an automation pipeline.

127.0.0.1 ONLY — same reasoning as llm-server.sh: no auth, must not be LAN-reachable.
"""
import json
import os
import re
import time
import uuid

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

UPSTREAM = os.environ.get("PROXY_UPSTREAM", "http://127.0.0.1:8081")
# Generation on a 4B can take a while; a short client timeout would look like the
# model failing rather than the proxy giving up.
TIMEOUT = float(os.environ.get("PROXY_TIMEOUT", "600"))

# Qwen wraps each call in <tool_call>...</tool_call>. DOTALL because the JSON is
# pretty-printed across lines. Non-greedy so several calls in one reply stay separate.
TOOL_RE = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)

# ---------------------------------------------------------------------------
# Gemma's dialect. [CHANGE: claude-code | 2026-08-16]
#
#   <|tool_call>call:NAME{key:VALUE,key2:VALUE2}<tool_call|>
#
# Values are NOT JSON. Strings are fenced with the literal five-character token
# <|"|> on both sides; true/false/null and numbers are bare; objects and arrays
# use {} and [] with the same rules inside. Top-level argument keys are bare
# words, but nested object keys may themselves be fenced.
#
# A REGEX CANNOT DO THIS. `\{(.*?)\}` stops at the first `}`, so any nested
# object silently truncates the arguments and the agent acts on half of them —
# a wrong call is worse than no call. Hence the small hand parser below.
GEMMA_CALL_OPEN = "<|tool_call>call:"
GEMMA_CALL_CLOSE = "<tool_call|>"
GEMMA_RESP_OPEN = "<|tool_response>response:"
GEMMA_RESP_CLOSE = "<tool_response|>"
GEMMA_QUOTE = '<|"|>'

app = FastAPI()


class _GemmaValue:
    """Recursive-descent reader for one Gemma argument value.

    Deliberately strict: anything it cannot read raises, and the caller then
    leaves the text alone rather than guessing. Inventing arguments the model
    never produced is the one failure mode worth refusing outright.
    """

    def __init__(self, s: str, i: int = 0):
        self.s, self.i = s, i

    def _peek(self) -> str:
        return self.s[self.i] if self.i < len(self.s) else ""

    def _eat(self, tok: str) -> None:
        if not self.s.startswith(tok, self.i):
            raise ValueError(f"expected {tok!r} at {self.i}")
        self.i += len(tok)

    def value(self):
        if self.s.startswith(GEMMA_QUOTE, self.i):
            return self.string()
        c = self._peek()
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        return self.scalar()

    def string(self) -> str:
        self._eat(GEMMA_QUOTE)
        end = self.s.find(GEMMA_QUOTE, self.i)
        if end < 0:
            raise ValueError("unterminated string")
        out = self.s[self.i:end]
        self.i = end + len(GEMMA_QUOTE)
        return out

    def obj(self) -> dict:
        self._eat("{")
        out = {}
        if self._peek() == "}":
            self.i += 1
            return out
        while True:
            key = self.string() if self.s.startswith(GEMMA_QUOTE, self.i) else self.bareword()
            self._eat(":")
            out[key] = self.value()
            if self._peek() == ",":
                self.i += 1
                continue
            self._eat("}")
            return out

    def arr(self) -> list:
        self._eat("[")
        out = []
        if self._peek() == "]":
            self.i += 1
            return out
        while True:
            out.append(self.value())
            if self._peek() == ",":
                self.i += 1
                continue
            self._eat("]")
            return out

    def bareword(self) -> str:
        start = self.i
        while self.i < len(self.s) and self.s[self.i] not in ":,}]":
            self.i += 1
        word = self.s[start:self.i].strip()
        if not word:
            raise ValueError("empty key")
        return word

    def scalar(self):
        start = self.i
        while self.i < len(self.s) and self.s[self.i] not in ",}]":
            self.i += 1
        raw = self.s[start:self.i].strip()
        if raw == "true":
            return True
        if raw == "false":
            return False
        if raw == "null":
            return None
        for cast in (int, float):
            try:
                return cast(raw)
            except ValueError:
                pass
        # An unfenced word. Not valid output from the template, but returning it
        # as text beats failing the whole call over one odd argument.
        return raw


def _extract_gemma_calls(content: str):
    """Return (remaining_text, calls) for Gemma's <|tool_call> syntax."""
    calls, cuts, i = [], [], 0
    while True:
        start = content.find(GEMMA_CALL_OPEN, i)
        if start < 0:
            break
        after = start + len(GEMMA_CALL_OPEN)
        brace = content.find("{", after)
        if brace < 0:
            break
        name = content[after:brace].strip()
        reader = _GemmaValue(content, brace)
        try:
            args = reader.obj()
        except ValueError:
            # Unparseable — skip past the opener and keep the text as prose.
            i = after
            continue
        close = content.find(GEMMA_CALL_CLOSE, reader.i)
        end = close + len(GEMMA_CALL_CLOSE) if close >= 0 else reader.i
        if name:
            calls.append({
                "id": f"call_{uuid.uuid4().hex[:24]}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            })
            cuts.append((start, end))
        i = end

    if not calls:
        return content, []
    out, prev = [], 0
    for start, end in cuts:
        out.append(content[prev:start])
        prev = end
    out.append(content[prev:])
    return "".join(out).strip(), calls


def extract_tool_calls(content: str):
    """Return (remaining_text, tool_calls). tool_calls is [] when there are none."""
    if not content:
        return content, []

    if GEMMA_CALL_OPEN in content:
        return _extract_gemma_calls(content)

    if "<tool_call>" not in content:
        return content, []

    calls = []
    for raw in TOOL_RE.findall(content):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Malformed JSON is NOT a tool call. Leaving it in the text is the
            # honest outcome — inventing a call here would make the agent act on
            # arguments the model never actually produced.
            continue
        name = parsed.get("name")
        if not name:
            continue
        calls.append({
            "id": f"call_{uuid.uuid4().hex[:24]}",
            "type": "function",
            "function": {
                "name": name,
                # OpenAI sends arguments as a JSON *string*, not an object.
                "arguments": json.dumps(parsed.get("arguments", {})),
            },
        })

    if not calls:
        return content, []
    return TOOL_RE.sub("", content).strip(), calls


def _gemma_literal(value) -> str:
    """Render one Python value the way Gemma's own template renders it."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return GEMMA_QUOTE + value + GEMMA_QUOTE
    if isinstance(value, (int, float)):
        return json.dumps(value)
    if isinstance(value, dict):
        # `| dictsort` in the template — key order is sorted, so match it.
        return "{" + ",".join(f"{k}:{_gemma_literal(v)}"
                              for k, v in sorted(value.items())) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_gemma_literal(v) for v in value) + "]"
    return GEMMA_QUOTE + str(value) + GEMMA_QUOTE


def _gemma_call_block(name: str, args: dict) -> str:
    body = ",".join(f"{k}:{_gemma_literal(v)}" for k, v in sorted((args or {}).items()))
    return f"{GEMMA_CALL_OPEN}{name}{{{body}}}{GEMMA_CALL_CLOSE}"


def _gemma_response_block(name: str, response) -> str:
    if isinstance(response, dict):
        body = ",".join(f"{k}:{_gemma_literal(v)}" for k, v in sorted(response.items()))
    else:
        body = f"value:{_gemma_literal(response)}"
    return f"{GEMMA_RESP_OPEN}{name}{{{body}}}{GEMMA_RESP_CLOSE}"


def flatten_content(content) -> str:
    """Content may be a string, None, or a list of typed parts. We need a string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            p.get("text", "") for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        )
    return str(content)


def _call_args(call: dict) -> dict:
    """OpenAI ships arguments as a JSON string; we need the object."""
    args = (call.get("function") or {}).get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    return args if isinstance(args, dict) else {}


def normalize_request(body: dict) -> dict:
    """Undo the translation on the way back in.

    Once the agent has made a tool call, its NEXT request replays the history —
    including the assistant turn we rewrote. That turn now has tool_calls and
    content=None, and llama-cpp-python's request schema rejects both: assistant
    content must be a string, never null. So the conversation dies on turn two,
    after tool calling appeared to work.

    Fix: fold the whole exchange back into the text the model itself produced.

    [CHANGE: claude-code | 2026-08-16] BUG-133 — this now emits GEMMA's dialect,
    because every model on this port is a Gemma. Two things had to change:

    1. The call blocks are `<|tool_call>call:NAME{...}<tool_call|>`, not Qwen's
       `<tool_call>{json}</tool_call>`. Sending Qwen's form to a Gemma replays
       history the model cannot read — it would see its own tool call as prose.

    2. The tool RESULTS are folded in here too, and the `role: "tool"` messages
       are dropped. This is not tidiness. Gemma's template opens its message loop
       with `{% if message['role'] != 'tool' %}` and only renders tool results by
       forward-scanning from an assistant turn that still carries `tool_calls` —
       which we just had to strip, because the server's schema and the template
       disagree about whether arguments are a string or a dict and there is no
       value that satisfies both. Leave the tool messages in place and they are
       silently discarded: the model answers as if the tool never ran, with no
       error anywhere.

    If a non-Gemma model is ever served here again, this function is the thing
    that has to learn a second dialect. The parser on the way out already knows
    both; only this direction has to choose.
    """
    original_messages = body.get("messages") or []

    # tool_call_id -> function name, so a tool result can name the tool it came
    # from. The template keys its response block on the NAME, not the id.
    call_names = {}
    for msg in original_messages:
        for call in msg.get("tool_calls") or []:
            if call.get("id"):
                call_names[call["id"]] = (call.get("function") or {}).get("name", "unknown")

    messages = []
    skip_until = -1
    for index, original in enumerate(original_messages):
        if index <= skip_until:
            continue
        msg = dict(original)
        text = flatten_content(msg.get("content"))

        if msg.get("role") == "assistant":
            calls = msg.pop("tool_calls", None) or []
            blocks = [_gemma_call_block((c.get("function") or {}).get("name", ""),
                                        _call_args(c))
                      for c in calls if (c.get("function") or {}).get("name")]
            if blocks:
                # Consume the tool results that answer these calls, so they land
                # inside the same model turn the way the template would place them.
                follow = index + 1
                while follow < len(original_messages) \
                        and original_messages[follow].get("role") == "tool":
                    result = original_messages[follow]
                    name = call_names.get(result.get("tool_call_id")) \
                        or result.get("name") or "unknown"
                    blocks.append(_gemma_response_block(
                        name, flatten_content(result.get("content"))))
                    follow += 1
                skip_until = follow - 1
                text = (text + "".join(blocks)).strip()

        msg["content"] = text
        messages.append(msg)

    body["messages"] = messages
    return body


def rewrite(payload: dict) -> dict:
    for choice in payload.get("choices", []):
        msg = choice.get("message")
        if not isinstance(msg, dict):
            continue
        text, calls = extract_tool_calls(msg.get("content") or "")
        if not calls:
            continue
        msg["tool_calls"] = calls
        # OpenAI sets content to null when the turn is purely a tool call.
        msg["content"] = text or None
        choice["finish_reason"] = "tool_calls"
    return payload


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    wants_stream = bool(body.get("stream"))
    body["stream"] = False  # see WHY IT COLLAPSES STREAMING above
    body = normalize_request(body)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(f"{UPSTREAM}/v1/chat/completions", json=body)

    if r.status_code != 200:
        return JSONResponse(status_code=r.status_code, content=r.json())

    payload = rewrite(r.json())

    if not wants_stream:
        return JSONResponse(content=payload)

    def sse():
        for choice in payload.get("choices", []):
            msg = choice.get("message", {})
            delta = {"role": "assistant"}
            if msg.get("content"):
                delta["content"] = msg["content"]
            if msg.get("tool_calls"):
                # Streaming tool_calls need an index per call or clients drop them.
                delta["tool_calls"] = [
                    {**c, "index": i} for i, c in enumerate(msg["tool_calls"])
                ]
            chunk = {
                "id": payload.get("id", f"chatcmpl-{uuid.uuid4().hex}"),
                "object": "chat.completion.chunk",
                "created": payload.get("created", int(time.time())),
                "model": payload.get("model", "luminos-local"),
                "choices": [{"index": choice.get("index", 0), "delta": delta,
                             "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            stop = dict(chunk)
            stop["choices"] = [{"index": choice.get("index", 0), "delta": {},
                                "finish_reason": choice.get("finish_reason", "stop")}]
            yield f"data: {json.dumps(stop)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")


@app.api_route("/{path:path}", methods=["GET", "POST"])
async def passthrough(path: str, request: Request):
    """Everything else (/v1/models, /v1/embeddings, health) goes straight through."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        if request.method == "GET":
            r = await client.get(f"{UPSTREAM}/{path}")
        else:
            r = await client.post(f"{UPSTREAM}/{path}", content=await request.body(),
                                  headers={"content-type": "application/json"})
    try:
        return JSONResponse(status_code=r.status_code, content=r.json())
    except ValueError:
        return JSONResponse(status_code=r.status_code, content={"raw": r.text})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PROXY_PORT", "8082")),
                log_level="warning")
