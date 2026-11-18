"""Add persistent academic-advisor revision feedback.

Revision ID: 20261118_03
Revises: 20261105_02
Create Date: 2026-11-18
"""

from alembic import op
import sqlalchemy as sa


revision = '20261118_03'
down_revision = '20261105_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'advisor_feedback',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('study_plan_id', sa.Integer(), sa.ForeignKey('study_plans.id'), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('semester', sa.Integer(), nullable=False),
        sa.Column('affected_course_codes_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('reason_category', sa.String(length=40), nullable=False, server_default='general'),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('feedback_type', sa.String(length=30), nullable=False, server_default='revision_requested'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_advisor_feedback_student_id', 'advisor_feedback', ['student_id'])
    op.create_index('ix_advisor_feedback_study_plan_id', 'advisor_feedback', ['study_plan_id'])
    op.create_index('ix_advisor_feedback_student_semester', 'advisor_feedback', ['student_id', 'semester'])
    op.create_index('ix_advisor_feedback_study_plan', 'advisor_feedback', ['study_plan_id'])


def downgrade() -> None:
    op.drop_index('ix_advisor_feedback_study_plan', table_name='advisor_feedback')
    op.drop_index('ix_advisor_feedback_student_semester', table_name='advisor_feedback')
    op.drop_index('ix_advisor_feedback_study_plan_id', table_name='advisor_feedback')
    op.drop_index('ix_advisor_feedback_student_id', table_name='advisor_feedback')
    op.drop_table('advisor_feedback')
