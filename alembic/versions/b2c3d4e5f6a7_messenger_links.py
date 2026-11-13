"""Messenger links table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-13 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: str | Sequence[str] | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('messenger_links',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('platform', sa.String(length=20), nullable=False),
    sa.Column('external_user_id', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('messenger_links', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_messenger_links_platform'), ['platform'], unique=False)
        batch_op.create_index(batch_op.f('ix_messenger_links_external_user_id'), ['external_user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('messenger_links', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_messenger_links_external_user_id'))
        batch_op.drop_index(batch_op.f('ix_messenger_links_platform'))

    op.drop_table('messenger_links')
