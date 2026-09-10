import time

from fastapi import APIRouter, Depends

from app.deps import get_gateway
from app.mesh.gateway import MeshGateway

router = APIRouter(tags=["health"])


@router.get("/health")
def health(gateway: MeshGateway = Depends(get_gateway)):
    # actuator_state is last-observed, decoupled from any send this process
    # made — see app/mesh/gateway.py. age_seconds lets a caller decide for
    # itself whether a reading is stale, rather than the backend guessing.
    now = time.monotonic()
    actuator_state = {
        pin: {"state": s.state, "age_seconds": round(now - s.observed_at, 1)}
        for pin, s in gateway.actuator_states.items()
    }
    return {"mesh_connected": gateway.is_connected, "actuator_state": actuator_state}
