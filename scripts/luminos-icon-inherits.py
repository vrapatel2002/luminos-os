#!/usr/bin/env python3
"""Set Inherits= in an icon theme index.theme while keeping [Icon Theme] as the first
group (the freedesktop Icon Theme spec requires it). kwriteconfig6 reorders groups
alphabetically, which buries [Icon Theme] hundreds of lines down.

[CHANGE: claude-code | 2026-07-26] BUG-090 — replaces the kwriteconfig6 call in
scripts/luminos-ubuntu-look step 2b."""
import sys, re

path, inherits = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()

# Split into (header, [(groupname, body), ...])
parts = re.split(r'(?m)^\[(.+?)\]\s*$\n', text)
lead, groups = parts[0], list(zip(parts[1::2], parts[2::2]))

out, changed = [], False
for name, body in groups:
    if name == "Icon Theme":
        new, n = re.subn(r'(?m)^Inherits=.*$', f'Inherits={inherits}', body)
        if n == 0:
            new = body.rstrip("\n") + f"\nInherits={inherits}\n\n"
        if new != body:
            changed = True
        body = new
    out.append((name, body))

if not any(n == "Icon Theme" for n, _ in out):
    sys.exit(f"{path}: no [Icon Theme] group — refusing to touch it")

# [Icon Theme] must come first.
out.sort(key=lambda kv: kv[0] != "Icon Theme")
if out[0][0] != groups[0][0]:
    changed = True

if not changed:
    print(f"{path}: already correct")
    sys.exit(0)

with open(path, "w", encoding="utf-8") as f:
    f.write(lead)
    for name, body in out:
        f.write(f"[{name}]\n{body}")
print(f"{path}: repaired")
