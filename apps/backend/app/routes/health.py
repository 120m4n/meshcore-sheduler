import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.deps import get_gateway, require_authenticated
from app.mesh.gateway import MeshGateway

router = APIRouter(tags=["health"])


@router.get("/health")
def health(gateway: MeshGateway = Depends(get_gateway)):
    # actuator_state is last-observed, decoupled from any send this process
    # made — see app/mesh/gateway.py. age_seconds lets a caller decide for
    # itself whether a reading is stale, rather than the backend guessing.
    # Public/unauthenticated by design — see README's curl monitoring example.
    return {"mesh_connected": gateway.is_connected, "actuator_state": gateway.actuator_state_snapshot()}


# Well under typical reverse-proxy idle-connection timeouts (nginx defaults
# to 60s) — keeps the SSE connection alive through the proxy without relying
# on TCP keepalive tuning.
_STREAM_HEARTBEAT_SECONDS = 15


@router.get("/health/actuator-state/stream", dependencies=[Depends(require_authenticated)])
async def actuator_state_stream(gateway: MeshGateway = Depends(get_gateway)):
    """Real-time push of actuator_state_snapshot() — never polling. The
    frontend does not, and must never, cause any mesh-channel traffic by
    connecting here or by any user action on it (see views/calendar.ts):
    it only ever receives whatever this gateway already has in memory,
    starting with the current snapshot and then one push per STATE=
    message the gateway's permanent listener observes on its own (see
    MeshGateway._on_channel_message / _broadcast_state). No code path
    reachable from this route touches the serial connection.
    """
    queue = gateway.subscribe_state()

    async def event_source():
        try:
            yield f"data: {json.dumps(gateway.actuator_state_snapshot())}\n\n"
            while True:
                try:
                    snapshot = await asyncio.wait_for(queue.get(), timeout=_STREAM_HEARTBEAT_SECONDS)
                    yield f"data: {json.dumps(snapshot)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            gateway.unsubscribe_state(queue)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
