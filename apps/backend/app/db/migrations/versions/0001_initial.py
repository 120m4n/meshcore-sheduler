"""initial schema: events, otp_challenges

Revision ID: 0001
Revises:
Create Date: 2026-09-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("pin", sa.Integer, nullable=False),
        sa.Column("recurrence", sa.String(16), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("on_time", sa.Time, nullable=False),
        sa.Column("off_time", sa.Time, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "otp_challenges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("user", sa.String(100), nullable=False),
        sa.Column("code_hash", sa.String(100), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("consumed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_otp_challenges_session_id", "otp_challenges", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_otp_challenges_session_id", table_name="otp_challenges")
    op.drop_table("otp_challenges")
    op.drop_table("events")
