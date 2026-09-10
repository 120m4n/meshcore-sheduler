from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings
from app.security.session import COOKIE_NAME, unsign


def get_session_payload(request: Request, settings: Settings = Depends(get_settings)) -> dict | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return unsign(settings.session_secret, token)


def require_authenticated(payload: dict | None = Depends(get_session_payload)) -> dict:
    if payload is None or payload.get("status") != "authenticated":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    return payload


def get_gateway(request: Request):
    return request.app.state.gateway
