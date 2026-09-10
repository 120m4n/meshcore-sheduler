# Mesh Event Scheduler

Monorepo for the web app that schedules ON/OFF actuator events over the MeshCore mesh. Lives inside `meshcore-cli` so the backend can develop directly against the local `meshcore` Python library used by this repo's CLI.

See the architecture document (published artifact, shared separately) for full design rationale, sequence diagrams, and the gap register of assumptions made where the brief was silent.

## Layout

```
apps/
├── backend/     FastAPI app — auth/OTP, calendar API, scheduler, mesh gateway
└── frontend/    Vite + vanilla TS — login, OTP, calendar UI
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
