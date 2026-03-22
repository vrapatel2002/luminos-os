"""
feature_extractor.py
Extracts binary features from an executable file for zone classification.
No external dependencies — pure stdlib only.
"""

import os
import re


# Magic bytes
ELF_MAGIC = b'\x7fELF'
PE_MAGIC = b'MZ'

# Win32 import DLL names to scan for
WIN32_DLLS = [
    b'kernel32.dll', b'KERNEL32.dll', b'KERNEL32.DLL',
    b'user32.dll',   b'USER32.dll',   b'USER32.DLL',
    b'ntdll.dll',    b'NTDLL.dll',    b'NTDLL.DLL',
    b'd3d9.dll',     b'D3D9.dll',     b'D3D9.DLL',
    b'd3d11.dll',    b'D3D11.dll',    b'D3D11.DLL',
    b'd3d12.dll',    b'D3D12.dll',    b'D3D12.DLL',
]

# Kernel driver import names
KERNEL_DRIVER_DLLS = [
    b'ntoskrnl.exe', b'NTOSKRNL.exe', b'NTOSKRNL.EXE',
    b'hal.dll',      b'HAL.dll',      b'HAL.DLL',
    b'ndis.sys',     b'NDIS.sys',     b'NDIS.SYS',
    b'ksecdd.sys',   b'KSECDD.sys',   b'KSECDD.SYS',
]

# Anti-cheat string markers (raw bytes, case-sensitive as they appear in binaries)
ANTICHEAT_STRINGS = [
    b'BattlEye',
    b'EasyAntiCheat',
    b'Vanguard',
    b'mhyprot',
    b'nProtect',
]

# Graphics API markers
VULKAN_STRINGS = [b'vulkan-1.dll', b'libvulkan']
OPENGL_STRINGS = [b'opengl32.dll', b'libGL']


def _contains_any(data: bytes, patterns: list) -> bool:
    return any(p in data for p in patterns)


def extract_features(path: str) -> dict:
    """
    Read a binary file and extract classification features.

    Returns a dict with:
      is_elf                  bool
      is_pe                   bool
      has_win32_imports       bool
      has_kernel_driver_imports bool
      has_anticheat_strings   bool
      file_size_mb            float
      has_vulkan              bool
      has_opengl              bool
    """
    file_size_bytes = os.path.getsize(path)
    file_size_mb = file_size_bytes / (1024 * 1024)

    with open(path, 'rb') as f:
        data = f.read()

    header = data[:4] if len(data) >= 4 else data

    is_elf = data[:4] == ELF_MAGIC
    is_pe  = data[:2] == PE_MAGIC

    has_win32_imports          = _contains_any(data, WIN32_DLLS)
    has_kernel_driver_imports  = _contains_any(data, KERNEL_DRIVER_DLLS)
    has_anticheat_strings      = _contains_any(data, ANTICHEAT_STRINGS)
    has_vulkan                 = _contains_any(data, VULKAN_STRINGS)
    has_opengl                 = _contains_any(data, OPENGL_STRINGS)

    return {
        "is_elf":                    is_elf,
        "is_pe":                     is_pe,
        "has_win32_imports":          has_win32_imports,
        "has_kernel_driver_imports":  has_kernel_driver_imports,
        "has_anticheat_strings":      has_anticheat_strings,
        "file_size_mb":               file_size_mb,
        "has_vulkan":                 has_vulkan,
        "has_opengl":                 has_opengl,
    }
