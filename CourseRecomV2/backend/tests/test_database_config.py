from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Base
from app.models import StudyPlan, User


def test_plain_postgres_url_uses_installed_psycopg_driver():
    settings = Settings(
        database_url='postgresql://user:password@db.example.com/course?sslmode=require',
    )

    assert settings.database_url == (
        'postgresql+psycopg://user:password@db.example.com/course?sslmode=require'
    )


def test_legacy_postgres_scheme_uses_installed_psycopg_driver():
    settings = Settings(database_url='postgres://user:password@db.example.com/course')

    assert settings.database_url == 'postgresql+psycopg://user:password@db.example.com/course'


def test_bootstrap_admin_settings_must_be_complete():
    with pytest.raises(ValidationError, match='must be configured together'):
        Settings(bootstrap_admin_nim='admin')


def test_demo_accounts_default_only_in_development_and_testing(monkeypatch):
    monkeypatch.delenv('SEED_DEMO_USERS', raising=False)
    assert Settings(environment='development').seed_demo_users is True
    assert Settings(environment='testing').seed_demo_users is True
    assert Settings(
        environment='production',
        jwt_secret='a' * 40,
        qr_verification_secret='b' * 40,
        public_api_base_url='https://api.example.edu/api',
    ).seed_demo_users is False


def test_demo_account_seeding_cannot_be_enabled_outside_development_or_testing():
    with pytest.raises(ValidationError, match='only be enabled'):
        Settings(environment='production', seed_demo_users=True)
    with pytest.raises(ValidationError, match='only be enabled'):
        Settings(environment='staging', seed_demo_users=True)


def test_production_requires_public_https_api_base_for_qr():
    with pytest.raises(ValidationError, match='PUBLIC_API_BASE_URL'):
        Settings(
            environment='production',
            seed_demo_users=False,
            jwt_secret='a' * 40,
            qr_verification_secret='b' * 40,
        )


def test_render_public_url_configures_frontend_and_qr_origins(monkeypatch):
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'https://courserecom.onrender.com/')
    monkeypatch.delenv('FRONTEND_URL', raising=False)

    settings = Settings(
        environment='production',
        seed_demo_users=False,
        jwt_secret='a' * 40,
        qr_verification_secret='b' * 40,
    )

    assert settings.frontend_url == 'https://courserecom.onrender.com'
    assert settings.public_api_base_url == 'https://courserecom.onrender.com/api'


def test_production_rejects_empty_and_default_secrets():
    with pytest.raises(ValidationError, match='JWT_SECRET'):
        Settings(
            environment='production',
            seed_demo_users=False,
            jwt_secret='',
            qr_verification_secret='q' * 40,
            public_api_base_url='https://api.example.edu/api',
        )
    with pytest.raises(ValidationError, match='JWT_SECRET'):
        Settings(
            environment='production',
            seed_demo_users=False,
            jwt_secret='course-recom-dev-secret-change-me',
            qr_verification_secret='q' * 40,
            public_api_base_url='https://api.example.edu/api',
        )


@pytest.mark.parametrize(
    'public_api_base_url',
    [
        'https://backend/api',
        'https://localhost/api',
        'https://127.0.0.1/api',
        'https://api.internal/api',
    ],
)
def test_production_rejects_internal_qr_hosts(public_api_base_url):
    with pytest.raises(ValidationError, match='PUBLIC_API_BASE_URL'):
        Settings(
            environment='production',
            seed_demo_users=False,
            jwt_secret='a' * 40,
            qr_verification_secret='b' * 40,
            public_api_base_url=public_api_base_url,
        )


def test_cloud_seed_can_create_admin_without_demo_accounts(monkeypatch):
    import app.seed as seed

    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    monkeypatch.setattr(seed, 'SessionLocal', lambda: Session(engine))
    monkeypatch.setattr(seed.settings, 'seed_demo_users', False)
    monkeypatch.setattr(seed.settings, 'bootstrap_admin_nim', 'cloud-admin')
    monkeypatch.setattr(seed.settings, 'bootstrap_admin_name', 'Cloud Admin')
    monkeypatch.setattr(seed.settings, 'bootstrap_admin_password', 'unique-cloud-password')

    seed.seed_data()

    with Session(engine) as db:
        users = db.query(User).all()
        assert len(users) == 1
        assert users[0].nim == 'cloud-admin'
        assert users[0].role == 'admin'


def test_study_plan_index_allows_only_one_pending_plan_per_student():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with Session(engine) as db:
        db.add(User(
            nim='TESTINDEX',
            full_name='Mahasiswa Uji',
            role='mahasiswa',
            password_hash='test-only',
        ))
        db.flush()
        student = db.query(User).filter_by(nim='TESTINDEX').one()
        db.add(StudyPlan(
            student_id=student.id,
            semester=3,
            courses_json='[]',
            status='pending',
            created_at=now,
            updated_at=now,
        ))
        db.commit()
        db.add(StudyPlan(
            student_id=student.id,
            semester=3,
            courses_json='[]',
            status='pending',
            created_at=now,
            updated_at=now,
        ))
        with pytest.raises(IntegrityError):
            db.commit()
