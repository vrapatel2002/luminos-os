#!/bin/bash
# [CHANGE: claude-code | 2026-11-09] DECISION 182 — regenerate packages/kio-luminos/kio-luminos-places.patch
# from a pristine kio tarball + kio-edit.py.   usage: make-kio-patch.sh path/to/kio-6.30.0.tar.xz
set -e
here=$(cd "$(dirname "$0")" && pwd); repo=$(cd "$here/../.." && pwd)
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
v=$(basename "$1" .tar.xz)
mkdir "$tmp/a" "$tmp/b"; tar xf "$1" -C "$tmp/a"; tar xf "$1" -C "$tmp/b"
python3 "$here/kio-edit.py" "$tmp/b/$v" "$here/luminosfilesstyle_p.h"
(cd "$tmp/a" && diff -ruN "$v" "../b/$v" | sed "s#\.\./b/$v#$v#") > "$repo/packages/kio-luminos/kio-luminos-places.patch" || true
echo "wrote $repo/packages/kio-luminos/kio-luminos-places.patch ($(wc -l < "$repo/packages/kio-luminos/kio-luminos-places.patch") lines)"
