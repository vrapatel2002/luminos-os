import subprocess
import json
import os

def get_system_context():
    # 1. RAM
    try:
        res = subprocess.run(["curl", "-s", "http://localhost:9091/meminfo"], capture_output=True, text=True, timeout=1)
        if res.returncode == 0:
            ram = json.loads(res.stdout)
            ram_used = round(ram.get("used", 0), 1)
            ram_total = round(ram.get("total", 0), 0)
            ram_avail = round(ram.get("available", 0), 1)
        else:
            ram_used, ram_total, ram_avail = "unknown", "unknown", "unknown"
    except:
        ram_used, ram_total, ram_avail = "unknown", "unknown", "unknown"

    # 2. Temp
    try:
        temps = []
        for path in os.listdir("/sys/class/hwmon/"):
            t_file = f"/sys/class/hwmon/{path}/temp1_input"
            if os.path.exists(t_file):
                with open(t_file, "r") as f:
                    temps.append(int(f.read().strip()) / 1000)
        cpu_temp = round(max(temps), 1) if temps else "unknown"
    except:
        cpu_temp = "unknown"

    # 3. Profile
    try:
        res = subprocess.run(["asusctl", "profile", "show"], capture_output=True, text=True, timeout=1)
        profile = res.stdout.strip() if res.returncode == 0 else "unknown"
    except:
        profile = "unknown"

    # 4. Services
    services = ["luminos-ram", "luminos-power"]
    states = []
    for s in services:
        try:
            res = subprocess.run(["systemctl", "is-active", s], capture_output=True, text=True, timeout=1)
            states.append(f"{s}: {res.stdout.strip()}")
        except:
            states.append(f"{s}: unknown")
    services_status = ", ".join(states)

    return {
        "ram_used": ram_used,
        "ram_total": ram_total,
        "ram_available": ram_avail,
        "cpu_temp": cpu_temp,
        "profile": profile,
        "services_status": services_status
    }

def get_brain_context(message):
    # Extract first 3 keywords (longer than 2 chars)
    words = [w for w in message.lower().split() if len(w) > 2]
    keywords = " ".join(words[:3])
    
    brain_context = ""
    if keywords:
        try:
            res = subprocess.run(["/usr/local/bin/luminos-brain", "query", keywords], capture_output=True, text=True, timeout=2)
            brain_context = res.stdout.strip()
        except:
            pass

    # Safety check
    if any(k in message.lower() for k in ["python", "venv", "install", "pip"]):
        try:
            res = subprocess.run(["/usr/local/bin/luminos-brain", "safe", message], capture_output=True, text=True, timeout=2)
            safety = res.stdout.strip()
            brain_context = f"SAFETY ALERT: {safety}\n\n{brain_context}"
        except:
            pass

    return brain_context.strip()

def log_incident(message):
    if any(k in message.lower() for k in ["error", "crash", "broken", "failed"]):
        try:
            subprocess.run(["/usr/local/bin/luminos-brain", "log", f"user reported: {message}"], timeout=2)
        except:
            pass
