"""Add transcript to calls

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
"""

from alembic import op
import sqlalchemy as sa

revision = 'e5f6g7h8i9j0'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('calls', sa.Column('transcript', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('calls', 'transcript')
