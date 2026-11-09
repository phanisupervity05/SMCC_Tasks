"""Add auto_output to calls

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
"""

from alembic import op
import sqlalchemy as sa

revision = 'f6g7h8i9j0k1'
down_revision = 'e5f6g7h8i9j0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('calls', sa.Column('auto_output', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('calls', 'auto_output')
