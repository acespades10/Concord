"""Persist login rate limits across workers and application restarts."""

import sqlalchemy as sa
from alembic import op

revision = "62d8aa4e82b1"
down_revision = "11bd92d3f6d6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "login_budgets",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("started_at", sa.Float(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_login_budgets_started_at", "login_budgets", ["started_at"])


def downgrade():
    op.drop_index("ix_login_budgets_started_at", table_name="login_budgets")
    op.drop_table("login_budgets")
