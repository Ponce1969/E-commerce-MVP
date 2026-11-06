"""create categories and product_categories nm tables

Revision ID: 8c2e4f6a1b3d
Revises: 7a1b3c4d5e6f
Create Date: 2026-11-05 22:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c2e4f6a1b3d"
down_revision: str | Sequence[str] | None = "7a1b3c4d5e6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create categories table
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
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
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )
    op.create_index(op.f("ix_categories_name"), "categories", ["name"], unique=True)
    op.create_index(op.f("ix_categories_is_active"), "categories", ["is_active"], unique=False)

    # 2. Create product_categories N:M association table
    op.create_table(
        "product_categories",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("product_id", "category_id"),
    )
    op.create_index(
        op.f("ix_product_categories_category_id"),
        "product_categories",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_categories_product_id"),
        "product_categories",
        ["product_id"],
        unique=False,
    )

    # 3. Make products.category nullable to support transition to N:M relation
    op.alter_column(
        "products",
        "category",
        existing_type=sa.String(length=100),
        nullable=True,
    )

    # 4. Data migration: populate categories table from existing distinct categories in products
    op.execute(
        """
        INSERT INTO categories (name, is_active)
        SELECT DISTINCT TRIM(category) AS name, true AS is_active
        FROM products
        WHERE category IS NOT NULL AND TRIM(category) != ''
        ON CONFLICT (name) DO NOTHING;
        """
    )

    # Sync serial sequence for categories
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('categories', 'id'),
            COALESCE((SELECT MAX(id) FROM categories), 1),
            true
        );
        """
    )

    # 5. Populate product_categories association table from existing products.category
    op.execute(
        """
        INSERT INTO product_categories (product_id, category_id)
        SELECT p.id, c.id
        FROM products p
        JOIN categories c ON TRIM(p.category) = c.name
        ON CONFLICT (product_id, category_id) DO NOTHING;
        """
    )

    # 6. Mass rounding sanitation (ROUND_HALF_UP to integers)
    op.execute(
        """
        UPDATE product_price_list_items
        SET sale_price = ROUND(sale_price, 0)
        WHERE sale_price != ROUND(sale_price, 0)
        """
    )
    op.execute(
        """
        UPDATE product_prices
        SET price_iva_inc = ROUND(price_iva_inc, 0)
        WHERE price_iva_inc IS NOT NULL AND price_iva_inc != ROUND(price_iva_inc, 0)
        """
    )


def downgrade() -> None:
    # Coalesce null categories back to 'General' before enforcing NOT NULL
    op.execute("UPDATE products SET category = 'General' WHERE category IS NULL;")
    op.alter_column(
        "products",
        "category",
        existing_type=sa.String(length=100),
        nullable=False,
    )

    op.drop_index(op.f("ix_product_categories_product_id"), table_name="product_categories")
    op.drop_index(op.f("ix_product_categories_category_id"), table_name="product_categories")
    op.drop_table("product_categories")

    op.drop_index(op.f("ix_categories_is_active"), table_name="categories")
    op.drop_index(op.f("ix_categories_name"), table_name="categories")
    op.drop_table("categories")
