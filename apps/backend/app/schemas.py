from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.repositories.event_repo import duration_seconds, MIN_DURATION_SECONDS

Recurrence = Literal["once", "daily"]


class EventCreate(BaseModel):
    label: str | None = None
    pin: int
    recurrence: Recurrence
    start_date: date
    end_date: date | None = None
    on_time: time
    off_time: time
    enabled: bool = True

    @field_validator("pin")
    @classmethod
    def _pin_range(cls, v: int) -> int:
        if not (0 <= v <= 7):
            raise ValueError("pin must be between 0 and 7")
        return v

    @field_validator("end_date")
    @classmethod
    def _end_after_start(cls, v: date | None, info) -> date | None:
        start = info.data.get("start_date")
        if v is not None and start is not None and v < start:
            raise ValueError("end_date must not be before start_date")
        return v

    @model_validator(mode="after")
    def _min_duration(self) -> "EventCreate":
        # Same rule event_repo.create/update enforce server-side — checked
        # here too so a bad request 422s with a clear message instead of
        # reaching the repository at all. The repository check remains the
        # real guarantee (see UX proposal §05); this is the fast path.
        if duration_seconds(self.on_time, self.off_time) < MIN_DURATION_SECONDS:
            raise ValueError(f"ON/OFF must be at least {MIN_DURATION_SECONDS} seconds apart")
        return self


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str | None
    pin: int
    recurrence: Recurrence
    start_date: date
    end_date: date | None
    on_time: time
    off_time: time
    enabled: bool
    created_by: str


class LoginRequest(BaseModel):
    user: str
    password: str


class OtpRequest(BaseModel):
    code: str


class SessionState(BaseModel):
    status: Literal["unauthenticated", "pending_otp", "authenticated"]
    user: str | None = None
