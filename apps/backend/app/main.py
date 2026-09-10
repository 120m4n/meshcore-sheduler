import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.engine import SessionLocal
from app.mesh.gateway import MeshGateway
from app.routes import auth, events, health
from app.scheduler.ticker import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    gateway = MeshGateway(
        port=settings.mesh_serial_port,
        baudrate=settings.mesh_serial_baudrate,
        channel_name=settings.mesh_channel_name,
        channel_idx=settings.mesh_channel_idx,
        actuator_name=settings.mesh_actuator_name,
    )
    # Fail loudly on startup if the companion isn't reachable — an app that
    # silently came up without mesh access would accept logins it can never
    # deliver an OTP for.
    await gateway.start()
    app.state.gateway = gateway

    scheduler = start_scheduler(SessionLocal, gateway)
    app.state.scheduler = scheduler

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await gateway.stop()


app = FastAPI(title="Mesh Event Scheduler", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(health.router)
