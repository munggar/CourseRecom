from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal, ensure_schema
from app.deps import create_access_token, get_password_hash
from app.main import app
from app.models import User


client = TestClient(app)


def test_admin_can_read_advisor_assignment_history_without_raw_audit_ids():
    ensure_schema()
    db = SessionLocal()
    db.execute(text('PRAGMA foreign_keys=OFF'))
    db.query(User).filter(User.nim.like('ADHIST-%')).delete(synchronize_session=False)
    db.commit()
    admin = User(nim='ADHIST-ADMIN', username='adhist-admin', full_name='Admin Riwayat', role='admin',
                 password_hash=get_password_hash('password-test'))
    old_advisor = User(nim='ADHIST-OLD', username='adhist-old', full_name='Dosen Lama', role='dosen',
                       password_hash=get_password_hash('password-test'))
    new_advisor = User(nim='ADHIST-NEW', username='adhist-new', full_name='Dosen Baru', role='dosen',
                       password_hash=get_password_hash('password-test'))
    student = User(nim='ADHIST-STUDENT', username='adhist-student', full_name='Mahasiswa Riwayat', role='mahasiswa',
                   password_hash=get_password_hash('password-test'))
    db.add_all([admin, old_advisor, new_advisor, student])
    db.commit()
    db.refresh(student)
    student.advisor_id = old_advisor.id
    db.commit()

    admin_token = create_access_token(admin.nim, admin.role, admin.token_version)
    old_token = create_access_token(old_advisor.nim, old_advisor.role, old_advisor.token_version)
    student_token = create_access_token(student.nim, student.role, student.token_version)
    admin_nim = admin.nim
    student_nim = student.nim
    old_advisor_nim = old_advisor.nim
    new_advisor_nim = new_advisor.nim
    db.close()

    assignment = client.patch(
        f'/api/admin/students/{student_nim}/advisor',
        headers={'Authorization': f'Bearer {admin_token}'},
        json={'advisor_nim': new_advisor_nim, 'reason': 'Pergantian pembimbing akademik'},
    )
    assert assignment.status_code == 200

    history = client.get('/api/admin/advisor-history', headers={'Authorization': f'Bearer {admin_token}'})
    assert history.status_code == 200
    item = next(entry for entry in history.json() if entry['student_nim'] == student_nim)
    assert item['previous_advisor_nim'] == old_advisor_nim
    assert item['advisor_nim'] == new_advisor_nim
    assert item['admin_name'] == admin.full_name
    assert item['reason'] == 'Pergantian pembimbing akademik'
    assert item['changed_at']

    assert client.get('/api/admin/advisor-history', headers={'Authorization': f'Bearer {old_token}'}).status_code == 403
    assert client.get('/api/admin/advisor-history', headers={'Authorization': f'Bearer {student_token}'}).status_code == 403

    db = SessionLocal()
    db.execute(text('PRAGMA foreign_keys=OFF'))
    db.query(User).filter(User.nim.like('ADHIST-%')).delete(synchronize_session=False)
    db.commit()
    db.close()
