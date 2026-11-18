"""Create course-level advisor feedback for recommendation learning.

Revision ID: 20261118_03
Revises: 20261105_02
Create Date: 2026-11-18
"""

import sqlalchemy as sa
from alembic import op


revision = '20261118_03'
down_revision = '20261105_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'advisor_course_feedback' in inspector.get_table_names():
        return

    op.create_table(
        'advisor_course_feedback',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('study_plan_id', sa.Integer(), sa.ForeignKey('study_plans.id'), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('semester', sa.Integer(), nullable=False),
        sa.Column('course_code', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_advisor_course_feedback_student_id', 'advisor_course_feedback', ['student_id'])
    op.create_index('ix_advisor_course_feedback_study_plan_id', 'advisor_course_feedback', ['study_plan_id'])
    op.create_index('ix_advisor_course_feedback_reviewer_id', 'advisor_course_feedback', ['reviewer_id'])
    op.create_index('ix_advisor_course_feedback_semester', 'advisor_course_feedback', ['semester'])
    op.create_index('ix_advisor_course_feedback_course_code', 'advisor_course_feedback', ['course_code'])


def downgrade() -> None:
    op.drop_index('ix_advisor_course_feedback_course_code', table_name='advisor_course_feedback')
    op.drop_index('ix_advisor_course_feedback_semester', table_name='advisor_course_feedback')
    op.drop_index('ix_advisor_course_feedback_reviewer_id', table_name='advisor_course_feedback')
    op.drop_index('ix_advisor_course_feedback_study_plan_id', table_name='advisor_course_feedback')
    op.drop_index('ix_advisor_course_feedback_student_id', table_name='advisor_course_feedback')
    op.drop_table('advisor_course_feedback')
