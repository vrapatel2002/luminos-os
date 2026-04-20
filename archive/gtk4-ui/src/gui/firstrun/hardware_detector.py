"""
src/gui/firstrun/hardware_detector.py
Hardware detection for the First Run Setup wizard (step 2).

All functions are pure Python + stdlib — no GTK required.
detect_all() is the main entry point; all sub-detectors are
individually callable for testing.
"""

import logging
import os
import platform
import re
import shutil
import subprocess

logger = logging.getLogger("luminos-ai.gui.firstrun.hardware")


# ===========================================================================
# Public API
# ===========================================================================

def detect_all() -> dict:
    """
    Run all hardware detections and return a combined result dict.

    Returns:
        Dict with keys: cpu, ram, npu, igpu, nvidia, storage, display,
        wine_available, firecracker_available, kvm_available.
    """
    return {
        "cpu":                  _detect_cpu(),
        "ram":                  _detect_ram(),
        "npu":                  _detect_npu(),
        "igpu":                 _detect_igpu(),
        "nvidia":               _detect_nvidia(),
        "storage":              _detect_storage(),
        "display":              _detect_display(),
        "wine_available":       _check_wine(),
        "firecracker_available": _check_firecracker(),
        "kvm_available":        _check_kvm(),
    }


def get_readiness_score(hw: dict) -> dict:
    """
    Calculate how ready the hardware is to run Luminos.

    Args:
        hw: Dict returned by detect_all().

    Returns:
        Dict with: score (0-100), zone2_ready, zone3_ready, npu_ready,
        ai_ready, issues ([str]), grade ("A"|"B"|"C").
    """
    score    = 0
    issues   = []

    zone2_ready = bool(hw.get("wine_available"))
    zone3_ready = bool(hw.get("kvm_available") and hw.get("firecracker_available"))
    npu_ready   = bool(hw.get("npu", {}).get("detected"))
    ai_ready    = bool(hw.get("nvidia", {}).get("detected"))

    # CPU — mandatory (15 pts)
    cpu = hw.get("cpu", {})
    if cpu.get("name"):
        score += 15
    else:
        issues.append("CPU information unavailable")

    # RAM — 8 GB minimum (15 pts)
    ram_gb = hw.get("ram", {}).get("total_gb", 0.0)
    if ram_gb >= 16:
        score += 15
    elif ram_gb >= 8:
        score += 10
        issues.append(f"RAM is {ram_gb:.1f} GB — 16 GB recommended")
    else:
        score += 5
        issues.append(f"RAM is {ram_gb:.1f} GB — minimum 8 GB required")

    # NPU — optional but preferred (15 pts)
    if npu_ready:
        score += 15
    else:
        issues.append("No AMD XDNA NPU found — AI classification will use CPU")

    # iGPU — needed for display (10 pts)
    if hw.get("igpu", {}).get("detected"):
        score += 10
    else:
        issues.append("No iGPU detected — display acceleration unavailable")

    # NVIDIA GPU — for HIVE models (20 pts)
    if ai_ready:
        vram = hw.get("nvidia", {}).get("vram_gb") or 0
        if vram >= 4:
            score += 20
        else:
            score += 10
            issues.append(f"NVIDIA GPU has {vram:.0f} GB VRAM — 4 GB minimum for HIVE")
    else:
        issues.append("No NVIDIA GPU — HIVE AI models unavailable")

    # Zone 2 — Wine/Proton (10 pts)
    if zone2_ready:
        score += 10
    else:
        issues.append("Wine64 not found — Zone 2 (Windows apps) unavailable")

    # Zone 3 — KVM + Firecracker (10 pts)
    if zone3_ready:
        score += 10
    else:
        missing = []
        if not hw.get("kvm_available"):
            missing.append("KVM")
        if not hw.get("firecracker_available"):
            missing.append("Firecracker")
        issues.append(f"Zone 3 unavailable — missing: {', '.join(missing)}")

    # Storage — 20 GB free recommended (5 pts)
    free_gb = hw.get("storage", {}).get("free_gb", 0.0)
    if free_gb >= 20:
        score += 5
    else:
        issues.append(f"Only {free_gb:.0f} GB storage free — 20 GB recommended")

    # Grade
    if score >= 80:
        grade = "A"
    elif score >= 50:
        grade = "B"
    else:
        grade = "C"

    return {
        "score":       score,
        "zone2_ready": zone2_ready,
        "zone3_ready": zone3_ready,
        "npu_ready":   npu_ready,
        "ai_ready":    ai_ready,
        "issues":      issues,
        "grade":       grade,
    }


# ===========================================================================
# Sub-detectors
# ===========================================================================

def _detect_cpu() -> dict:
    name  = "Unknown CPU"
    cores = 0
    arch  = platform.machine()

    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            content = f.read()

        for line in content.splitlines():
            if line.startswith("model name") and name == "Unknown CPU":
                name = line.split(":", 1)[1].strip()
            if line.startswith("cpu cores"):
                try:
                    cores = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
        # physical cores fallback: count "processor" lines / 2
        if cores == 0:
            procs = len(re.findall(r"^processor\s*:", content, re.MULTILINE))
            cores = max(1, procs)
    except OSError:
        pass

    return {"name": name, "cores": cores, "arch": arch}


def _detect_ram() -> dict:
    total_gb  = 0.0
    speed_mhz = None

    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    kb = int(line.split()[1])
                    total_gb = round(kb / 1024 / 1024, 1)
                    break
    except OSError:
        pass

    # DMI speed — optional, may need root
    try:
        out = subprocess.check_output(
            ["dmidecode", "-t", "memory"],
            stderr=subprocess.DEVNULL, timeout=3, text=True
        )
        m = re.search(r"Speed:\s*(\d+)\s*MT/s", out)
        if m:
            speed_mhz = int(m.group(1))
    except Exception:
        pass

    return {"total_gb": total_gb, "speed_mhz": speed_mhz}


def _detect_npu() -> dict:
    npu_path = "/dev/accel/accel0"
    detected = os.path.exists(npu_path)
    if detected:
        return {"detected": True, "name": "AMD XDNA", "tops": 16}
    return {"detected": False, "name": None, "tops": None}


def _detect_igpu() -> dict:
    try:
        out = subprocess.check_output(
            ["lspci", "-nn"], stderr=subprocess.DEVNULL, timeout=3, text=True
        )
        for line in out.splitlines():
            if "VGA" in line or "Display" in line:
                if any(kw in line for kw in ("AMD", "Intel", "Radeon", "RDNA")):
                    name = line.split(":")[-1].strip()
                    # Determine driver
                    driver = None
                    if "AMD" in name or "Radeon" in name:
                        driver = "amdgpu"
                    elif "Intel" in name:
                        driver = "i915"
                    return {"detected": True, "name": name, "driver": driver}
    except Exception:
        pass
    return {"detected": False, "name": None, "driver": None}


def _detect_nvidia() -> dict:
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL, timeout=3, text=True
        )
        lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
        if lines:
            parts = lines[0].split(",")
            gpu_name = parts[0].strip()
            vram_gb  = round(int(parts[1].strip()) / 1024, 1) if len(parts) > 1 else None
            return {"detected": True, "name": gpu_name, "vram_gb": vram_gb}
    except Exception:
        pass
    return {"detected": False, "name": None, "vram_gb": None}


def _detect_storage() -> dict:
    total_gb = 0.0
    free_gb  = 0.0
    disk_type = "Unknown"

    try:
        stat = os.statvfs("/")
        total_gb = round(stat.f_blocks * stat.f_frsize / 1024 ** 3, 1)
        free_gb  = round(stat.f_bfree  * stat.f_frsize / 1024 ** 3, 1)
    except OSError:
        pass

    # Probe disk type from /sys
    try:
        out = subprocess.check_output(
            ["lsblk", "-nd", "-o", "NAME,ROTA,TRAN"],
            stderr=subprocess.DEVNULL, timeout=3, text=True
        )
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                rotational = parts[1]
                tran = parts[2] if len(parts) > 2 else ""
                if "nvme" in tran.lower():
                    disk_type = "NVMe"
                elif rotational == "0":
                    disk_type = "SSD"
                elif rotational == "1":
                    disk_type = "HDD"
                if disk_type != "Unknown":
                    break
    except Exception:
        pass

    return {"total_gb": total_gb, "free_gb": free_gb, "type": disk_type}


def _detect_display() -> dict:
    resolution  = None
    refresh_hz  = None

    # Try xrandr first
    try:
        out = subprocess.check_output(
            ["xrandr"], stderr=subprocess.DEVNULL, timeout=3, text=True
        )
        m = re.search(r"(\d{3,5}x\d{3,5})\s+(\d+\.\d+)\*", out)
        if m:
            resolution = m.group(1)
            refresh_hz = int(float(m.group(2)))
    except Exception:
        pass

    # Try /sys/class/drm
    if resolution is None:
        try:
            for drm_path in sorted(os.listdir("/sys/class/drm")):
                modes_path = f"/sys/class/drm/{drm_path}/modes"
                if os.path.exists(modes_path):
                    with open(modes_path) as f:
                        first = f.readline().strip()
                    if first:
                        resolution = first
                        break
        except Exception:
            pass

    return {"resolution": resolution, "refresh_hz": refresh_hz}


def _check_wine() -> bool:
    return bool(shutil.which("wine64") or shutil.which("wine"))


def _check_firecracker() -> bool:
    return bool(shutil.which("firecracker"))


def _check_kvm() -> bool:
    return os.path.exists("/dev/kvm")
