"""add tenancy and subscription tables

Revision ID: c81a4f3d9b10
Revises: 4b7d0c91e2a3
Create Date: 2026-09-21 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c81a4f3d9b10"
down_revision: str | None = "4b7d0c91e2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_tenant_columns(table: str) -> None:
    op.add_column(table, sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.create_index(op.f(f"ix_{table}_tenant_id"), table, ["tenant_id"], unique=False)
    op.create_foreign_key(
        op.f(f"fk_{table}_tenant_id_tenants"),
        table,
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "plan_type",
            sa.Enum("free", "monthly", "yearly", name="plan_type", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "inactive",
                "expired",
                "canceled",
                name="subscription_status",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_customer_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_subscriptions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_subscriptions_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscriptions")),
    )
    op.create_index(op.f("ix_subscriptions_tenant_id"), "subscriptions", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_subscriptions_user_id"), "subscriptions", ["user_id"], unique=False)

    # Back-fill: every existing row is assigned to a single "Default Tenant" so
    # the new NOT NULL constraints can be applied safely to pre-SaaS data.
    op.execute(sa.text("INSERT INTO tenants (id, name) VALUES (1, 'Default Tenant')"))

    for table in ("users", "forms", "form_fields", "submissions"):
        _add_tenant_columns(table)

    op.execute(sa.text("UPDATE users SET tenant_id = 1 WHERE tenant_id IS NULL"))
    op.execute(sa.text("UPDATE forms SET tenant_id = 1 WHERE tenant_id IS NULL"))
    op.execute(
        sa.text("UPDATE form_fields SET tenant_id = 1 WHERE tenant_id IS NULL")
    )
    op.execute(
        sa.text("UPDATE submissions SET tenant_id = 1 WHERE tenant_id IS NULL")
    )

    for table in ("users", "forms", "form_fields", "submissions"):
        op.alter_column(table, "tenant_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    for table in ("users", "forms", "form_fields", "submissions"):
        op.drop_constraint(op.f(f"fk_{table}_tenant_id_tenants"), table, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table}_tenant_id"), table_name=table)
        op.drop_column(table, "tenant_id")

    op.drop_index(op.f("ix_subscriptions_user_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_tenant_id"), table_name="subscriptions")
    op.drop_constraint(op.f("fk_subscriptions_user_id_users"), "subscriptions", type_="foreignkey")
    op.drop_constraint(
        op.f("fk_subscriptions_tenant_id_tenants"), "subscriptions", type_="foreignkey"
    )
    op.drop_table("subscriptions")
    op.drop_table("tenants")