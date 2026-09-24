"""Add model route strategy."""
from alembic import op
import sqlalchemy as sa


revision = "20260924_1100_model_route_strategy"
down_revision = "20260924_1000_route_decision_logs"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "route_strategy" not in {column["name"] for column in inspector.get_columns("models")}:
        op.add_column("models", sa.Column("route_strategy", sa.String(20), nullable=False, server_default="priority"))


def downgrade():
    op.drop_column("models", "route_strategy")
