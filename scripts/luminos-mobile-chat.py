#!/usr/bin/env python3
# [CHANGE: antigravity | 2026-08-16]
"""Luminos Mobile Web Chat — Lightweight, mobile-friendly chat for phone browsers.

Zero Docker, Zero OpenClaw. Pure bare-metal FastAPI server serving a clean,
responsive dark-mode web app to your phone over local Wi-Fi or Tailscale.
Talks directly to the local llama.cpp server on 127.0.0.1:8080 (Dolphin/Nexus).
"""

import json
import os
import secrets
import socket
import sys
import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

# [CHANGE: claude-code | 2026-08-24] Was http://127.0.0.1:8081 — that port is
# jobhunt-llm.service, i.e. OpenClaw's own llama.cpp running a 4B model. So this
# "zero OpenClaw" phone client was in fact pointed straight back into the
# OpenClaw stack and never touched Dolphin at all. 8080 is Dolphin (Nexus), as
# launched by hive-start-model.sh. Path is now phone -> this proxy -> Dolphin.
LLM_UPSTREAM = os.environ.get("LLM_UPSTREAM", "http://127.0.0.1:8080")
PORT = int(os.environ.get("MOBILE_CHAT_PORT", "8090"))
HOST = os.environ.get("MOBILE_CHAT_HOST", "0.0.0.0")

# [CHANGE: claude-code | 2026-08-24] Privacy. This port is the ONLY thing bound
# to the LAN (llama.cpp stays on 127.0.0.1), so it is the entire attack surface.
# Plain HTTP meant every prompt and reply crossed the Wi-Fi in cleartext,
# readable by the router and by any device holding the WPA2 PSK. TLS hides the
# content; the token stops strangers using the model at all.
CONF_DIR = os.path.expanduser("~/.local/share/luminos/mobile-chat")
SSL_CERT = os.environ.get("MOBILE_CHAT_CERT", os.path.join(CONF_DIR, "cert.pem"))
SSL_KEY = os.environ.get("MOBILE_CHAT_KEY", os.path.join(CONF_DIR, "key.pem"))
TOKEN_FILE = os.path.join(CONF_DIR, "token.txt")


def load_token():
    try:
        with open(TOKEN_FILE) as fh:
            return fh.read().strip()
    except OSError:
        sys.exit(f"FATAL: no token at {TOKEN_FILE}\n"
                 f"Create one with: openssl rand -hex 16 > {TOKEN_FILE}")


TOKEN = load_token()

app = FastAPI(title="Luminos Mobile Chat")


@app.middleware("http")
async def require_token(request: Request, call_next):
    """Gate every route. The token arrives once as ?k=..., then rides in a cookie.

    compare_digest rather than == so a wrong guess cannot be narrowed down by
    timing the response.
    """
    if secrets.compare_digest(request.cookies.get("lmc", ""), TOKEN):
        return await call_next(request)

    supplied = request.query_params.get("k", "")
    if supplied and secrets.compare_digest(supplied, TOKEN):
        response = await call_next(request)
        response.set_cookie(
            "lmc", TOKEN,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="strict",
            secure=True,
        )
        return response

    return JSONResponse({"detail": "unauthorized"}, status_code=401)

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Luminos Local Chat</title>
  <style>
    :root {
      --bg: #0d0f12;
      --panel: #16191f;
      --card: #1c2028;
      --border: #2b313d;
      --accent: #6366f1;
      --accent-glow: rgba(99, 102, 241, 0.25);
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --user-msg: #312e81;
      --ai-msg: #1a202c;
      --code-bg: #090b0e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100dvh;
      overflow: hidden;
    }
    header {
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      padding: 10px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      z-index: 10;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 700;
      font-size: 1.05rem;
      letter-spacing: -0.3px;
    }
    .brand span { color: var(--accent); }
    .header-controls {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    select {
      background: var(--card);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 6px 10px;
      font-size: 0.85rem;
      font-weight: 500;
      outline: none;
      max-width: 170px;
    }
    .btn-clear {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-muted);
      border-radius: 8px;
      padding: 6px 10px;
      font-size: 0.82rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .btn-clear:active { background: var(--card); }
    main {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      scroll-behavior: smooth;
    }
    .msg {
      max-width: 90%;
      padding: 12px 15px;
      border-radius: 16px;
      line-height: 1.5;
      font-size: 0.95rem;
      word-wrap: break-word;
      animation: fadeIn 0.15s ease-out;
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
    .msg.user {
      align-self: flex-end;
      background: var(--user-msg);
      color: #ffffff;
      border-bottom-right-radius: 4px;
    }
    .msg.ai {
      align-self: flex-start;
      background: var(--ai-msg);
      border: 1px solid var(--border);
      border-bottom-left-radius: 4px;
    }
    .msg pre {
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      margin: 8px 0;
      overflow-x: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85rem;
    }
    .msg code {
      background: var(--code-bg);
      padding: 2px 5px;
      border-radius: 4px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.88rem;
    }
    .msg pre code { background: none; padding: 0; }
    .typing {
      display: inline-block;
      width: 7px;
      height: 14px;
      background: var(--accent);
      margin-left: 4px;
      vertical-align: middle;
      animation: blink 0.8s infinite;
    }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
    footer {
      background: var(--panel);
      border-top: 1px solid var(--border);
      padding: 10px 12px;
      display: flex;
      gap: 8px;
      align-items: flex-end;
    }
    textarea {
      flex: 1;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      color: var(--text);
      padding: 10px 14px;
      font-size: 0.95rem;
      resize: none;
      max-height: 120px;
      min-height: 44px;
      line-height: 1.4;
      outline: none;
      font-family: inherit;
    }
    textarea:focus { border-color: var(--accent); }
    .btn-send {
      background: var(--accent);
      border: none;
      color: white;
      width: 44px;
      height: 44px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      flex-shrink: 0;
      transition: opacity 0.15s;
    }
    .btn-send:disabled { opacity: 0.4; cursor: not-allowed; }
    .empty-state {
      margin: auto;
      text-align: center;
      color: var(--text-muted);
      padding: 20px;
    }
    .empty-state h3 { color: var(--text); margin-bottom: 6px; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span>●</span> Luminos Phone
    </div>
    <div class="header-controls">
      <select id="modelSelect">
        <option value="luminos-dolphin">🐬 Dolphin 3.0 (36k)</option>
        <option value="luminos-local">⚡ Gemma 4 E4B (24k)</option>
        <option value="luminos-local-moe">🧠 Gemma 26B MoE</option>
      </select>
      <button class="btn-clear" id="btnClear" title="Clear Chat">Clear</button>
    </div>
  </header>

  <main id="chat">
    <div class="empty-state" id="emptyState">
      <h3>Ready to Chat</h3>
      <p>Direct casual chat with your local AI model.</p>
    </div>
  </main>

  <footer>
    <textarea id="promptInput" placeholder="Message your local model..." rows="1"></textarea>
    <button class="btn-send" id="btnSend">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <line x1="22" y1="2" x2="11" y2="13"></line>
        <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
      </svg>
    </button>
  </footer>

  <script>
    const chatEl = document.getElementById("chat");
    const emptyState = document.getElementById("emptyState");
    const promptInput = document.getElementById("promptInput");
    const btnSend = document.getElementById("btnSend");
    const btnClear = document.getElementById("btnClear");
    const modelSelect = document.getElementById("modelSelect");

    let history = [];
    let isGenerating = false;

    // Load saved model
    const savedModel = localStorage.getItem("luminos_selected_model");
    if (savedModel) modelSelect.value = savedModel;
    modelSelect.addEventListener("change", () => {
      localStorage.setItem("luminos_selected_model", modelSelect.value);
    });

    // Auto-expand textarea
    promptInput.addEventListener("input", () => {
      promptInput.style.height = "auto";
      promptInput.style.height = Math.min(promptInput.scrollHeight, 120) + "px";
    });

    promptInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    btnSend.addEventListener("click", sendMessage);
    btnClear.addEventListener("click", () => {
      history = [];
      chatEl.innerHTML = "";
      chatEl.appendChild(emptyState);
    });

    function formatContent(text) {
      // Basic markdown formatting for code blocks and inline code
      let formatted = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

      // Fenced code blocks
      formatted = formatted.replace(/```([a-zA-Z0-9_-]*)\\n([\\s\\S]*?)```/g, (match, lang, code) => {
        return `<pre><code>${code.trim()}</code></pre>`;
      });

      // Inline code
      formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
      // Line breaks
      formatted = formatted.replace(/\\n/g, "<br>");
      return formatted;
    }

    async function sendMessage() {
      const text = promptInput.value.trim();
      if (!text || isGenerating) return;

      if (emptyState.parentNode) emptyState.remove();

      // Add user message
      history.push({ role: "user", content: text });
      appendMessage("user", text);
      promptInput.value = "";
      promptInput.style.height = "44px";

      // Create AI message container
      const aiDiv = appendMessage("ai", "");
      const cursor = document.createElement("span");
      cursor.className = "typing";
      aiDiv.appendChild(cursor);

      isGenerating = true;
      btnSend.disabled = true;

      let fullAiText = "";

      // [CHANGE: claude-code | 2026-08-24] Was history.slice(-16). A fixed turn
      // count either wasted the context window on short turns or overran it on
      // long ones. Budget by characters instead (~4 chars/token), newest first,
      // reserving room for the 2048-token reply.
      // [CHANGE: claude-code | 2026-08-25] 32000 -> 44000 to match ctx 16384.
      const CHAR_BUDGET = 44000;
      const payloadMessages = [];
      let used = 0;
      for (let i = history.length - 1; i >= 0; i--) {
        used += history[i].content.length;
        if (used > CHAR_BUDGET && payloadMessages.length) break;
        payloadMessages.unshift(history[i]);
      }

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: modelSelect.value,
            messages: payloadMessages
          })
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Server returned ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\\n");
          buffer = lines.pop(); // keep partial line

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || !trimmed.startsWith("data:")) continue;
            const dataStr = trimmed.slice(5).trim();
            if (dataStr === "[DONE]") continue;

            try {
              const data = JSON.parse(dataStr);
              const delta = data.choices?.[0]?.delta?.content || "";
              if (delta) {
                fullAiText += delta;
                aiDiv.innerHTML = formatContent(fullAiText);
                aiDiv.appendChild(cursor);
                chatEl.scrollTop = chatEl.scrollHeight;
              }
            } catch (e) {}
          }
        }

        cursor.remove();
        aiDiv.innerHTML = formatContent(fullAiText);
        history.push({ role: "assistant", content: fullAiText });
      } catch (err) {
        cursor.remove();
        aiDiv.innerHTML = `<span style="color:#ef4444;">Error: ${err.message}</span>`;
      } finally {
        isGenerating = false;
        btnSend.disabled = false;
        chatEl.scrollTop = chatEl.scrollHeight;
      }
    }

    function appendMessage(role, text) {
      const div = document.createElement("div");
      div.className = `msg ${role}`;
      div.innerHTML = formatContent(text);
      chatEl.appendChild(div);
      chatEl.scrollTop = chatEl.scrollHeight;
      return div;
    }
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_PAGE

@app.get("/api/info")
async def info():
    return {"status": "ok", "lan_ip": get_lan_ip(), "port": PORT}

@app.post("/api/chat")
async def chat_proxy(request: Request):
    body = await request.json()
    model = body.get("model", "luminos-dolphin")
    messages = body.get("messages", [])

    upstream_payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 2048,
        "temperature": 0.7,
    }

    async def stream_generator():
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{LLM_UPSTREAM}/v1/chat/completions",
                json=upstream_payload,
                headers={"Content-Type": "application/json"}
            ) as upstream_response:
                if upstream_response.status_code != 200:
                    err_body = await upstream_response.aread()
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': f'Model error ({upstream_response.status_code}): {err_body.decode()}'}}]})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                # [CHANGE: claude-code | 2026-08-25] These three yields used to
                # end in \\n\\n, which is an ESCAPED backslash in Python source:
                # it emitted the two characters \ and n, not a newline. SSE frames
                # are delimited by a blank line, so the whole stream arrived as
                # one unbroken line and the browser's split("\n") never found a
                # boundary — the phone showed nothing at all. Measured on the
                # wire before the fix: 1 real newline, 24 literal "\n" strings.
                # Note the \\n on the JS side of HTML_PAGE ARE correct: that
                # string is Python-escaped once so the browser sees \n.
                async for line in upstream_response.aiter_lines():
                    if line:
                        yield f"{line}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

def main():
    lan_ip = get_lan_ip()
    for path in (SSL_CERT, SSL_KEY):
        if not os.path.exists(path):
            sys.exit(f"FATAL: missing TLS material at {path}")

    url = f"https://{lan_ip}:{PORT}/?k={TOKEN}"
    print("===========================================================")
    print("  Luminos Mobile Phone Chat Server Active!  [HTTPS + token]")
    print("  Open this URL on your phone (same Wi-Fi):")
    print(f"  --> {url}")
    print("  Your phone will warn once about the self-signed cert.")
    print("===========================================================")
    uvicorn.run(
        app, host=HOST, port=PORT, log_level="warning",
        ssl_certfile=SSL_CERT, ssl_keyfile=SSL_KEY,
    )

if __name__ == "__main__":
    main()
