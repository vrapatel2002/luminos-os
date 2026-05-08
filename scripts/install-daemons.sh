#!/usr/bin/env bash
# install-daemons.sh — Build and install all Luminos Go daemons.
# Creates required directories, installs systemd services, enables and starts all four.
# Must be run from the repo root or any subdirectory (it resolves the repo root itself).
# Requires: go, sudo, systemd.
# [CHANGE: claude-code | 2026-04-20] Phase 1 Go foundation — daemon install script.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BINDIR="/usr/local/bin"
SYSTEMD_DIR="/etc/systemd/system"
LOG_DIR="/var/log/luminos"
RUN_DIR="/run/luminos"
ETC_DIR="/etc/luminos"

cd "$REPO_ROOT"

echo "==> Building Luminos daemons from $REPO_ROOT ..."
go build -o /tmp/luminos-ai       ./cmd/luminos-ai
go build -o /tmp/luminos-power    ./cmd/luminos-power
go build -o /tmp/luminos-sentinel ./cmd/luminos-sentinel
go build -o /tmp/luminos-router   ./cmd/luminos-router
go build -o /tmp/luminos-ram      ./cmd/luminos-ram
echo "    Build complete."

# Print binary sizes so we can sanity-check nothing is bloated.
echo ""
echo "==> Binary sizes:"
ls -lh /tmp/luminos-ai /tmp/luminos-power /tmp/luminos-sentinel /tmp/luminos-router /tmp/luminos-ram

echo ""
echo "==> Installing binaries to $BINDIR/ ..."
sudo install -m 755 /tmp/luminos-ai       "$BINDIR/luminos-ai"
sudo install -m 755 /tmp/luminos-power    "$BINDIR/luminos-power"
sudo install -m 755 /tmp/luminos-sentinel "$BINDIR/luminos-sentinel"
sudo install -m 755 /tmp/luminos-router   "$BINDIR/luminos-router"
sudo install -m 755 /tmp/luminos-ram      "$BINDIR/luminos-ram"

echo "==> Creating required directories ..."
sudo mkdir -p "$LOG_DIR" "$RUN_DIR" "$ETC_DIR"
sudo chmod 755 "$LOG_DIR" "$RUN_DIR"

echo "==> Installing systemd service files ..."
sudo install -m 644 "$REPO_ROOT/systemd/luminos-ai.service"       "$SYSTEMD_DIR/"
sudo install -m 644 "$REPO_ROOT/systemd/luminos-power.service"    "$SYSTEMD_DIR/"
sudo install -m 644 "$REPO_ROOT/systemd/luminos-sentinel.service" "$SYSTEMD_DIR/"
sudo install -m 644 "$REPO_ROOT/systemd/luminos-router.service"   "$SYSTEMD_DIR/"
sudo install -m 644 "$REPO_ROOT/systemd/luminos-ram.service"      "$SYSTEMD_DIR/"

echo "==> Reloading systemd ..."
sudo systemctl daemon-reload

echo "==> Enabling and starting services ..."
sudo systemctl enable --now luminos-ai.service
sudo systemctl enable --now luminos-power.service
sudo systemctl enable --now luminos-sentinel.service
sudo systemctl enable --now luminos-router.service
sudo systemctl enable --now luminos-ram.service

echo ""
echo "==> Installation complete. Service status:"
systemctl status luminos-ai luminos-power luminos-sentinel luminos-router luminos-ram --no-pager || true

echo ""
echo "==> Quick health check (requires services to be running):"
echo '{"type":"ping","source":"install-script","timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"}' \
  | nc -U /run/luminos/ai.sock 2>/dev/null || echo "    (luminos-ai not yet ready — retry in a moment)"
