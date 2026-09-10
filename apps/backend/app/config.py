import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthUser(dict):
    """Thin typed-ish accessor over one AUTH_USERS entry."""

    @property
    def user(self) -> str:
        return self["user"]

    @property
    def pass_hash(self) -> str:
        return self["pass_hash"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = Field("sqlite:///./mesh_scheduler.db", alias="DATABASE_URL")

    mesh_serial_port: str = Field(alias="MESH_SERIAL_PORT")
    mesh_serial_baudrate: int = Field(115200, alias="MESH_SERIAL_BAUDRATE")
    mesh_channel_name: str = Field("#i2c-am2301", alias="MESH_CHANNEL_NAME")
    mesh_channel_idx: int = Field(3, alias="MESH_CHANNEL_IDX")

    # Channel broadcasts have no library-level ACK (unlike unicast send_msg/
    # send_cmd) — the actuator instead echoes state on the same channel,
    # decoupled from any specific send, e.g.
    # "Rtp-02-switch: PIN0=ON STATE=b10000000". The gateway's permanent
    # listener only trusts echoes whose node name matches this, since other
    # nodes may share the channel.
    mesh_actuator_name: str = Field("Rtp-02-switch", alias="MESH_ACTUATOR_NAME")

    auth_users_raw: str = Field("[]", alias="AUTH_USERS")
    otp_ttl_seconds: int = Field(120, alias="OTP_TTL_SECONDS")
    otp_max_attempts: int = Field(5, alias="OTP_MAX_ATTEMPTS")

    session_secret: str = Field(alias="SESSION_SECRET")
    tz: str = Field("UTC", alias="TZ")
    cors_origins_raw: str = Field("http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def auth_users(self) -> list[AuthUser]:
        return [AuthUser(item) for item in json.loads(self.auth_users_raw)]

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    @field_validator("mesh_channel_name")
    @classmethod
    def _must_not_be_public(cls, v: str) -> str:
        if v in ("", "0", "public"):
            raise ValueError("MESH_CHANNEL_NAME must never be the public channel")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
