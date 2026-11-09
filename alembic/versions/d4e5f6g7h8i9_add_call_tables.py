"""Add call lead-score and call-audit tables

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-11-07 10:00:00.000000

Creates: calls, lead_scores, call_audits, rejected_requests.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6g7h8i9'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'calls',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_id', sa.String(64), nullable=False),
        sa.Column('lead_id', sa.String(128), nullable=True),
        sa.Column('agent_id', sa.String(128), nullable=False),
        sa.Column('agent_name', sa.String(255), nullable=False),
        sa.Column('customer_name', sa.String(255), nullable=True),
        sa.Column('call_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('recording_url', sa.Text(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('sent_to_auto_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_calls_id', 'calls', ['id'])
    op.create_index('ix_calls_task_id', 'calls', ['task_id'], unique=True)
    op.create_index('ix_calls_agent_id', 'calls', ['agent_id'])
    op.create_index('ix_calls_status', 'calls', ['status'])

    op.create_table(
        'lead_scores',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_id', sa.String(64), sa.ForeignKey('calls.task_id'), nullable=False),
        sa.Column('band', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(255), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_lead_scores_task_id', 'lead_scores', ['task_id'], unique=True)

    op.create_table(
        'call_audits',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_id', sa.String(64), sa.ForeignKey('calls.task_id'), nullable=False),
        sa.Column('checks', sa.JSON(), nullable=False),
        sa.Column('score_percent', sa.Float(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_call_audits_task_id', 'call_audits', ['task_id'], unique=True)

    op.create_table(
        'rejected_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('endpoint', sa.String(255), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_rejected_requests_created_at', 'rejected_requests', ['created_at'])


def downgrade() -> None:
    op.drop_table('rejected_requests')
    op.drop_table('call_audits')
    op.drop_table('lead_scores')
    op.drop_table('calls')
