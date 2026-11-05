"""create price lists and product price list items tables

Revision ID: 7a1b3c4d5e6f
Revises: 5b81a2f9c3d4
Create Date: 2026-11-04 22:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a1b3c4d5e6f"
down_revision: str | Sequence[str] | None = "5b81a2f9c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create price_lists table
    op.create_table(
        "price_lists",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_price_lists_code"),
    )
    op.create_index(op.f("ix_price_lists_code"), "price_lists", ["code"], unique=True)

    # Seed the 5 canonical price lists matching existing commercial lists
    op.execute(
        """
        INSERT INTO price_lists (id, code, name, description, is_active)
        VALUES
            (1, 'EMPRESAS_LIMPIEZA', 'Empresas / Limpieza', 'Canal corporativo y empresas de limpieza', true),
            (2, 'RESIDENCIALES', 'Residenciales', 'Residenciales de ancianos y casas de salud', true),
            (3, 'LAVANDERIA_PRO', 'Lavandería profesional', 'Lavanderías industriales y comerciales', true),
            (4, 'LAVANDERIA_DOM', 'Lavandería domiciliaria', 'Servicios de lavandería doméstica', true),
            (5, 'AUTOMOTRIZ', 'Automotriz', 'Talleres y lavaderos automotrices', true)
        ON CONFLICT (id) DO UPDATE
        SET code = EXCLUDED.code, name = EXCLUDED.name, description = EXCLUDED.description;
        """
    )
    # Ensure serial sequence is synced
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('price_lists', 'id'),
            COALESCE((SELECT MAX(id) FROM price_lists), 1),
            true
        );
        """
    )

    # 2. Create product_price_list_items table
    op.create_table(
        "product_price_list_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("price_list_id", sa.Integer(), nullable=False),
        sa.Column("sale_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.ForeignKeyConstraint(["price_list_id"], ["price_lists.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "price_list_id", name="uq_product_price_list"),
    )
    op.create_index(
        op.f("ix_product_price_list_items_price_list_id"),
        "product_price_list_items",
        ["price_list_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_price_list_items_product_id"),
        "product_price_list_items",
        ["product_id"],
        unique=False,
    )

    # 3. Data migration: Migrate active prices from product_prices with commercial rounding
    op.execute(
        """
        INSERT INTO product_price_list_items (product_id, price_list_id, sale_price, is_active)
        SELECT
            pp.product_id,
            pp.commercial_list_id AS price_list_id,
            ROUND(pp.price_iva_inc, 0) AS sale_price,
            true AS is_active
        FROM product_prices pp
        JOIN price_lists pl ON pl.id = pp.commercial_list_id
        WHERE pp.price_iva_inc IS NOT NULL AND pp.price_iva_inc > 0
        ON CONFLICT (product_id, price_list_id) DO UPDATE
        SET sale_price = EXCLUDED.sale_price;
        """
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_product_price_list_items_product_id"), table_name="product_price_list_items"
    )
    op.drop_index(
        op.f("ix_product_price_list_items_price_list_id"), table_name="product_price_list_items"
    )
    op.drop_table("product_price_list_items")

    op.drop_index(op.f("ix_price_lists_code"), table_name="price_lists")
    op.drop_table("price_lists")
