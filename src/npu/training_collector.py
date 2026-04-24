import json, os
from datetime import datetime

TRAINING_DIR = os.path.expanduser(
    "~/.local/share/luminos/training")
SENTINEL_DATA = f"{TRAINING_DIR}/sentinel.jsonl"
ROUTER_DATA = f"{TRAINING_DIR}/router.jsonl"
MAX_EXAMPLES = 10000

def _count(path):
    try:
        return sum(1 for _ in open(path))
    except:
        return 0

def log_sentinel(process, path, label, source, conf):
    if source != 'rules': return
    if _count(SENTINEL_DATA) >= MAX_EXAMPLES: return
    os.makedirs(TRAINING_DIR, exist_ok=True)
    ex = {"ts": datetime.now().isoformat(),
          "input": f"{process} {path}",
          "label": label}
    open(SENTINEL_DATA,'a').write(
        json.dumps(ex)+'\n')

def log_router(exe, features, label, source, conf):
    if source != 'rules': return
    if _count(ROUTER_DATA) >= MAX_EXAMPLES: return
    os.makedirs(TRAINING_DIR, exist_ok=True)
    ex = {"ts": datetime.now().isoformat(),
          "exe": exe, "features": features,
          "label": label}
    open(ROUTER_DATA,'a').write(
        json.dumps(ex)+'\n')

def status():
    s = _count(SENTINEL_DATA)
    r = _count(ROUTER_DATA)
    return {"sentinel": s, "router": r,
            "sentinel_ready": s >= 1000,
            "router_ready": r >= 1000}
