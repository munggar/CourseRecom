"""Add official student roster and single-use registration invitations.

Revision ID: 20261121_06
Revises: 20261118_05
Create Date: 2026-11-21
"""

import sqlalchemy as sa
from alembic import op


revision = '20261121_06'
down_revision = '20261118_05'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if 'student_roster_entries' in sa.inspect(bind).get_table_names():
        return

    op.create_table(
        'student_roster_entries',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('nim', sa.String(length=20), nullable=False),
        sa.Column('full_name', sa.String(length=120), nullable=False),
        sa.Column('program_study', sa.String(length=120), nullable=False),
        sa.Column('angkatan', sa.String(length=4), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('registration_code_hash', sa.String(length=64), nullable=True),
        sa.Column('registration_code_expires_at', sa.DateTime(), nullable=True),
        sa.Column('registered_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('imported_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('imported_at', sa.DateTime(), nullable=False),
        sa.Column('registered_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('nim', name='uq_student_roster_entries_nim'),
        sa.UniqueConstraint('registered_user_id', name='uq_student_roster_entries_registered_user'),
    )
    op.create_index('ix_student_roster_entries_nim', 'student_roster_entries', ['nim'], unique=True)
    op.create_index('ix_student_roster_entries_registered_user_id', 'student_roster_entries', ['registered_user_id'])


def downgrade() -> None:
    op.drop_index('ix_student_roster_entries_registered_user_id', table_name='student_roster_entries')
    op.drop_index('ix_student_roster_entries_nim', table_name='student_roster_entries')
    op.drop_table('student_roster_entries')
