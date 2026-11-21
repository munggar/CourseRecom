from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.deps import get_password_hash
from app.main import app
from app.models import AuditLog, User


def _create_student():
    suffix = uuid4().hex[:10]
    db = SessionLocal()
    user = User(
        nim=f'COOKIE{suffix}',
        username=f'cookie{suffix}',
        full_name='Mahasiswa Cookie Test',
        role='mahasiswa',
        password_hash=get_password_hash('cookie-password'),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    username = user.username
    db.close()
    return user_id, username


def _cleanup_student(user_id: int):
    db = SessionLocal()
    db.query(AuditLog).filter(AuditLog.actor_id == user_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_cookie_login_uses_httponly_cookie_and_logout_revokes_session():
    user_id, username = _create_student()
    client = TestClient(app)
    try:
        login = client.post(
            '/api/auth/login',
            headers={'X-Auth-Mode': 'cookie'},
            json={'username': username, 'password': 'cookie-password', 'role': 'mahasiswa'},
        )
        assert login.status_code == 200, login.text
        assert login.json()['access_token'] is None
        cookie_header = login.headers.get('set-cookie', '')
        assert 'course_recom_session=' in cookie_header
        assert 'httponly' in cookie_header.casefold()
        assert 'samesite=lax' in cookie_header.casefold()
        if settings.environment.casefold() in {'prod', 'production'}:
            assert 'secure' in cookie_header.casefold()

        me = client.get('/api/auth/me')
        assert me.status_code == 200
        assert me.json()['id'] == user_id

        blocked_csrf = client.put(
            '/api/auth/profile',
            headers={'Origin': 'https://attacker.invalid'},
            json={'full_name': 'Nama Berubah', 'username': username},
        )
        assert blocked_csrf.status_code == 403

        origin = settings.frontend_url.rstrip('/')
        logout = client.post('/api/auth/logout', headers={'Origin': origin})
        assert logout.status_code == 204
        assert 'course_recom_session=' in logout.headers.get('set-cookie', '')
        assert client.get('/api/auth/me').status_code == 401
    finally:
        client.close()
        _cleanup_student(user_id)


def test_legacy_bearer_session_can_be_migrated_to_httponly_cookie():
    user_id, username = _create_student()
    client = TestClient(app)
    try:
        login = client.post(
            '/api/auth/login',
            json={'username': username, 'password': 'cookie-password', 'role': 'mahasiswa'},
        )
        assert login.status_code == 200
        legacy_token = login.json()['access_token']
        assert legacy_token

        migrated = client.post(
            '/api/auth/session/migrate',
            headers={'Authorization': f'Bearer {legacy_token}'},
        )
        assert migrated.status_code == 204
        assert 'httponly' in migrated.headers.get('set-cookie', '').casefold()
        me = client.get('/api/auth/me')
        assert me.status_code == 200
        assert me.json()['id'] == user_id
    finally:
        client.close()
        _cleanup_student(user_id)
