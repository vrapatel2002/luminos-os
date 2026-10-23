# luminos-vision.py — "borrowed eyes" for text-only GLM-5.3. Shared by luminos-glm-proxy and luminos-screenshot.
# [CHANGE: cowork | 2026-10-23] DECISION 156 / BUG-209.
# GLM-5.3 (abliterated-model-large-v2) is text-only: Abliteration returns HTTP 400 for any image.
# abliterated-model CAN read images, so it describes them and the description goes to GLM as text.
# Descriptions are cached by image hash (same image -> same text), which keeps prompt caching stable.
import base64, hashlib, http.client, json, os, ssl

UP_HOST = "api.abliteration.ai"
EYES_MODEL = "abliterated-model"
CACHE = os.path.expanduser("~/.cache/luminos-glm/vision")
PROMPT = ("You are the eyes for a text-only AI that cannot see this image. Describe it so that AI can act on it: "
          "what it is (screenshot / photo / diagram), every window or panel and where it sits, ALL readable text copied "
          "verbatim (titles, buttons, menus, messages, errors, code, numbers), the state of controls (selected, "
          "checked, disabled), and anything that looks wrong (errors, glitches, blank areas, odd colours). Be exact; "
          "do not guess at text you cannot read.")

def _key():
    for line in open(os.path.expanduser("~/.config/luminos/abliteration.env")):
        if line.startswith("ABLITERATION_API_KEY="):
            return line.strip().split("=", 1)[1]
    raise RuntimeError("no ABLITERATION_API_KEY")

def describe(media_type, b64data, question=None, timeout=180):
    """Return (text, cached). Never raises: on failure returns an explanatory text."""
    h = hashlib.sha256(((question or "") + "|" + b64data).encode()).hexdigest()
    os.makedirs(CACHE, mode=0o700, exist_ok=True)
    cp = os.path.join(CACHE, h + ".txt")
    if os.path.exists(cp):
        return open(cp).read(), True
    prompt = PROMPT + (("\n\nAlso answer this specifically: " + question) if question else "")
    body = json.dumps({"model": EYES_MODEL, "max_tokens": 2500, "messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64data}},
        {"type": "text", "text": prompt}]}]})
    try:
        c = http.client.HTTPSConnection(UP_HOST, 443, timeout=timeout, context=ssl.create_default_context())
        c.request("POST", "/v1/messages", body=body, headers={"authorization": "Bearer " + _key(),
                  "anthropic-version": "2023-06-01", "content-type": "application/json"})
        r = c.getresponse(); d = json.loads(r.read() or b"{}"); c.close()
        if r.status != 200:
            return "[image could not be described: HTTP %s %s]" % (r.status, json.dumps(d)[:200]), False
        text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text").strip()
    except Exception as e:
        return "[image could not be described: %s]" % e, False
    tmp = cp + ".tmp"; open(tmp, "w").write(text); os.replace(tmp, cp)
    return text, False

def _replace_list(blocks, do_describe, stats):
    out = []
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "image":
            src = b.get("source") or {}
            if src.get("type") == "base64" and do_describe:
                text, hit = describe(src.get("media_type", "image/png"), src.get("data", ""))
                stats["images"] += 1; stats["cached"] += int(hit)
            elif src.get("type") == "base64":
                text = "(image omitted for token counting)"
            else:
                text = "(image given by URL %s — not viewable)" % src.get("url", "?")
            out.append({"type": "text", "text": "[Image — GLM-5.3 cannot see images, so it was described by "
                        "abliterated-model:]\n" + text})
        elif isinstance(b, dict) and b.get("type") == "tool_result" and isinstance(b.get("content"), list):
            nb = dict(b); nb["content"] = _replace_list(b["content"], do_describe, stats); out.append(nb)
        else:
            out.append(b)
    return out

def strip_images(req, do_describe=True):
    """Replace every image block in an Anthropic Messages request with a text description, in place."""
    stats = {"images": 0, "cached": 0}
    for m in req.get("messages") or []:
        if isinstance(m, dict) and isinstance(m.get("content"), list):
            m["content"] = _replace_list(m["content"], do_describe, stats)
    return stats

def has_images(req):
    return '"type": "image"' in json.dumps(req) or '"type":"image"' in json.dumps(req, separators=(",", ":"))
