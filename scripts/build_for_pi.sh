#!/usr/bin/env bash
# Build a deployable artifact for the Mesh Event Scheduler, targeting a
# Raspberry Pi 3 running natively (venv + systemd + nginx, no Docker — a Pi
# 3's 1GB RAM makes the Docker daemon overhead not worth it for this app).
#
# Runs on the PC, not the Pi: the frontend's TypeScript/Vite build is
# comparatively heavy and slow on a Pi 3, so it's built here and shipped as
# static files. The backend ships as source + a pinned requirements list —
# `deploy_to_pi.sh` creates the actual Python venv ON the Pi, since Python
# wheels are platform-specific (a venv built on a Windows/x86_64 PC cannot
# run on the Pi's ARM CPU).
#
# Usage:
#   scripts/build_for_pi.sh [output_dir]
#
# Produces <output_dir>/ (default: dist_pi/) containing:
#   backend/        app/ source, pyproject.toml, alembic.ini, migrations
#   frontend/       pre-built static site (dist/ from `vite build`)
#   systemd/        unit files (see scripts/deploy_to_pi.sh)
#   nginx/           reverse-proxy site config
#   VERSION          git commit + build timestamp, for `ip:port` sanity checks
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-$REPO_ROOT/dist_pi}"
BACKEND_DIR="$REPO_ROOT/apps/backend"
FRONTEND_DIR="$REPO_ROOT/apps/frontend"

echo "==> Building into $OUT_DIR"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/backend" "$OUT_DIR/frontend" "$OUT_DIR/systemd" "$OUT_DIR/nginx"

# ---------- backend: source only, venv gets built ON the Pi ----------
echo "==> Staging backend source"
cp -r "$BACKEND_DIR/app" "$OUT_DIR/backend/app"
cp "$BACKEND_DIR/pyproject.toml" "$OUT_DIR/backend/"
cp "$BACKEND_DIR/alembic.ini" "$OUT_DIR/backend/"
cp "$BACKEND_DIR/README.md" "$OUT_DIR/backend/"
# Never ship the local .env: values like MESH_SERIAL_PORT are host-specific
# (e.g. macOS /dev/cu.usbmodemXXXX won't exist on the Pi's Linux/ttyUSB0) and
# SESSION_SECRET/AUTH_USERS shouldn't leak from a dev machine into a deploy
# artifact. deploy_to_pi.sh already warns and tells you where to put a
# Pi-specific .env.
cp "$BACKEND_DIR/.env.example" "$OUT_DIR/backend/.env.example"
# meshcore-cli's own pyproject pins the `meshcore` library version this repo
# is validated against — the backend depends on that same library, so ship
# the root pyproject too as a version reference for the Pi-side install.
cp "$REPO_ROOT/pyproject.toml" "$OUT_DIR/backend/root-pyproject-reference.toml"

echo "==> Running backend tests before packaging (fail fast, don't ship broken code)"
if [ -x "$REPO_ROOT/.venv/Scripts/python.exe" ]; then
    PY="$REPO_ROOT/.venv/Scripts/python.exe"
elif [ -x "$REPO_ROOT/.venv/bin/python" ]; then
    PY="$REPO_ROOT/.venv/bin/python"
else
    echo "!! No repo-root venv found at .venv — skipping test run. Create one and" >&2
    echo "!! 'pip install -e apps/backend[dev]' before relying on this build." >&2
    PY=""
fi
if [ -n "$PY" ]; then
    (cd "$BACKEND_DIR" && "$PY" -m pytest -q)
fi

# ---------- frontend: real production build ----------
# Built same-origin (empty base URL): the Pi's nginx serves the static
# frontend AND proxies /auth, /events, /health on the same host:port (see
# deploy/nginx/mesh-scheduler.conf) — no separate frontend port, no CORS,
# no cross-origin session cookie. This differs from local dev, where
# VITE_API_BASE_URL points at a separate :8000 uvicorn origin.
echo "==> Building frontend for same-origin deployment (tsc --noEmit + vite build)"
(cd "$FRONTEND_DIR" && VITE_API_BASE_URL="" npm run build)
cp -r "$FRONTEND_DIR/dist/." "$OUT_DIR/frontend/"
rm -rf "$FRONTEND_DIR/dist"

# ---------- systemd units ----------
cp "$REPO_ROOT/deploy/systemd/mesh-scheduler-backend.service" "$OUT_DIR/systemd/"

# ---------- nginx site ----------
cp "$REPO_ROOT/deploy/nginx/mesh-scheduler.conf" "$OUT_DIR/nginx/"

# ---------- version stamp ----------
{
    echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "git_commit=$(cd "$REPO_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
    echo "git_branch=$(cd "$REPO_ROOT" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
} > "$OUT_DIR/VERSION"

echo "==> Done. Artifact at: $OUT_DIR"
echo "    Next: scripts/deploy_to_pi.sh <user>@<pi-host-or-ip> [$OUT_DIR]"
