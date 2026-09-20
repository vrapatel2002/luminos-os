"""Make the import of the hyphenated helper scripts EXPLICIT.

[CHANGE: claude-code | 2026-09-19] SPEC §3.3.
SPDX-License-Identifier: GPL-3.0-or-later

Before this, `import luminos_wallpaper_pkg` worked only because something outside
the repo staged that file under that name. An invisible step is one nobody can
fix when it breaks — and it is why splitting a tested module looked risky enough
to nearly not happen. The path is stated here instead.
"""
import importlib.machinery, importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CANDIDATES = {
    "luminos_wallpaper_pkg": ["scripts/luminos-wallpaper-pkg"],
    "luminos_wallpaper_lively": ["scripts/luminos-wallpaper-lively"],
}

for name, rels in CANDIDATES.items():
    if name in sys.modules:
        continue
    for rel in rels:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            path = os.path.join(HERE, name + ".py")      # flat scratch layout
        if os.path.isfile(path):
            loader = importlib.machinery.SourceFileLoader(name, path)
            mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
            loader.exec_module(mod)
            sys.modules[name] = mod
            break
