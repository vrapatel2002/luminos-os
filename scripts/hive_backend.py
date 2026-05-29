#!/usr/bin/env python3
# HIVE Backend — inference + chat persistence (no HTTP)
# [CHANGE: claude-code | 2026-05-08]
# [CHANGE: claude-code | 2026-05-28] Route through hive-daemon (8078) not llama-server directly
# Imported by hive-popup-app.py, bridged to JS via QWebChannel.

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from hive_context import log_incident

CHATS_DIR = Path.home() / ".local/share/luminos/hive-chats"
CHATS_DIR.mkdir(parents=True, exist_ok=True)

# All chat goes through hive-daemon which owns routing, swapping, and web search.
HIVE_DAEMON = "http://127.0.0.1:8078"

# Map UI model names → chip names that hive-daemon understands
_CHIP_MAP = {
    "bolt":  "Code",
    "nova":  "Learn",
    "nexus": None,   # nexus = no chip = auto route
}


def chat(message, model, history):
    if not message or not message.strip():
        return {"error": "empty message"}

    chip = _CHIP_MAP.get(model) if model else None

    try:
        r = requests.post(
            f"{HIVE_DAEMON}/chat",
            json={
                "message": message,
                "chip": chip,
                "history": history or [],
            },
            timeout=180,
        )
        r.raise_for_status()
        data = r.json()
        response_text = (data.get("content") or "").strip() or "(empty response)"
        agent = (data.get("agent") or "nexus").lower()
    except requests.exceptions.Timeout:
        response_text = "(HIVE timed out — model may still be loading, try again)"
        agent = model or "nexus"
    except requests.exceptions.ConnectionError:
        response_text = "(HIVE daemon not running — check: systemctl --user status luminos-hive.service)"
        agent = model or "nexus"
    except Exception as e:
        response_text = f"(error: {e})"
        agent = model or "nexus"

    log_incident(message)

    return {
        "id": uuid.uuid4().hex[:12],
        "role": "assistant",
        "content": response_text,
        "model": agent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def preload():
    """Trigger hive-daemon to start loading nexus in background. Non-blocking."""
    try:
        requests.post(f"{HIVE_DAEMON}/preload", timeout=2)
    except Exception:
        pass
    return {"ok": True}


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


def js_preload():
    """Trigger background nexus preload and return immediately."""
    return json.dumps(preload())


def js_state():
    """Poll daemon state: {ready, model, stage}."""
    try:
        r = requests.get(f"{HIVE_DAEMON}/state", timeout=2)
        data = r.json()
        r2 = requests.get(f"{HIVE_DAEMON}/progress", timeout=2)
        prog = r2.json()
        return json.dumps({"ready": data.get("ready", False),
                           "model": data.get("model"),
                           "stage": prog.get("stage", "idle")})
    except Exception:
        return json.dumps({"ready": False, "model": None, "stage": "daemon_offline"})
