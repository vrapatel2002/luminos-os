#!/usr/bin/env python3
# HIVE Popup Server — Flask backend for HTML chat UI
# [CHANGE: claude-code | 2026-05-08]

import json
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

CHATS_DIR = Path.home() / ".local/share/luminos/hive-chats"
CHATS_DIR.mkdir(parents=True, exist_ok=True)

HTML_PATH = Path(__file__).resolve().parent / "hive-popup-ui.html"

LLAMA_SERVER = "http://127.0.0.1:8080"


def route_model(text):
    lower = text.lower()
    for kw in ["code", "script", "write"]:
        if kw in lower:
            return "bolt"
    return "nexus"


@app.route("/")
def index():
    return send_file(str(HTML_PATH))


@app.route("/api/chats", methods=["GET"])
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
    return jsonify(chats)


@app.route("/api/chats/<chat_id>", methods=["GET"])
def get_chat(chat_id):
    chat_file = CHATS_DIR / f"{chat_id}.json"
    if not chat_file.exists():
        return jsonify({"error": "not found"}), 404
    return jsonify(json.loads(chat_file.read_text()))


@app.route("/api/save", methods=["POST"])
def save_chat():
    data = request.get_json(force=True)
    chat_id = data.get("id") or uuid.uuid4().hex[:12]
    data["id"] = chat_id
    data.setdefault("createdAt", datetime.now(timezone.utc).isoformat())
    data["updatedAt"] = datetime.now(timezone.utc).isoformat()
    (CHATS_DIR / f"{chat_id}.json").write_text(json.dumps(data, indent=2))
    return jsonify({"id": chat_id, "ok": True})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "empty message"}), 400

    model_key = data.get("model") or route_model(message)
    history = data.get("messages", [])
    prompt = build_prompt(history, message, model_key)

    try:
        r = requests.post(
            f"{LLAMA_SERVER}/completion",
            json={
                "prompt": prompt,
                "n_predict": 256,
                "temperature": 0.7,
                "top_p": 0.9,
                "stop": ["User:", "Assistant:"],
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

    reply = {
        "id": uuid.uuid4().hex[:12],
        "role": "assistant",
        "content": response_text,
        "model": model_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify(reply)


def build_prompt(history, current_msg, model):
    lines = []
    if model == "bolt":
        lines.append("<|system|>\nYou are Bolt, a coding specialist AI. Provide concise, correct code solutions.</s>")
    else:
        lines.append("<|system|>\nYou are Nexus, a helpful AI assistant. Be direct and concise.</s>")

    for msg in history[-10:]:
        role = "user" if msg["role"] == "user" else "assistant"
        lines.append(f"<|{role}|>\n{msg['content']}</s>")

    lines.append(f"<|user|>\n{current_msg}</s>")
    lines.append("<|assistant|>\n")
    return "\n".join(lines)


if __name__ == "__main__":
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    print(f"{port}", flush=True)

    app.run(host="127.0.0.1", port=port, debug=False)
