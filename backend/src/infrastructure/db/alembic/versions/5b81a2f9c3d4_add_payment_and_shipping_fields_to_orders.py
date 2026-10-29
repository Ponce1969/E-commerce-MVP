"""add payment and shipping fields to orders

Revision ID: 5b81a2f9c3d4
Revises: 3015a01c6cce
Create Date: 2026-10-28 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5b81a2f9c3d4"
down_revision: str | Sequence[str] | None = "3015a01c6cce"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

payment_method_enum = postgresql.ENUM(
    "BROU_TRANSFER", "MERCADO_PAGO", name="payment_method_enum", create_type=False
)
payment_status_enum = postgresql.ENUM(
    "PENDING", "PAID", "REJECTED", "EXPIRED", name="payment_status_enum", create_type=False
)


def upgrade() -> None:
    # 1. Create Enums if they don't exist
    conn = op.get_bind()
    payment_method_type = postgresql.ENUM(
        "BROU_TRANSFER", "MERCADO_PAGO", name="payment_method_enum"
    )
    payment_method_type.create(conn, checkfirst=True)

    payment_status_type = postgresql.ENUM(
        "PENDING", "PAID", "REJECTED", "EXPIRED", name="payment_status_enum"
    )
    payment_status_type.create(conn, checkfirst=True)

    # 2. Add columns to orders table
    op.add_column("orders", sa.Column("payment_method", payment_method_enum, nullable=True))
    op.add_column(
        "orders",
        sa.Column(
            "payment_status",
            payment_status_enum,
            server_default="PENDING",
            nullable=False,
        ),
    )
    op.add_column("orders", sa.Column("payment_id", sa.String(length=100), nullable=True))
    op.add_column("orders", sa.Column("preference_id", sa.String(length=100), nullable=True))
    op.add_column("orders", sa.Column("remito_postal", sa.String(length=100), nullable=True))
    op.add_column("orders", sa.Column("tracking_url", sa.String(length=500), nullable=True))

    # Structured shipping address columns
    op.add_column(
        "orders", sa.Column("shipping_recipient_name", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("shipping_document_number", sa.String(length=50), nullable=True)
    )
    op.add_column("orders", sa.Column("shipping_street", sa.String(length=255), nullable=True))
    op.add_column(
        "orders", sa.Column("shipping_street_number", sa.String(length=50), nullable=True)
    )
    op.add_column("orders", sa.Column("shipping_apartment", sa.String(length=50), nullable=True))
    op.add_column("orders", sa.Column("shipping_city", sa.String(length=100), nullable=True))
    op.add_column("orders", sa.Column("shipping_state", sa.String(length=100), nullable=True))
    op.add_column("orders", sa.Column("shipping_postal_code", sa.String(length=20), nullable=True))
    op.add_column("orders", sa.Column("shipping_phone", sa.String(length=50), nullable=True))
    op.add_column("orders", sa.Column("shipping_notes", sa.Text(), nullable=True))

    # 3. Create indexes
    op.create_index(op.f("ix_orders_payment_status"), "orders", ["payment_status"], unique=False)
    op.create_index(op.f("ix_orders_payment_id"), "orders", ["payment_id"], unique=False)
    op.create_index(op.f("ix_orders_preference_id"), "orders", ["preference_id"], unique=False)
    op.create_index(op.f("ix_orders_remito_postal"), "orders", ["remito_postal"], unique=False)


def downgrade() -> None:
    # 1. Drop indexes
    op.drop_index(op.f("ix_orders_remito_postal"), table_name="orders")
    op.drop_index(op.f("ix_orders_preference_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_payment_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_payment_status"), table_name="orders")

    # 2. Drop columns
    op.drop_column("orders", "shipping_notes")
    op.drop_column("orders", "shipping_phone")
    op.drop_column("orders", "shipping_postal_code")
    op.drop_column("orders", "shipping_state")
    op.drop_column("orders", "shipping_city")
    op.drop_column("orders", "shipping_apartment")
    op.drop_column("orders", "shipping_street_number")
    op.drop_column("orders", "shipping_street")
    op.drop_column("orders", "shipping_document_number")
    op.drop_column("orders", "shipping_recipient_name")
    op.drop_column("orders", "tracking_url")
    op.drop_column("orders", "remito_postal")
    op.drop_column("orders", "preference_id")
    op.drop_column("orders", "payment_id")
    op.drop_column("orders", "payment_status")
    op.drop_column("orders", "payment_method")

    # 3. Drop enums
    conn = op.get_bind()
    sa.Enum(name="payment_status_enum").drop(conn, checkfirst=True)
    sa.Enum(name="payment_method_enum").drop(conn, checkfirst=True)
