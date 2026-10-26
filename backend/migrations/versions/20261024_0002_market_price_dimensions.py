"""Retain market-price variety and grade dimensions.

These nullable fields preserve existing rows and let the importer keep source
observations separate when several varieties/grades share a market and date.
"""

from alembic import op
import sqlalchemy as sa


revision = "20261024_0002"
down_revision = "20261024_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("market_prices", sa.Column("variety", sa.String(length=100), nullable=True))
    op.add_column("market_prices", sa.Column("grade", sa.String(length=100), nullable=True))
    op.create_index(
        "ix_market_prices_crop_market_variant_date",
        "market_prices",
        ["crop_id", "market_id", "variety", "grade", sa.literal_column("price_date").desc()],
        unique=False,
    )
    op.add_column("selling_requests", sa.Column("buyer_offer_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_selling_requests_buyer_offer_id_buyer_offers",
        "selling_requests", "buyer_offers", ["buyer_offer_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_selling_requests_buyer_offer_id", "selling_requests", ["buyer_offer_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_selling_requests_buyer_offer_id", "selling_requests", type_="unique")
    op.drop_constraint(
        "fk_selling_requests_buyer_offer_id_buyer_offers", "selling_requests", type_="foreignkey"
    )
    op.drop_column("selling_requests", "buyer_offer_id")
    op.drop_index("ix_market_prices_crop_market_variant_date", table_name="market_prices")
    op.drop_column("market_prices", "grade")
    op.drop_column("market_prices", "variety")
