"""Add preparations product type.

Revision ID: 37a5a7b73d4a
Revises: ea84b5ce47e9
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "37a5a7b73d4a"
down_revision: str | Sequence[str] | None = "ea84b5ce47e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRODUCT_TYPE = "preparations 🍲"


def upgrade() -> None:
    """Seed preparations in databases created before this category existed."""
    product_type = sa.table(
        "product_type", sa.column("id", sa.Integer), sa.column("name", sa.String)
    )
    connection = op.get_bind()
    exists = connection.scalar(
        sa.select(product_type.c.id).where(product_type.c.name == PRODUCT_TYPE)
    )
    if exists is None:
        connection.execute(sa.insert(product_type).values(name=PRODUCT_TYPE))


def downgrade() -> None:
    """Remove preparations only when no products reference it."""
    product_type = sa.table(
        "product_type", sa.column("id", sa.Integer), sa.column("name", sa.String)
    )
    product = sa.table("product", sa.column("product_type_id", sa.Integer))
    connection = op.get_bind()
    product_type_id = connection.scalar(
        sa.select(product_type.c.id).where(product_type.c.name == PRODUCT_TYPE)
    )
    if product_type_id is None:
        return

    is_used = connection.scalar(
        sa.select(sa.literal(True))
        .select_from(product)
        .where(product.c.product_type_id == product_type_id)
        .limit(1)
    )
    if not is_used:
        connection.execute(sa.delete(product_type).where(product_type.c.id == product_type_id))
