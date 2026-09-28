"""persistent operational alert state"""
from alembic import op
import sqlalchemy as sa

revision = "20260928_1200_alert_rules"
down_revision = "20260924_1100_model_route_strategy"
branch_labels = None
depends_on = None

def upgrade():
    if "alert_states" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table("alert_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alert_key", sa.String(160), nullable=False),
        sa.Column("alert_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("last_value", sa.String(64)),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("alert_key", name="uq_alert_state_key"))

def downgrade():
    if "alert_states" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("alert_states")
