"""Add Command Center policies and call flags

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
"""

from alembic import op
import sqlalchemy as sa

revision = 'h8i9j0k1l2m3'
down_revision = 'g7h8i9j0k1l2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'command_policies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(120), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('stage', sa.String(16), nullable=False),
        sa.Column('action', sa.String(16), nullable=False),
        sa.Column('match_mode', sa.String(8), nullable=False, server_default='all'),
        sa.Column('conditions', sa.JSON(), nullable=False),
        sa.Column('message', sa.String(255), nullable=True),
        sa.Column('source', sa.String(16), nullable=False, server_default='builder'),
        sa.Column('natural_language', sa.Text(), nullable=True),
        sa.Column('hit_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.String(128), nullable=True),
        sa.Column('updated_by', sa.String(128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'call_flags',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_id', sa.String(64), sa.ForeignKey('calls.task_id'), nullable=False),
        sa.Column('policy_id', sa.Integer(), nullable=False),
        sa.Column('policy_name', sa.String(120), nullable=False),
        sa.Column('message', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('task_id', 'policy_id', name='uq_call_flags_task_policy'),
    )
    op.create_index('ix_call_flags_task_id', 'call_flags', ['task_id'])
    op.create_index('ix_call_flags_policy_id', 'call_flags', ['policy_id'])


def downgrade() -> None:
    op.drop_index('ix_call_flags_policy_id', table_name='call_flags')
    op.drop_index('ix_call_flags_task_id', table_name='call_flags')
    op.drop_table('call_flags')
    op.drop_table('command_policies')
