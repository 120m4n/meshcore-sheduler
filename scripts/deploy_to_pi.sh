#!/usr/bin/env bash
# Copy a build artifact (from scripts/build_for_pi.sh) to a Raspberry Pi and
# set it up to run natively: a Python venv for the backend, systemd for the
# backend service, and nginx as the single public entry point serving the
# frontend + proxying the API (see deploy/nginx/mesh-scheduler.conf for why
# same-origin matters here).
#
# Usage:
#   scripts/deploy_to_pi.sh <user>@<pi-host-or-ip> [artifact_dir]
#
# Example:
#   scripts/build_for_pi.sh
#   scripts/deploy_to_pi.sh pi@192.168.1.50
#   scripts/deploy_to_pi.sh pi@raspberrypi.local dist_pi
#
# Requires: ssh + scp (already available via Git Bash on Windows), and a Pi
# reachable over SSH with sudo. Does NOT install nginx/systemd — those ship
# with Raspberry Pi OS; this only installs python3-venv if missing.
set -euo pipefail

TARGET="${1:?usage: scripts/deploy_to_pi.sh <user>@<pi-host-or-ip> [artifact_dir]}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${2:-$REPO_ROOT/dist_pi}"
REMOTE_DIR="/opt/mesh-scheduler"

if [ ! -d "$ARTIFACT_DIR" ]; then
    echo "!! No artifact at $ARTIFACT_DIR — run scripts/build_for_pi.sh first." >&2
    exit 1
fi

if [ ! -f "$ARTIFACT_DIR/backend/.env" ]; then
    echo "!! $ARTIFACT_DIR/backend/.env is missing (only .env.example was staged)." >&2
    echo "!! Fill in apps/backend/.env locally and re-run build_for_pi.sh, or scp it" >&2
    echo "!! directly to $TARGET:$REMOTE_DIR/backend/.env before starting the service." >&2
fi

echo "==> Copying artifact to $TARGET:$REMOTE_DIR (sudo password may be prompted)"
ssh "$TARGET" "sudo mkdir -p $REMOTE_DIR && sudo chown \$(whoami) $REMOTE_DIR"

# scp -r is used over rsync since rsync isn't part of a stock Windows/Git
# Bash install — scp is. If rsync is available on your machine, prefer:
#   rsync -az --delete "$ARTIFACT_DIR/" "$TARGET:$REMOTE_DIR/"
# for faster incremental re-deploys.
scp -r "$ARTIFACT_DIR/backend" "$ARTIFACT_DIR/frontend" "$ARTIFACT_DIR/systemd" "$ARTIFACT_DIR/nginx" "$ARTIFACT_DIR/VERSION" "$TARGET:$REMOTE_DIR/"

echo "==> Provisioning on the Pi: venv, systemd unit, nginx site"
ssh "$TARGET" bash -s <<'REMOTE_SCRIPT'
set -euo pipefail
REMOTE_DIR="/opt/mesh-scheduler"
SERVICE_USER="mesh-scheduler"

echo "  -- ensuring python3-venv is installed"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip nginx >/dev/null

echo "  -- creating service user (idempotent)"
id -u "$SERVICE_USER" >/dev/null 2>&1 || sudo useradd --system --home "$REMOTE_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
# Serial port access requires membership in the dialout group.
sudo usermod -aG dialout "$SERVICE_USER"

echo "  -- building backend venv (ARM wheels, built ON the Pi — do not copy a"
echo "     venv built on a PC, it will not run on this CPU architecture)"
echo "     This can take several minutes on a Pi 3 if any dependency (e.g."
echo "     bleak's platform bindings) has no prebuilt ARM wheel and must"
echo "     compile from source — that is expected, not a failure."
cd "$REMOTE_DIR/backend"
sudo -u "$SERVICE_USER" python3 -m venv .venv
sudo -u "$SERVICE_USER" .venv/bin/pip install --upgrade pip
sudo -u "$SERVICE_USER" .venv/bin/pip install .

echo "  -- running migrations"
sudo -u "$SERVICE_USER" .venv/bin/alembic upgrade head

echo "  -- installing systemd unit"
sudo cp "$REMOTE_DIR/systemd/mesh-scheduler-backend.service" /etc/systemd/system/
sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$REMOTE_DIR/backend"
sudo systemctl daemon-reload
sudo systemctl enable mesh-scheduler-backend
sudo systemctl restart mesh-scheduler-backend

echo "  -- installing nginx site"
sudo cp "$REMOTE_DIR/nginx/mesh-scheduler.conf" /etc/nginx/sites-available/mesh-scheduler.conf
sudo ln -sf /etc/nginx/sites-available/mesh-scheduler.conf /etc/nginx/sites-enabled/mesh-scheduler.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

echo "  -- backend status:"
sudo systemctl --no-pager status mesh-scheduler-backend | head -8
REMOTE_SCRIPT

PI_IP="$(ssh "$TARGET" "hostname -I | awk '{print \$1}'")"
echo ""
echo "==> Deploy complete."
echo "    Validate with:   curl -sf http://$PI_IP/health"
echo "    Open in browser: http://$PI_IP/"
echo "    Logs:            ssh $TARGET journalctl -u mesh-scheduler-backend -f"
echo "    See apps/README.md 'Exposing to the web' for making this reachable"
echo "    outside your LAN."
