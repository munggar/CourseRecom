import csv
from io import BytesIO, StringIO
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook

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


def _roster_csv(rows: list[list[str]]) -> bytes:
    output = StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['NIM', 'Nama Lengkap', 'Program Studi', 'Angkatan'])
    writer.writerows(rows)
    return output.getvalue().encode('utf-8')


def _cleanup(nims: list[str], admin_id: int | None) -> None:
    db = SessionLocal()
    try:
        db.query(StudentRosterEntry).filter(StudentRosterEntry.nim.in_(nims)).delete(synchronize_session=False)
        student_ids = [
            row[0] for row in db.query(User.id).filter(User.nim.in_(nims)).all()
        ]
        if student_ids:
            db.query(AuditLog).filter(AuditLog.actor_id.in_(student_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(student_ids)).delete(synchronize_session=False)
        if admin_id is not None:
            db.query(AuditLog).filter(
                AuditLog.actor_id == admin_id,
                AuditLog.entity_type == 'student_roster',
                AuditLog.entity_id == 'batch',
            ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_admin_import_creates_student_account_and_disables_public_registration():
    nim = f'ROSTER{uuid4().hex[:10]}'
    client = TestClient(app)
    admin_id = None
    try:
        headers = _login_admin(client)
        db = SessionLocal()
        admin_id = db.query(User.id).filter(User.nim == 'admin').scalar()
        db.close()

        disabled_registration = client.post(
            '/api/auth/register',
            json={
                'nim': nim,
                'full_name': 'Mahasiswa Roster Uji',
                'program_study': 'Sistem dan Teknologi Informasi',
                'interests': 'Manajemen Teknologi Informasi',
                'angkatan': '2022',
                'password': 'password-roster-123',
            },
        )
        assert disabled_registration.status_code == 403
        assert 'diimpor roster' in disabled_registration.text

        imported = client.post(
            '/api/admin/student-roster/import',
            headers=headers,
            files={
                'file': (
                    'roster.csv',
                    _roster_csv([[nim, 'Mahasiswa Roster Uji', 'Sistem dan Teknologi Informasi', '2022']]),
                    'text/csv',
                )
            },
        )
        assert imported.status_code == 200, imported.text
        result = imported.json()
        assert result['imported'] == 1
        assert result['created_accounts'] == 1
        assert result['already_registered'] == 0
        assert result['registered'] >= 1
        assert result['waiting'] == 0
        assert len(result['credentials']) == 1

        credential = result['credentials'][0]
        assert credential['nim'] == nim
        assert credential['username'] == nim
        assert len(credential['temporary_password']) >= 12

        student_login = client.post(
            '/api/auth/login',
            json={
                'username': credential['username'],
                'password': credential['temporary_password'],
                'role': 'mahasiswa',
            },
        )
        assert student_login.status_code == 200, student_login.text

        summary = client.get('/api/admin/student-roster', headers=headers)
        assert summary.status_code == 200
        assert summary.json()['registered'] >= 1
        assert summary.json()['waiting'] == 0

        db = SessionLocal()
        roster = db.query(StudentRosterEntry).filter(StudentRosterEntry.nim == nim).one()
        student = db.query(User).filter(User.nim == nim).one()
        assert roster.registered_user_id == student.id
        assert roster.registered_at is not None
        assert roster.registration_code_hash is None
        assert roster.registration_code_expires_at is None
        assert student.role == 'mahasiswa'
        assert student.password_hash != credential['temporary_password']
        db.close()

        repeated_import = client.post(
            '/api/admin/student-roster/import',
            headers=headers,
            files={
                'file': (
                    'roster.csv',
                    _roster_csv([[nim, 'Mahasiswa Roster Uji', 'Sistem dan Teknologi Informasi', '2022']]),
                    'text/csv',
                )
            },
        )
        assert repeated_import.status_code == 200, repeated_import.text
        assert repeated_import.json()['created_accounts'] == 0
        assert repeated_import.json()['already_registered'] == 1
        assert repeated_import.json()['credentials'] == []

        still_valid = client.post(
            '/api/auth/login',
            json={
                'username': credential['username'],
                'password': credential['temporary_password'],
                'role': 'mahasiswa',
            },
        )
        assert still_valid.status_code == 200, still_valid.text

        retired_invitation_endpoint = client.post(
            '/api/admin/student-roster/invitations.csv',
            headers=headers,
        )
        assert retired_invitation_endpoint.status_code == 410
    finally:
        _cleanup([nim], admin_id)
        client.close()


def test_student_roster_excel_import_creates_accounts():
    nim = f'XLSX{uuid4().hex[:12]}'
    client = TestClient(app)
    admin_id = None
    try:
        headers = _login_admin(client)
        db = SessionLocal()
        admin_id = db.query(User.id).filter(User.nim == 'admin').scalar()
        db.close()

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = 'Data Mahasiswa'
        worksheet.append(['NIM', 'Nama Lengkap', 'Program Studi', 'Angkatan'])
        worksheet.append([nim, 'Mahasiswa Excel Uji', 'STI', '2022'])
        worksheet['A2'].number_format = '@'
        buffer = BytesIO()
        workbook.save(buffer)

        imported = client.post(
            '/api/admin/student-roster/import',
            headers=headers,
            files={
                'file': (
                    'roster-mahasiswa.xlsx',
                    buffer.getvalue(),
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                )
            },
        )
        assert imported.status_code == 200, imported.text
        payload = imported.json()
        assert payload['imported'] == 1
        assert payload['created_accounts'] == 1
        assert payload['registered'] >= 1
        assert payload['waiting'] == 0
        assert payload['credentials'][0]['nim'] == nim

        template = client.get('/api/admin/student-roster/template.xlsx', headers=headers)
        assert template.status_code == 200
        assert template.headers['content-type'].startswith(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        assert template.content[:2] == b'PK'
    finally:
        _cleanup([nim], admin_id)
        client.close()


def test_student_roster_import_rejects_duplicate_nim_atomically():
    nim = f'DUPROSTER{uuid4().hex[:8]}'
    client = TestClient(app)
    admin_id = None
    try:
        headers = _login_admin(client)
        db = SessionLocal()
        admin_id = db.query(User.id).filter(User.nim == 'admin').scalar()
        db.close()

        response = client.post(
            '/api/admin/student-roster/import',
            headers=headers,
            files={
                'file': (
                    'duplikat.csv',
                    _roster_csv([
                        [nim, 'Mahasiswa Duplikat', 'STI', '2022'],
                        [nim, 'Mahasiswa Duplikat', 'STI', '2022'],
                    ]),
                    'text/csv',
                )
            },
        )
        assert response.status_code == 422
        db = SessionLocal()
        assert db.query(StudentRosterEntry).filter(StudentRosterEntry.nim == nim).count() == 0
        assert db.query(User).filter(User.nim == nim).count() == 0
        db.close()
    finally:
        _cleanup([nim], admin_id)
        client.close()


def test_admin_can_import_one_hundred_student_accounts_in_one_batch():
    batch = uuid4().hex[:8].upper()
    nims = [f'ROSTER{batch}{index:03d}' for index in range(100)]
    rows = [
        [nim, f'Mahasiswa Roster Uji {index:03d}', 'Sistem dan Teknologi Informasi', '2022']
        for index, nim in enumerate(nims, start=1)
    ]
    client = TestClient(app)
    admin_id = None
    try:
        headers = _login_admin(client)
        db = SessionLocal()
        admin_id = db.query(User.id).filter(User.nim == 'admin').scalar()
        db.close()

        imported = client.post(
            '/api/admin/student-roster/import',
            headers=headers,
            files={'file': ('roster-100.csv', _roster_csv(rows), 'text/csv')},
        )
        assert imported.status_code == 200, imported.text
        payload = imported.json()
        assert payload['imported'] == 100
        assert payload['created'] == 100
        assert payload['created_accounts'] == 100
        assert payload['already_registered'] == 0
        assert payload['registered'] >= 100
        assert payload['waiting'] == 0
        assert len(payload['credentials']) == 100
        assert {item['nim'] for item in payload['credentials']} == set(nims)
        assert len({item['temporary_password'] for item in payload['credentials']}) == 100

        summary = client.get('/api/admin/student-roster', headers=headers)
        assert summary.status_code == 200
        assert summary.json()['registered'] >= 100
        assert summary.json()['waiting'] == 0
        assert summary.json()['target_reached'] is True

        db = SessionLocal()
        roster_rows = db.query(StudentRosterEntry).filter(StudentRosterEntry.nim.in_(nims)).all()
        student_rows = db.query(User).filter(User.nim.in_(nims)).all()
        assert len(roster_rows) == 100
        assert len(student_rows) == 100
        assert all(row.registered_user_id is not None for row in roster_rows)
        assert all(row.registration_code_hash is None for row in roster_rows)
        assert {row.id for row in student_rows} == {row.registered_user_id for row in roster_rows}
        assert all(row.role == 'mahasiswa' for row in student_rows)
        db.close()
    finally:
        _cleanup(nims, admin_id)
        client.close()
