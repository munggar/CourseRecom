"""Create missing CourseRecom schema and add legacy columns safely.

Revision ID: 20261104_01
Revises:
Create Date: 2026-11-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import and_, inspect, select, text

from app.database import Base
import app.models


revision = '20261104_01'
down_revision = None
branch_labels = None
depends_on = None


LEGACY_COLUMNS = {
    'users': [
        sa.Column('advisor_id', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(length=120), nullable=True),
        sa.Column('program_study', sa.String(length=120), nullable=True),
        sa.Column('angkatan', sa.String(length=20), nullable=True),
    ],
    'khs_documents': [
        sa.Column('content', sa.LargeBinary(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    ],
    'student_records': [
        sa.Column('semester', sa.Integer(), nullable=True),
        sa.Column('course_name', sa.String(length=120), nullable=True),
        sa.Column('sks', sa.Integer(), nullable=True),
        sa.Column('numeric_grade', sa.Float(), nullable=True),
        sa.Column('grade_point', sa.Float(), nullable=True),
        sa.Column('is_passed', sa.Boolean(), nullable=True),
    ],
    'courses': [
        sa.Column('available_semesters', sa.String(length=40), nullable=True),
        sa.Column('prerequisite_text', sa.Text(), nullable=True),
        sa.Column('capacity', sa.Integer(), nullable=False, server_default='40'),
    ],
}


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    inspector = inspect(bind)

    for table_name, columns in LEGACY_COLUMNS.items():
        existing = {column['name'] for column in inspector.get_columns(table_name)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table_name, column)

    inspector = inspect(bind)
    _assert_no_orphaned_foreign_keys(bind)
    _ensure_foreign_keys(bind)
    inspector = inspect(bind)
    for table in Base.metadata.sorted_tables:
        existing_indexes = {index['name'] for index in inspector.get_indexes(table.name)}
        for index in table.indexes:
            if index.name in existing_indexes:
                continue
            if index.name == 'uq_study_plans_one_pending_per_student':
                duplicates = bind.execute(text(
                    "SELECT student_id, COUNT(*) FROM study_plans "
                    "WHERE status = 'pending' GROUP BY student_id HAVING COUNT(*) > 1"
                )).all()
                if duplicates:
                    raise RuntimeError(
                        'Multiple pending study plans exist for the same student; '
                        f'resolve without deleting records before migration: {duplicates}'
                    )
            options = index.dialect_options
            op.create_index(
                index.name,
                table.name,
                [column.name for column in index.columns],
                unique=index.unique,
                sqlite_where=options['sqlite'].get('where'),
                postgresql_where=options['postgresql'].get('where'),
            )


def _assert_no_orphaned_foreign_keys(bind) -> None:
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_columns = {
            column['name'] for column in inspector.get_columns(table.name)
        }
        for foreign_key in table.foreign_keys:
            source = foreign_key.parent
            referenced = foreign_key.column
            if source.name not in existing_columns or referenced.table.name not in existing_tables:
                continue
            target = referenced.table.alias('fk_target')
            orphans = bind.execute(
                select(source)
                .select_from(table.outerjoin(target, source == target.c[referenced.name]))
                .where(and_(source.is_not(None), target.c[referenced.name].is_(None)))
                .limit(10)
            ).scalars().all()
            if orphans:
                raise RuntimeError(
                    'Orphaned foreign-key values detected; no data was removed. '
                    'Export and remediate these references before retrying migration: '
                    f'{table.name}.{source.name} -> {referenced.table.name}.{referenced.name}; '
                    f'samples={orphans}'
                )


def _ensure_foreign_keys(bind) -> None:
    inspector = inspect(bind)
    for table in Base.metadata.sorted_tables:
        existing = {
            (
                tuple(foreign_key['constrained_columns']),
                foreign_key['referred_table'],
                tuple(foreign_key['referred_columns']),
            )
            for foreign_key in inspector.get_foreign_keys(table.name)
        }
        missing = [
            foreign_key
            for foreign_key in table.foreign_keys
            if (
                (foreign_key.parent.name,),
                foreign_key.column.table.name,
                (foreign_key.column.name,),
            ) not in existing
        ]
        if not missing:
            continue
        if bind.dialect.name == 'sqlite':
            with op.batch_alter_table(table.name, recreate='always') as batch:
                for foreign_key in missing:
                    batch.create_foreign_key(
                        f'fk_{table.name}_{foreign_key.parent.name}_{foreign_key.column.table.name}',
                        foreign_key.column.table.name,
                        [foreign_key.parent.name],
                        [foreign_key.column.name],
                    )
        else:
            for foreign_key in missing:
                op.create_foreign_key(
                    f'fk_{table.name}_{foreign_key.parent.name}_{foreign_key.column.table.name}',
                    table.name,
                    foreign_key.column.table.name,
                    [foreign_key.parent.name],
                    [foreign_key.column.name],
                )
        inspector = inspect(bind)


def downgrade() -> None:
    raise RuntimeError('This data-preserving baseline migration has no automatic downgrade.')
