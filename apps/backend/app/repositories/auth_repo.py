from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import AuthUser, Settings
from app.db.models import OtpChallenge, new_uuid


def find_user(settings: Settings, username: str) -> AuthUser | None:
    for u in settings.auth_users:
        if u.user == username:
            return u
    return None


def verify_password(user: AuthUser, password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), user.pass_hash.encode("utf-8"))


def create_challenge(
    db: Session, session_id: str, username: str, code_hash: str, ttl_seconds: int
) -> OtpChallenge:
    # A fresh login attempt invalidates any earlier pending code for this session.
    db.query(OtpChallenge).filter(
        OtpChallenge.session_id == session_id, OtpChallenge.consumed.is_(False)
    ).update({"consumed": True})

    challenge = OtpChallenge(
        id=new_uuid(),
        session_id=session_id,
        user=username,
        code_hash=code_hash,
        expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
        attempts=0,
        consumed=False,
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


def get_active_challenge(db: Session, session_id: str) -> OtpChallenge | None:
    return db.scalar(
        select(OtpChallenge)
        .where(OtpChallenge.session_id == session_id, OtpChallenge.consumed.is_(False))
        .order_by(OtpChallenge.created_at.desc())
    )


def record_attempt(db: Session, challenge: OtpChallenge) -> None:
    challenge.attempts += 1
    db.commit()


def consume(db: Session, challenge: OtpChallenge) -> None:
    challenge.consumed = True
    db.commit()
