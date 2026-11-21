import csv
from io import StringIO
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, StudentRosterEntry, User


def _login_admin(client: TestClient) -> dict[str, str]:
    login = client.post(
        '/api/auth/login',
        json={'username': 'admin', 'password': 'password123', 'role': 'admin'},
    )
    assert login.status_code == 200, login.text
    return {'Authorization': f"Bearer {login.json()['access_token']}"}


def _registration_payload(nim: str, code: str | None = None) -> dict:
    return {
        'nim': nim,
        'full_name': 'Mahasiswa Roster Uji',
        'program_study': 'Sistem dan Teknologi Informasi',
        'interests': 'Manajemen Teknologi Informasi',
        'angkatan': '2022',
        'registration_code': code,
        'password': 'password-roster-123',
    }


def test_production_style_registration_requires_roster_and_consumes_invitation_once():
    old_setting = settings.require_student_roster
    settings.require_student_roster = True
    nim = f'ROSTER{uuid4().hex[:10]}'
    client = TestClient(app)
    admin_id = None
    try:
        admin_headers = _login_admin(client)
        db = SessionLocal()
        admin_id = db.query(User.id).filter(User.nim == 'admin').scalar()
        db.close()

        blocked = client.post('/api/auth/register', json=_registration_payload(nim))
        assert blocked.status_code == 403
        assert 'roster resmi' in blocked.text

        roster_csv = StringIO(newline='')
        writer = csv.writer(roster_csv)
        writer.writerow(['NIM', 'Nama Lengkap', 'Program Studi', 'Angkatan'])
        writer.writerow([nim, 'Mahasiswa Roster Uji', 'Sistem dan Teknologi Informasi', '2022'])
        imported = client.post(
            '/api/admin/student-roster/import',
            headers=admin_headers,
            files={'file': ('roster.csv', roster_csv.getvalue().encode('utf-8'), 'text/csv')},
        )
        assert imported.status_code == 200, imported.text
        assert imported.json()['total_active'] >= 1
        assert imported.json()['waiting'] >= 1

        summary = client.get('/api/admin/student-roster', headers=admin_headers)
        assert summary.status_code == 200
        assert summary.json()['target'] == 100

        invitations = client.post('/api/admin/student-roster/invitations.csv', headers=admin_headers)
        assert invitations.status_code == 200
        rows = list(csv.DictReader(StringIO(invitations.content.decode('utf-8-sig'))))
        invitation = next(row for row in rows if row['NIM'] == nim)
        code = invitation['Kode Pendaftaran']
        assert len(code) >= 24

        missing_code = client.post('/api/auth/register', json=_registration_payload(nim))
        assert missing_code.status_code == 403

        wrong_code = client.post('/api/auth/register', json=_registration_payload(nim, 'wrong-code-value-000000'))
        assert wrong_code.status_code == 403

        mismatched_name = _registration_payload(nim, code)
        mismatched_name['full_name'] = 'Nama Tidak Sesuai'
        mismatch = client.post('/api/auth/register', json=mismatched_name)
        assert mismatch.status_code == 422
        assert 'Nama harus sesuai' in mismatch.text

        registration = client.post('/api/auth/register', json=_registration_payload(nim, code))
        assert registration.status_code == 201, registration.text
        assert registration.json()['role'] == 'mahasiswa'

        repeated = client.post('/api/auth/register', json=_registration_payload(nim, code))
        assert repeated.status_code == 409

        db = SessionLocal()
        roster = db.query(StudentRosterEntry).filter(StudentRosterEntry.nim == nim).one()
        student = db.query(User).filter(User.nim == nim).one()
        assert roster.registered_user_id == student.id
        assert roster.registered_at is not None
        assert roster.registration_code_hash is None
        assert roster.registration_code_expires_at is None
        db.close()

        summary_after = client.get('/api/admin/student-roster', headers=admin_headers)
        assert summary_after.status_code == 200
        assert summary_after.json()['registered'] >= 1
    finally:
        db = SessionLocal()
        roster = db.query(StudentRosterEntry).filter(StudentRosterEntry.nim == nim).first()
        user = db.query(User).filter(User.nim == nim).first()
        if roster:
            db.delete(roster)
        if user:
            db.query(AuditLog).filter(AuditLog.actor_id == user.id).delete(synchronize_session=False)
            db.delete(user)
        if admin_id is not None:
            db.query(AuditLog).filter(
                AuditLog.actor_id == admin_id,
                AuditLog.entity_type == 'student_roster',
                AuditLog.entity_id == 'batch',
            ).delete(synchronize_session=False)
        db.commit()
        db.close()
        client.close()
        settings.require_student_roster = old_setting


def test_student_roster_import_rejects_duplicate_nim_atomically():
    old_setting = settings.require_student_roster
    settings.require_student_roster = True
    nim = f'DUPROSTER{uuid4().hex[:8]}'
    client = TestClient(app)
    admin_id = None
    try:
        headers = _login_admin(client)
        db = SessionLocal()
        admin_id = db.query(User.id).filter(User.nim == 'admin').scalar()
        db.close()

        roster_csv = StringIO(newline='')
        writer = csv.writer(roster_csv)
        writer.writerow(['NIM', 'Nama Lengkap', 'Program Studi', 'Angkatan'])
        writer.writerow([nim, 'Mahasiswa Duplikat', 'STI', '2022'])
        writer.writerow([nim, 'Mahasiswa Duplikat', 'STI', '2022'])
        response = client.post(
            '/api/admin/student-roster/import',
            headers=headers,
            files={'file': ('duplikat.csv', roster_csv.getvalue().encode('utf-8'), 'text/csv')},
        )
        assert response.status_code == 422
        db = SessionLocal()
        assert db.query(StudentRosterEntry).filter(StudentRosterEntry.nim == nim).count() == 0
        db.close()
    finally:
        db = SessionLocal()
        db.query(StudentRosterEntry).filter(StudentRosterEntry.nim == nim).delete(synchronize_session=False)
        db.query(User).filter(User.nim == nim).delete(synchronize_session=False)
        if admin_id is not None:
            db.query(AuditLog).filter(
                AuditLog.actor_id == admin_id,
                AuditLog.entity_type == 'student_roster',
                AuditLog.entity_id == 'batch',
            ).delete(synchronize_session=False)
        db.commit()
        db.close()
        client.close()
        settings.require_student_roster = old_setting

def test_admin_can_import_one_hundred_official_roster_entries_and_generate_one_time_codes():
    old_setting = settings.require_student_roster
    settings.require_student_roster = True
    batch = uuid4().hex[:8].upper()
    nims = [f'ROSTER{batch}{index:03d}' for index in range(100)]
    client = TestClient(app)
    admin_id = None
    try:
        headers = _login_admin(client)
        db = SessionLocal()
        admin_id = db.query(User.id).filter(User.nim == 'admin').scalar()
        db.close()

        roster_csv = StringIO(newline='')
        writer = csv.writer(roster_csv)
        writer.writerow(['NIM', 'Nama Lengkap', 'Program Studi', 'Angkatan'])
        for index, nim in enumerate(nims, start=1):
            writer.writerow([
                nim,
                f'Mahasiswa Roster Uji {index:03d}',
                'Sistem dan Teknologi Informasi',
                '2022',
            ])

        imported = client.post(
            '/api/admin/student-roster/import',
            headers=headers,
            files={'file': ('roster-100.csv', roster_csv.getvalue().encode('utf-8'), 'text/csv')},
        )
        assert imported.status_code == 200, imported.text
        payload = imported.json()
        assert payload['imported'] == 100
        assert payload['created'] == 100
        assert payload['registered'] == 0
        assert payload['waiting'] == 100

        summary = client.get('/api/admin/student-roster', headers=headers)
        assert summary.status_code == 200
        assert summary.json()['total'] == 100
        assert summary.json()['registered'] == 0
        assert summary.json()['waiting'] == 100
        assert summary.json()['target_reached'] is True

        invitations = client.post('/api/admin/student-roster/invitations.csv', headers=headers)
        assert invitations.status_code == 200
        invite_rows = list(csv.DictReader(StringIO(invitations.content.decode('utf-8-sig'))))
        assert len(invite_rows) == 100
        assert {row['NIM'] for row in invite_rows} == set(nims)
        assert all(len(row['Kode Pendaftaran']) >= 24 for row in invite_rows)

        db = SessionLocal()
        roster_rows = db.query(StudentRosterEntry).filter(StudentRosterEntry.nim.in_(nims)).all()
        assert len(roster_rows) == 100
        assert all(row.registration_code_hash for row in roster_rows)
        assert all(row.registered_user_id is None for row in roster_rows)
        assert all(row.registration_code_hash not in {item['Kode Pendaftaran'] for item in invite_rows} for row in roster_rows)
        db.close()
    finally:
        db = SessionLocal()
        db.query(StudentRosterEntry).filter(StudentRosterEntry.nim.in_(nims)).delete(synchronize_session=False)
        if admin_id is not None:
            db.query(AuditLog).filter(
                AuditLog.actor_id == admin_id,
                AuditLog.entity_type == 'student_roster',
                AuditLog.entity_id == 'batch',
            ).delete(synchronize_session=False)
        db.commit()
        db.close()
        client.close()
        settings.require_student_roster = old_setting

