# Mesh Event Scheduler

Monorepo for the web app that schedules ON/OFF actuator events over the MeshCore mesh. Lives inside `meshcore-cli` so the backend can develop directly against the local `meshcore` Python library used by this repo's CLI.

See the architecture document (published artifact, shared separately) for full design rationale, sequence diagrams, and the gap register of assumptions made where the brief was silent.

## Layout

```
apps/
├── backend/     FastAPI app — auth/OTP, calendar API, scheduler, mesh gateway
└── frontend/    Vite + vanilla TS — login, OTP, calendar UI
deploy/
├── systemd/     mesh-scheduler-backend.service (Raspberry Pi deploy)
└── nginx/       reverse-proxy site config (same-origin frontend + API)
scripts/
├── build_for_pi.sh    builds a deployable artifact into dist_pi/ (run on your PC)
└── deploy_to_pi.sh    ships dist_pi/ to a Pi over SSH and provisions it
```

## Quick start

Backend:
```
cd apps/backend
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on POSIX
pip install -e ".[dev]"
cp .env.example .env     # fill in MESH_SERIAL_PORT, AUTH_USERS, etc.
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Frontend:
```
cd apps/frontend
npm install
cp .env.example .env      # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

## Docker Compose

`docker-compose.yml` builds both services (not started/tested in this environment — no Docker installed here). Before running it elsewhere:

```
cd apps
cp backend/.env.example backend/.env   # fill in real values
docker compose up --build
```

**USB serial and containers:** the companion radio is a host USB device. On Linux hosts, uncomment the `devices:` mapping in `docker-compose.yml` once you've confirmed the port with `python scripts/check_companion.py` (repo root) and point `MESH_SERIAL_PORT` at the same path inside the container (e.g. `/dev/ttyUSB0`). On Docker Desktop for Windows/Mac, a host `COMx`/serial port is **not** reachable from inside the Linux VM containers run in — for local Windows development, run the backend directly with `uvicorn` (Quick start above) rather than through Compose whenever you need real hardware access; only use Compose there for the frontend, or for backend testing where mesh connectivity isn't needed.

## Deploying to a Raspberry Pi (native, no Docker)

A Pi 3 has 1GB RAM — the Docker daemon's overhead isn't worth it here. This path runs the backend as a systemd service under its own venv (built with ARM wheels *on* the Pi) and serves the frontend as static files through nginx, which also reverse-proxies the API on the same origin (see `deploy/nginx/mesh-scheduler.conf` for why same-origin matters: no CORS, no cross-site cookie issues for the session cookie).

**1. Build the artifact — runs on your PC, not the Pi** (the frontend's TS/Vite build is comparatively heavy on a Pi 3; the backend's Python deps have platform-specific wheels, so only its *source* is shipped and the venv is built on-device):
```
cd <repo root>
cp apps/backend/.env.example apps/backend/.env   # fill in real values first
scripts/build_for_pi.sh
```
Runs the backend test suite (fails the build if anything's broken), type-checks and builds the frontend for same-origin serving, and stages everything into `dist_pi/`.

**2. Copy to the Pi and set it up** — requires SSH access with sudo:
```
scripts/deploy_to_pi.sh pi@<pi-ip-or-hostname>
```
This copies `dist_pi/` over (`scp`; swap for `rsync -az --delete` in the script if you have it — faster on repeat deploys), then over SSH: installs `python3-venv`/`nginx` if missing, creates a dedicated `mesh-scheduler` system user (added to the `dialout` group for serial port access), builds the backend venv **on the Pi's own ARM CPU** (never copy a venv built elsewhere — the wheels won't run), runs `alembic upgrade head`, installs and starts the `mesh-scheduler-backend` systemd unit, and installs the nginx site config.

To redeploy after a code change: re-run `build_for_pi.sh` then `deploy_to_pi.sh` again — both steps are idempotent.

### Validating it's up: `ip:port`

The backend itself binds to `127.0.0.1:8000` only (not exposed directly — see the systemd unit's comment on why); nginx is the public entry point on port 80. From any machine on the same network as the Pi:

```
curl -sf http://<pi-ip>/health
# {"mesh_connected": true, "actuator_state": {...}}
```

`mesh_connected: false` means the gateway is up but couldn't reach the companion — check `MESH_SERIAL_PORT` in `apps/backend/.env` and that the USB device is plugged in. If `curl` itself fails to connect, check nginx is running (`ssh pi@<ip> systemctl status nginx`) and the backend unit is healthy (`ssh pi@<ip> systemctl status mesh-scheduler-backend`; `journalctl -u mesh-scheduler-backend -f` for live logs — the gateway fails loudly and logs why if the companion isn't reachable, by design, see `app/mesh/gateway.py`).

Open `http://<pi-ip>/` in a browser for the actual app (login → OTP → calendar). To find the Pi's IP from the Pi itself: `hostname -I`.

### Exposing to the web (beyond your local network)

Everything above only reaches devices on the same LAN as the Pi. To reach it from outside, pick based on what you're comfortable exposing — this app holds a **hardcoded admin allow-list and controls a physical actuator**, so treat exposure as a real security decision, not a checkbox:

- **Tailscale / WireGuard (recommended)** — put the Pi on a private mesh VPN (e.g. `tailscale up` on the Pi) and access it via its VPN IP/hostname from anywhere, with zero public exposure. No changes needed to nginx or the app. This is the safest default for a small fixed-admin tool like this one.
- **Reverse SSH tunnel / port forward on your router**, if you specifically want it reachable by raw IP:
  1. Forward an external port (e.g. 443) on your router to the Pi's port 80.
  2. Put a TLS-terminating layer in front — either `certbot --nginx` on the Pi itself (needs a real domain name pointing at your public IP, and the port actually reachable from the internet for the ACME challenge), or a tunnel service (Cloudflare Tunnel, ngrok) that handles TLS for you without opening a router port at all.
  3. **Never expose the plain-HTTP `:80` config as-is to the public internet** — the session cookie and the login password travel in cleartext without TLS. Add HTTPS before doing this, not after.
- **Cloudflare Tunnel** is worth calling out separately: no router port-forwarding, free TLS, and works from behind CGNAT (common on residential/mobile connections) — install `cloudflared` on the Pi and point a tunnel at `http://localhost:80`.

Whichever you choose, `AUTH_USERS` in `apps/backend/.env` is the entire access-control surface (see the architecture gap register §8.3) — keep that list short and the bcrypt hashes real, since anything reachable from the public internet will eventually get scanned.
