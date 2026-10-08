"""Use upstream model names as IDs for previously imported models."""
from alembic import op
import sqlalchemy as sa


revision = "20261008_1200_unprefix_imported_model_ids"
down_revision = "20261008_1100_user_avatar"
branch_labels = None
depends_on = None


def upgrade():
    db = op.get_bind()
    bindings = db.execute(sa.text("""
        SELECT mc.model_id, mc.upstream_model, c.type AS channel_type
        FROM model_channels mc JOIN channels c ON c.channel_id = mc.channel_id
    """)).mappings().all()
    by_model = {}
    for binding in bindings:
        by_model.setdefault(binding["model_id"], []).append(binding)

    for old_id, rows in by_model.items():
        upstream_ids = {row["upstream_model"] for row in rows}
        if len(upstream_ids) != 1:
            continue
        new_id = upstream_ids.pop()
        if not any(old_id == f"{row['channel_type']}-{new_id}" for row in rows):
            continue

        params = {"old_id": old_id, "new_id": new_id}
        exists = db.execute(sa.text("SELECT 1 FROM models WHERE model_id = :new_id"), params).first()
        if not exists:
            db.execute(sa.text("""
                INSERT INTO models (
                    model_id, display_name, description, aliases, price_type,
                    price_per_1k_input, price_per_1k_output, price_per_request,
                    status, route_strategy, created_at, updated_at
                )
                SELECT :new_id, display_name, description, aliases, price_type,
                    price_per_1k_input, price_per_1k_output, price_per_request,
                    status, route_strategy, created_at, updated_at
                FROM models WHERE model_id = :old_id
            """), params)

        db.execute(sa.text("""
            INSERT INTO model_group_model_mappings (group_id, model_id, created_at)
            SELECT old.group_id, :new_id, old.created_at
            FROM model_group_model_mappings old
            WHERE old.model_id = :old_id
              AND NOT EXISTS (
                SELECT 1 FROM model_group_model_mappings existing
                WHERE existing.group_id = old.group_id AND existing.model_id = :new_id
              )
        """), params)
        db.execute(sa.text("""
            INSERT INTO model_channels (
                model_id, channel_id, upstream_model, priority, weight, enabled,
                created_at, updated_at
            )
            SELECT :new_id, old.channel_id, old.upstream_model, old.priority,
                old.weight, old.enabled, old.created_at, old.updated_at
            FROM model_channels old
            WHERE old.model_id = :old_id
              AND NOT EXISTS (
                SELECT 1 FROM model_channels existing
                WHERE existing.model_id = :new_id AND existing.channel_id = old.channel_id
              )
        """), params)
        db.execute(sa.text("UPDATE chat_conversations SET model_id = :new_id WHERE model_id = :old_id"), params)
        db.execute(sa.text("DELETE FROM model_group_model_mappings WHERE model_id = :old_id"), params)
        db.execute(sa.text("DELETE FROM model_channels WHERE model_id = :old_id"), params)
        db.execute(sa.text("DELETE FROM models WHERE model_id = :old_id"), params)


def downgrade():
    pass  # Merged model IDs cannot be separated reliably.
