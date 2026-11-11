"""Add indexes for the dashboard and list queries

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
"""

from alembic import op

revision = 'g7h8i9j0k1l2'
down_revision = 'f6g7h8i9j0k1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('ix_calls_created_at', 'calls', ['created_at'])
    op.create_index('ix_calls_status_sent_to_auto_at', 'calls', ['status', 'sent_to_auto_at'])
    op.create_index('ix_lead_scores_band', 'lead_scores', ['band'])


def downgrade() -> None:
    op.drop_index('ix_lead_scores_band', table_name='lead_scores')
    op.drop_index('ix_calls_status_sent_to_auto_at', table_name='calls')
    op.drop_index('ix_calls_created_at', table_name='calls')
