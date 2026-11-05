import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal, ensure_schema
from app.deps import create_access_token, get_password_hash
from app.main import app
from app.models import User


client = TestClient(app)


def _create_user(db, suffix):
    user = User(
        nim=f'SEC-{suffix}',
        username=f'sec-{suffix}',
        full_name='Security Test User',
        role='mahasiswa',
        password_hash=get_password_hash('old-password'),
        token_version=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(autouse=True)
def cleanup_users():
    ensure_schema()
    db = SessionLocal()
    db.execute(text('PRAGMA foreign_keys=OFF'))
    db.query(User).filter(User.nim.like('SEC-%')).delete(synchronize_session=False)
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.execute(text('PRAGMA foreign_keys=OFF'))
    db.query(User).filter(User.nim.like('SEC-%')).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_password_change_invalidates_old_token_and_issues_new_login_token():
    db = SessionLocal()
    user = _create_user(db, 'PASSWORD')
    old_token = create_access_token(user.nim, user.role, user.token_version)
    db.close()

    old_response = client.put(
        '/api/auth/profile',
        headers={'Authorization': f'Bearer {old_token}'},
        json={
            'full_name': user.full_name,
            'username': user.username,
            'phone_number': '+628123456789',
            'current_password': 'old-password',
            'new_password': 'new-password',
        },
    )
    assert old_response.status_code == 200

    db = SessionLocal()
    user = db.query(User).filter(User.nim == 'SEC-PASSWORD').one()
    assert user.token_version == 1
    assert user.username.casefold() == 'sec-password'
    db.close()

    reused = client.get('/api/auth/me', headers={'Authorization': f'Bearer {old_token}'})
    assert reused.status_code == 401

    login = client.post('/api/auth/login', json={
        'username': 'sec-password',
        'password': 'new-password',
        'role': 'mahasiswa',
    })
    assert login.status_code == 200, login.text
    assert login.json()['access_token']


def test_username_change_invalidates_old_token():
    db = SessionLocal()
    user = _create_user(db, 'USERNAME')
    old_token = create_access_token(user.nim, user.role, user.token_version)
    db.close()

    response = client.put(
        '/api/auth/profile',
        headers={'Authorization': f'Bearer {old_token}'},
        json={
            'full_name': user.full_name,
            'username': 'sec-username-renamed',
            'phone_number': None,
        },
    )
    assert response.status_code == 200
    refreshed_token = response.json()['access_token']
    reused = client.get('/api/auth/me', headers={'Authorization': f'Bearer {old_token}'})
    assert reused.status_code == 401
    refreshed = client.get('/api/auth/me', headers={'Authorization': f'Bearer {refreshed_token}'})
    assert refreshed.status_code == 200
    assert refreshed.json()['username'] == 'sec-username-renamed'


def test_phone_profile_is_normalized_persisted_and_returned():
    db = SessionLocal()
    user = _create_user(db, 'PHONE')
    db.close()
    token = create_access_token('SEC-PHONE', 'mahasiswa', 0)

    response = client.put(
        '/api/auth/profile',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'full_name': 'Security Test User',
            'username': 'sec-phone',
            'phone_number': '+62 812-3456-789',
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()['phone_number'] == '+628123456789'

    profile = client.get('/api/auth/profile', headers={'Authorization': f'Bearer {token}'})
    assert profile.status_code == 200, profile.text
    assert profile.json()['phone_number'] == '+628123456789'


def test_local_indonesian_phone_number_is_normalized_on_profile_update():
    db = SessionLocal()
    user = _create_user(db, 'PHONE-LOCAL')
    token = create_access_token(user.nim, user.role, user.token_version)
    db.close()

    response = client.put(
        '/api/auth/profile',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'full_name': user.full_name,
            'username': user.username,
            'phone_number': '085934633905',
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()['phone_number'] == '+6285934633905'


def test_invalid_phone_is_rejected():
    token_user = User(
        nim='SEC-PHONE-INVALID',
        username='sec-phone-invalid',
        full_name='Invalid Phone User',
        role='mahasiswa',
        password_hash=get_password_hash('password'),
    )
    db = SessionLocal()
    db.add(token_user)
    db.commit()
    db.refresh(token_user)
    token = create_access_token(token_user.nim, token_user.role, token_user.token_version)
    db.close()

    response = client.put(
        '/api/auth/profile',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'full_name': token_user.full_name,
            'username': token_user.username,
            'phone_number': 'abc123',
        },
    )
    assert response.status_code == 422


def test_logout_invalidates_current_token():
    db = SessionLocal()
    user = _create_user(db, 'LOGOUT')
    token = create_access_token(user.nim, user.role, user.token_version)
    db.close()

    response = client.post('/api/auth/logout', headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 204
    reused = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert reused.status_code == 401
