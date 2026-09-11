"""audit tables: event_sends, actuator_acks

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_sends",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_label", sa.String(200), nullable=True),
        sa.Column("pin", sa.Integer, nullable=False),
        sa.Column("edge", sa.String(3), nullable=False),
        sa.Column("message", sa.String(32), nullable=False),
        sa.Column("sent_at", sa.DateTime, nullable=False),
        sa.Column("ok", sa.Boolean, nullable=False),
        sa.Column("error", sa.String(500), nullable=True),
    )
    op.create_index("ix_event_sends_sent_at", "event_sends", ["sent_at"])

    op.create_table(
        "actuator_acks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("node", sa.String(100), nullable=False),
        sa.Column("state_bits", sa.String(8), nullable=False),
        sa.Column("observed_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_actuator_acks_observed_at", "actuator_acks", ["observed_at"])


def downgrade() -> None:
    op.drop_index("ix_actuator_acks_observed_at", table_name="actuator_acks")
    op.drop_table("actuator_acks")
    op.drop_index("ix_event_sends_sent_at", table_name="event_sends")
    op.drop_table("event_sends")
