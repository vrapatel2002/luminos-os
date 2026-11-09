#!/bin/bash
# [CHANGE: claude-code | 2026-11-09] DECISION 182 — regenerate packages/dolphin-luminos/dolphin-luminos-files.patch
# from a pristine dolphin tarball + dolphin-edit.py.   usage: make-dolphin-patch.sh path/to/dolphin-26.08.1.tar.xz
set -e
here=$(cd "$(dirname "$0")" && pwd); repo=$(cd "$here/../.." && pwd)
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
v=$(basename "$1" .tar.xz)
mkdir "$tmp/a" "$tmp/b"; tar xf "$1" -C "$tmp/a"; tar xf "$1" -C "$tmp/b"
python3 "$here/dolphin-edit.py" "$tmp/b/$v" "$here/luminosfilesstyle_p.h"
mkdir -p "$repo/packages/dolphin-luminos"
(cd "$tmp/a" && diff -ruN "$v" "../b/$v" | sed "s#\.\./b/$v#$v#") > "$repo/packages/dolphin-luminos/dolphin-luminos-files.patch" || true
echo "wrote $repo/packages/dolphin-luminos/dolphin-luminos-files.patch ($(wc -l < "$repo/packages/dolphin-luminos/dolphin-luminos-files.patch") lines)"
