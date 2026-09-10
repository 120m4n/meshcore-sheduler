# Mesh Event Scheduler — backend

FastAPI service: password + mesh-delivered OTP auth, calendar CRUD, an in-process
scheduler that fires `PINx_ON` / `PINx_OFF` over a MeshCore channel, and the single
serial gateway that owns the companion connection.

## Setup

This package depends on `meshcore`, the same library the sibling `meshcore-cli`
package (repo root) depends on. Install into the **same virtualenv** as the repo
root so there's only one `meshcore` install and no ambiguity about which serial
library version is in use — do not create a second, separate venv for this app.

```
cd ../..                      # repo root
.venv/Scripts/python.exe -m pip install -e apps/backend[dev]
cd apps/backend
copy .env.example .env        # fill in MESH_SERIAL_PORT, AUTH_USERS, SESSION_SECRET
..\..\.venv\Scripts\alembic.exe upgrade head
..\..\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

(POSIX: `source ../../.venv/bin/activate`, then `alembic upgrade head` and
`uvicorn app.main:app --reload --port 8000` directly.)

## Generating an AUTH_USERS entry

```
python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

Paste the resulting hash into the `AUTH_USERS` JSON array in `.env`:
`[{"user":"admin","pass_hash":"$2b$12$..."}]`

## Tests

```
..\..\.venv\Scripts\pytest.exe
```

Tests use an in-memory SQLite database and a stub mesh gateway — they never touch
a real serial port.
