import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.engine import get_session
from app.deps import get_gateway, get_session_payload
from app.mesh.gateway import MeshGateway
from app.repositories import auth_repo
from app.schemas import LoginRequest, OtpRequest, SessionState
from app.security import otp as otp_security
from app.security.session import COOKIE_NAME, MAX_AGE_SECONDS, sign

logger = logging.getLogger("routes.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, secret: str, payload: dict) -> None:
    response.set_cookie(
        COOKIE_NAME,
        sign(secret, payload),
        max_age=MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    gateway: MeshGateway = Depends(get_gateway),
):
    user = auth_repo.find_user(settings, body.user)
    if user is None or not auth_repo.verify_password(user, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    session_id = str(uuid.uuid4())
    code = otp_security.generate_code()
    auth_repo.create_challenge(
        db, session_id, user.user, otp_security.hash_code(code), settings.otp_ttl_seconds
    )

    try:
        await gateway.send_channel(f"OTP {code}")
    except Exception:
        logger.exception("failed to deliver OTP over mesh")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "could not deliver OTP over mesh")

    _set_session_cookie(response, settings.session_secret, {"status": "pending_otp", "sid": session_id, "user": user.user})
    return {"pending_otp": True}


@router.post("/otp")
async def verify_otp(
    body: OtpRequest,
    response: Response,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    payload: dict | None = Depends(get_session_payload),
):
    if payload is None or payload.get("status") != "pending_otp":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no pending login")

    session_id = payload["sid"]
    challenge = auth_repo.get_active_challenge(db, session_id)
    if challenge is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no active OTP challenge, please log in again")

    if datetime.utcnow() > challenge.expires_at:
        auth_repo.consume(db, challenge)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "OTP expired, please log in again")

    if challenge.attempts >= settings.otp_max_attempts:
        auth_repo.consume(db, challenge)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "too many attempts, please log in again")

    if not otp_security.verify_code(body.code, challenge.code_hash):
        auth_repo.record_attempt(db, challenge)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "incorrect code")

    auth_repo.consume(db, challenge)
    _set_session_cookie(response, settings.session_secret, {"status": "authenticated", "sid": session_id, "user": payload["user"]})
    return {"authenticated": True}


@router.get("/me", response_model=SessionState)
async def me(payload: dict | None = Depends(get_session_payload)):
    if payload is None:
        return SessionState(status="unauthenticated")
    return SessionState(status=payload.get("status", "unauthenticated"), user=payload.get("user"))


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}
