"""add password reset OTP columns to users

Revision ID: 4b7d0c91e2a3
Revises: 7fb0f06463a3
Create Date: 2026-09-21 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4b7d0c91e2a3"
down_revision: str | None = "7fb0f06463a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("reset_otp_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("reset_otp_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "reset_otp_expires_at")
    op.drop_column("users", "reset_otp_hash")