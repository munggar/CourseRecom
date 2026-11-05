"""Add account phone and token version fields.

Revision ID: 20261105_02
Revises: 20261104_01
Create Date: 2026-11-05
"""

import sqlalchemy as sa
from alembic import op


revision = '20261105_02'
down_revision = '20261104_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {column['name'] for column in sa.inspect(bind).get_columns('users')}
    with op.batch_alter_table('users') as batch:
        if 'token_version' not in existing:
            batch.add_column(sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'))
        if 'phone_number' not in existing:
            batch.add_column(sa.Column('phone_number', sa.String(length=20), nullable=True))
    with op.batch_alter_table('users') as batch:
        batch.alter_column('token_version', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('phone_number')
        batch.drop_column('token_version')
