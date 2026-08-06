#!/usr/bin/env python
"""Translate Qwen-style <tool_call> text into real OpenAI tool_calls.
[CHANGE: claude-code | 2026-08-05] Phase 0b — makes agent frameworks work locally.

THE PROBLEM THIS SOLVES
-----------------------
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

app = FastAPI()


def extract_tool_calls(content: str):
    """Return (remaining_text, tool_calls). tool_calls is [] when there are none."""
    if not content or "<tool_call>" not in content:
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


def normalize_request(body: dict) -> dict:
    """Undo the translation on the way back in.

    Once the agent has made a tool call, its NEXT request replays the history —
    including the assistant turn we rewrote. That turn now has tool_calls and
    content=None, and llama-cpp-python's request schema rejects both: assistant
    content must be a string, never null. So the conversation dies on turn two,
    after tool calling appeared to work.

    Fix: fold tool_calls back into the exact <tool_call> text the model itself
    produced. The GGUF's own template understands that form, which keeps the
    replayed history identical to what the model generated.
    """
    messages = []
    for original in body.get("messages") or []:
        msg = dict(original)
        text = flatten_content(msg.get("content"))

        if msg.get("role") == "assistant":
            calls = msg.pop("tool_calls", None) or []
            blocks = []
            for call in calls:
                fn = call.get("function", {})
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                blocks.append(
                    "<tool_call>\n"
                    + json.dumps({"name": fn.get("name"), "arguments": args})
                    + "\n</tool_call>"
                )
            if blocks:
                text = (text + "\n" + "\n".join(blocks)).strip()

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
