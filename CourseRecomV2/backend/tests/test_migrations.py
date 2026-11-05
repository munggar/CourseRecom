from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from pathlib import Path

ALEMBIC_INI = Path(__file__).resolve().parent.parent / 'alembic.ini'


def _upgrade(database_url):
    config = Config(ALEMBIC_INI)
    config.set_main_option('sqlalchemy.url', database_url.replace('%', '%%'))
    config.set_main_option('script_location', str(ALEMBIC_INI.parent / 'alembic'))
    command.upgrade(config, 'head')


def _create_legacy_database(database_url, *, orphan=False):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(
            'CREATE TABLE users ('
            'id INTEGER PRIMARY KEY, nim VARCHAR(20) NOT NULL UNIQUE, '
            'full_name VARCHAR(120) NOT NULL, role VARCHAR(20) NOT NULL, '
            'email VARCHAR(120), password_hash VARCHAR(255) NOT NULL, '
            'is_active BOOLEAN, semester INTEGER, ipk FLOAT, sks_lulus INTEGER, '
            'sks_sisa INTEGER, kuota_sks INTEGER, interests VARCHAR(255))'
        ))
        connection.execute(text(
            'CREATE TABLE courses ('
            'id INTEGER PRIMARY KEY, code VARCHAR(20) NOT NULL UNIQUE, '
            'name VARCHAR(120) NOT NULL, sks INTEGER NOT NULL, semester INTEGER NOT NULL, '
            'category VARCHAR(60) NOT NULL, description TEXT, day VARCHAR(20), '
            'time VARCHAR(60), prerequisite_codes VARCHAR(255), is_active BOOLEAN)'
        ))
        connection.execute(text(
            'CREATE TABLE student_records ('
            'id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES users(id), '
            'course_code VARCHAR(20) NOT NULL, grade VARCHAR(2) NOT NULL)'
        ))
        connection.execute(text(
            'CREATE TABLE khs_documents ('
            'id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES users(id), '
            'filename VARCHAR(255) NOT NULL, sha256 VARCHAR(64) NOT NULL, '
            'status VARCHAR(20) NOT NULL, parsed_data TEXT NOT NULL, '
            'created_at DATETIME NOT NULL)'
        ))
        connection.execute(text(
            "INSERT INTO users (id, nim, full_name, role, password_hash) "
            "VALUES (1, 'LEGACY1', 'Legacy Student', 'mahasiswa', 'hash')"
        ))
        connection.execute(text(
            "INSERT INTO courses (id, code, name, sks, semester, category) "
            "VALUES (1, 'LEG001', 'Legacy Course', 3, 1, 'Wajib')"
        ))
        connection.execute(text(
            'INSERT INTO student_records (id, student_id, course_code, grade) '
            f"VALUES (1, {99 if orphan else 1}, 'LEG001', 'A')"
        ))
        connection.execute(text(
            "INSERT INTO khs_documents "
            "(id, student_id, filename, sha256, status, parsed_data, created_at) "
            "VALUES (1, 1, 'legacy.pdf', 'a', 'confirmed', '{}', CURRENT_TIMESTAMP)"
        ))
    engine.dispose()


def test_fresh_migration_is_repeatable_and_creates_constraints(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'fresh.sqlite').as_posix()}"
    _upgrade(database_url)
    _upgrade(database_url)

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert 'kprs_requests' in inspector.get_table_names()
    assert 'advisor_id' in {
        column['name'] for column in inspector.get_columns('users')
    }
    assert any(
        index['name'] == 'uq_study_plans_one_pending_per_student'
        for index in inspector.get_indexes('study_plans')
    )
    assert inspector.get_foreign_keys('student_records')
    engine.dispose()


def test_legacy_migration_preserves_academic_history_and_adds_columns(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'legacy.sqlite').as_posix()}"
    _create_legacy_database(database_url)
    _upgrade(database_url)

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.execute(text(
            'SELECT nim FROM users WHERE id = 1'
        )).scalar_one() == 'LEGACY1'
        assert connection.execute(text(
            'SELECT course_code, grade FROM student_records WHERE id = 1'
        )).one() == ('LEG001', 'A')
        assert connection.execute(text(
            'SELECT filename FROM khs_documents WHERE id = 1'
        )).scalar_one() == 'legacy.pdf'
    assert {'semester', 'grade_point', 'is_passed'} <= {
        column['name'] for column in inspect(engine).get_columns('student_records')
    }
    assert {'content', 'updated_at'} <= {
        column['name'] for column in inspect(engine).get_columns('khs_documents')
    }
    assert any(
        foreign_key['constrained_columns'] == ['advisor_id']
        and foreign_key['referred_table'] == 'users'
        for foreign_key in inspect(engine).get_foreign_keys('users')
    )
    engine.dispose()


def test_migration_reports_orphans_without_deleting_them(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'orphan.sqlite').as_posix()}"
    _create_legacy_database(database_url, orphan=True)

    try:
        _upgrade(database_url)
    except RuntimeError as exc:
        assert 'Orphaned foreign-key values detected' in str(exc)
        assert 'samples=[99]' in str(exc)
    else:
        raise AssertionError('Migration should report, not silently accept, orphaned history.')

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.execute(text(
            'SELECT student_id FROM student_records WHERE id = 1'
        )).scalar_one() == 99
    engine.dispose()
