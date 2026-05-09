#!/usr/bin/env python3
# HIVE Backend — inference + chat persistence (no HTTP)
# [CHANGE: claude-code | 2026-05-08]
# Imported by hive-popup-app.py, bridged to JS via QWebChannel.

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from hive_context import get_system_context, get_brain_context, log_incident

CHATS_DIR = Path.home() / ".local/share/luminos/hive-chats"
CHATS_DIR.mkdir(parents=True, exist_ok=True)

LLAMA_SERVER = "http://127.0.0.1:8080"


def route_model(text):
    lower = text.lower()
    for kw in ["code", "script", "write"]:
        if kw in lower:
            return "bolt"
    return "nexus"


def build_prompt(history, current_msg, model, sys_ctx=None, brain_ctx=""):
    lines = []
    
    # System Context String
    if sys_ctx:
        sys_info = f"""
CURRENT SYSTEM STATE:
RAM: {sys_ctx['ram_used']}GB used of {sys_ctx['ram_total']}GB ({sys_ctx['ram_available']}GB available)
CPU Temperature: {sys_ctx['cpu_temp']}°C
Power Profile: {sys_ctx['profile']}
Services: {sys_ctx['services_status']}
"""
    else:
        sys_info = ""

    knowledge = f"\nRELEVANT KNOWLEDGE:\n{brain_ctx}\n" if brain_ctx else ""

    system_prompt = f"""You are HIVE, the local AI assistant for Luminos OS.
You are a security guard — observe, report, guide.
Never fix things yourself. Guide the user.
{sys_info}{knowledge}
RULES:
- If asked about Python/venv: always check brain context before answering
- If something seems risky: say NO and explain why
- Keep answers short and direct
- Cite which rule or incident you're referencing"""

    lines.append(f"<|system|>\n{system_prompt}</s>")

    for msg in history[-10:]:
        role = "user" if msg["role"] == "user" else "assistant"
        lines.append(f"<|{role}|>\n{msg['content']}</s>")

    lines.append(f"<|user|>\n{current_msg}</s>")
    lines.append("<|assistant|>\n")
    return "\n".join(lines)


def chat(message, model, history):
    if not message or not message.strip():
        return {"error": "empty message"}

    model_key = model or route_model(message)

    # [CHANGE: gemini-cli | 2026-05-09] Context injection
    sys_ctx = get_system_context()
    brain_ctx = get_brain_context(message)

    prompt = build_prompt(history or [], message, model_key, sys_ctx, brain_ctx)

    try:
        r = requests.post(
            f"{LLAMA_SERVER}/completion",
            json={
                "prompt": prompt,
                "n_predict": 256,
                "temperature": 0.7,
                "top_p": 0.9,
                "stop": ["User:", "Assistant:", "</s>"],
            },
            timeout=120,
        )
        r.raise_for_status()
        response_text = r.json().get("content", "").strip()
    except requests.exceptions.Timeout:
        response_text = "(llama-server timed out)"
    except requests.exceptions.ConnectionError:
        response_text = "(llama-server not running — start it first)"
    except Exception as e:
        response_text = f"(error: {e})"

    if not response_text:
        response_text = "(empty response)"

    # [CHANGE: gemini-cli | 2026-05-09] Log incident if needed
    log_incident(message)

    return {
        "id": uuid.uuid4().hex[:12],
        "role": "assistant",
        "content": response_text,
        "model": model_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def list_chats():
    chats = []
    for f in sorted(CHATS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text())
            chats.append({
                "id": data.get("id", f.stem),
                "name": data.get("name", "Untitled"),
                "model": data.get("model", "nexus"),
                "createdAt": data.get("createdAt", ""),
                "updatedAt": data.get("updatedAt", ""),
                "messageCount": len(data.get("messages", [])),
            })
        except Exception:
            pass
    return chats


def get_chat(chat_id):
    chat_file = CHATS_DIR / f"{chat_id}.json"
    if not chat_file.exists():
        return {"error": "not found"}
    return json.loads(chat_file.read_text())


def save_chat(data):
    chat_id = data.get("id") or uuid.uuid4().hex[:12]
    data["id"] = chat_id
    data.setdefault("createdAt", datetime.now(timezone.utc).isoformat())
    data["updatedAt"] = datetime.now(timezone.utc).isoformat()
    (CHATS_DIR / f"{chat_id}.json").write_text(json.dumps(data, indent=2))
    return {"id": chat_id, "ok": True}


# QWebChannel-facing wrappers — all take/return JSON strings for JS bridge
def js_chat(json_str):
    data = json.loads(json_str)
    result = chat(
        data.get("message", ""),
        data.get("model"),
        data.get("messages", []),
    )
    if "error" in result:
        return json.dumps(result)
    return json.dumps(result)


def js_list_chats():
    return json.dumps(list_chats())


def js_get_chat(chat_id):
    return json.dumps(get_chat(chat_id))


def js_save_chat(json_str):
    data = json.loads(json_str)
    result = save_chat(data)
    return json.dumps(result)
