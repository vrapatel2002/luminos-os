"""
zone_rules.py
Rule-based compatibility router. Takes extracted features, returns layer decision.

Stage 1 of the two-stage router (rules first, AI fallback second).
Handles ~80% of binaries deterministically — fast, no model needed.

Output is always one of: proton | wine | lutris | firecracker | kvm
Plus a confidence score and human-readable reason.

Rule priority (highest to lowest):
  1. ELF binary → native (zone 1, no layer needed)
  2. Anticheat (EAC, BattlEye) → kvm
  3. Kernel-level APIs (NtCreateProcess etc) → firecracker
  4. DX12 only → proton
  5. DX9/10/11 → proton (DXVK handles translation)
  6. .NET only, no DirectX → wine
  7. No special APIs → proton (safest default)
"""


def classify(features: dict) -> dict:
    """
    Apply priority-ordered rules to extracted features.

    Args:
        features: dict from feature_extractor.extract_features()

    Returns:
        {
            "zone": int,           # 1=native, 2=wine/proton, 3=firecracker/kvm
            "layer": str,          # proton|wine|lutris|firecracker|kvm|native
            "confidence": float,   # 0.0–1.0
            "reason": str,
            "rule_matched": bool,  # True if a rule decided, False for fallback
        }
    """
    is_elf   = features.get("is_elf", False)
    is_pe    = features.get("is_pe", False)
    has_ac   = features.get("has_anticheat_strings", False)
    has_kern = features.get("has_kernel_driver_imports", False)
    has_kapi = features.get("has_kernel_api_calls", False)
    has_dx9  = features.get("has_dx9", False)
    has_dx10 = features.get("has_dx10", False)
    has_dx11 = features.get("has_dx11", False)
    has_dx12 = features.get("has_dx12", False)
    has_net  = features.get("has_dotnet", False)
    has_w32  = features.get("has_win32_imports", False)

    # Rule 1 — Native Linux ELF → run directly
    if is_elf:
        return _decision(1, "native", 0.99, "Native Linux binary", True)

    # Rule 2 — Anticheat → KVM (full VM required for ring-0 anticheat)
    if is_pe and has_ac:
        return _decision(3, "kvm", 0.95, "Anticheat detected (EAC/BattlEye) — full VM required", True)

    # Rule 3 — Kernel-level APIs or driver imports → Firecracker
    if is_pe and (has_kern or has_kapi):
        return _decision(3, "firecracker", 0.92, "Kernel-level API access detected — microVM sandbox", True)

    # Rule 4 — DirectX 12 → Proton (VKD3D-Proton handles DX12→Vulkan)
    if is_pe and has_dx12:
        return _decision(2, "proton", 0.90, "DirectX 12 detected — Proton + VKD3D-Proton", True)

    # Rule 5 — DirectX 9/10/11 → Proton (DXVK handles DX9-11→Vulkan)
    if is_pe and (has_dx9 or has_dx10 or has_dx11):
        return _decision(2, "proton", 0.88, "DirectX 9/10/11 detected — Proton + DXVK", True)

    # Rule 6 — .NET only, no DirectX → plain Wine
    if is_pe and has_net and not (has_dx9 or has_dx10 or has_dx11 or has_dx12):
        return _decision(2, "wine", 0.85, ".NET application, no DirectX — plain Wine", True)

    # Rule 7 — PE with Win32 imports, no special APIs → Proton (safest default)
    if is_pe and has_w32:
        return _decision(2, "proton", 0.80, "Win32 application — Proton (default)", True)

    # Rule 8 — PE with no recognized imports → Proton, lower confidence
    if is_pe:
        return _decision(2, "proton", 0.60, "PE binary, no recognized imports — Proton (default)", False)

    # Fallback — unknown binary type, no rule matched → needs AI
    return _decision(1, "native", 0.40, "Unknown binary type — no rule matched", False)


def _decision(zone: int, layer: str, confidence: float,
              reason: str, rule_matched: bool) -> dict:
    return {
        "zone":         zone,
        "layer":        layer,
        "confidence":   confidence,
        "reason":       reason,
        "rule_matched": rule_matched,
    }
