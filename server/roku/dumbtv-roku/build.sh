#!/usr/bin/env bash
# Build the sideload zip. [CHANGE: claude-code | 2026-10-27]
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist
rm -f dist/dumbtv-roku.zip
zip -qr dist/dumbtv-roku.zip manifest source components images
unzip -l dist/dumbtv-roku.zip | tail -1
