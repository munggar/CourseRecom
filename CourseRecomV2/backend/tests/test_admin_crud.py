from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import create_access_token
from app.main import app
from app.models import AuditLog, Course, User


client = TestClient(app)
ADMIN_HEADERS = {
    'Authorization': 'Bearer ' + create_access_token('admin', 'admin'),
}


def test_admin_course_create_read_update_deactivate_and_reactivate_cycle():
    code = f'CR{uuid4().hex[:10]}'.upper()
    payload = {
        'code': code,
        'name': 'Mata Kuliah CRUD Uji',
        'sks': 3,
        'semester': 4,
        'available_semesters': '4,6',
        'category': 'Pilihan',
        'description': 'Data untuk pengujian CRUD.',
        'prerequisite_text': '',
        'prerequisite_codes': '',
        'day': 'Senin',
        'time': '08:00-10:00',
        'capacity': 40,
    }
    try:
        created = client.post('/api/admin/courses', headers=ADMIN_HEADERS, json=payload)
        assert created.status_code == 201, created.text
        assert created.json()['code'] == code

        listed = client.get('/api/admin/courses', headers=ADMIN_HEADERS)
        assert listed.status_code == 200
        assert any(item['code'] == code for item in listed.json())

        updated_payload = {**payload, 'name': 'Mata Kuliah CRUD Diperbarui', 'capacity': 55}
        updated = client.put(
            f'/api/admin/courses/{code}',
            headers=ADMIN_HEADERS,
            json=updated_payload,
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()['name'] == 'Mata Kuliah CRUD Diperbarui'
        assert updated.json()['capacity'] == 55

        db = SessionLocal()
        stored = db.query(Course).filter(Course.code == code).one()
        assert stored.name == 'Mata Kuliah CRUD Diperbarui'
        assert stored.capacity == 55
        db.close()

        deactivated = client.delete(f'/api/admin/courses/{code}', headers=ADMIN_HEADERS)
        assert deactivated.status_code == 204
        listed_after_delete = client.get('/api/admin/courses', headers=ADMIN_HEADERS)
        assert all(item['code'] != code for item in listed_after_delete.json())

        db = SessionLocal()
        stored = db.query(Course).filter(Course.code == code).one()
        assert stored.is_active is False
        db.close()

        reactivated = client.post('/api/admin/courses', headers=ADMIN_HEADERS, json=updated_payload)
        assert reactivated.status_code == 201, reactivated.text
        visible_again = client.get('/api/admin/courses', headers=ADMIN_HEADERS)
        assert any(item['code'] == code for item in visible_again.json())

        db = SessionLocal()
        actions = {
            item.action for item in db.query(AuditLog).filter(
                AuditLog.entity_type == 'course',
                AuditLog.entity_id == code,
            ).all()
        }
        assert 'course_saved' in actions
        assert 'course_deactivated' in actions
        db.close()
    finally:
        db = SessionLocal()
        db.query(AuditLog).filter(
            AuditLog.entity_type == 'course',
            AuditLog.entity_id == code,
        ).delete(synchronize_session=False)
        db.query(Course).filter(Course.code == code).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_admin_lecturer_create_read_update_and_delete_cycle():
    suffix = uuid4().hex[:10]
    nip = f'DOS{suffix}'.upper()
    username = f'lecturer-{suffix}'
    email = f'{username}@example.test'
    try:
        created = client.post('/api/admin/lecturers', headers=ADMIN_HEADERS, json={
            'nip': nip,
            'full_name': 'Dosen CRUD Awal',
            'username': username,
            'email': email,
            'password': 'password-uji-123',
        })
        assert created.status_code == 201, created.text
        assert created.json()['role'] == 'dosen'

        listed = client.get('/api/admin/lecturers', headers=ADMIN_HEADERS)
        assert listed.status_code == 200
        assert any(item['nim'] == nip for item in listed.json())

        updated = client.put(f'/api/admin/lecturers/{nip}', headers=ADMIN_HEADERS, json={
            'full_name': 'Dosen CRUD Diperbarui',
            'username': username,
            'email': email,
        })
        assert updated.status_code == 200, updated.text
        assert updated.json()['full_name'] == 'Dosen CRUD Diperbarui'

        db = SessionLocal()
        stored = db.query(User).filter(User.nim == nip, User.role == 'dosen').one()
        assert stored.full_name == 'Dosen CRUD Diperbarui'
        stored_id = stored.id
        db.close()

        deleted = client.delete(f'/api/admin/lecturers/{nip}', headers=ADMIN_HEADERS)
        assert deleted.status_code == 204
        listed_after_delete = client.get('/api/admin/lecturers', headers=ADMIN_HEADERS)
        assert all(item['nim'] != nip for item in listed_after_delete.json())

        db = SessionLocal()
        assert db.query(User).filter(User.id == stored_id).first() is None
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == 'user',
            AuditLog.entity_id == str(stored_id),
            AuditLog.action.in_(('lecturer_created', 'lecturer_updated', 'lecturer_deleted')),
        ).count() >= 3
        db.close()
    finally:
        db = SessionLocal()
        lecturer = db.query(User).filter(User.nim == nip).first()
        if lecturer:
            db.delete(lecturer)
        db.query(AuditLog).filter(
            AuditLog.entity_type == 'user',
            AuditLog.action.in_(('lecturer_created', 'lecturer_updated', 'lecturer_deleted')),
            AuditLog.new_value.like(f'%{nip}%'),
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_admin_course_crud_is_forbidden_to_student():
    student_headers = {
        'Authorization': 'Bearer ' + create_access_token('2203001', 'mahasiswa'),
    }
    response = client.post('/api/admin/courses', headers=student_headers, json={
        'code': f'NO{uuid4().hex[:8]}'.upper(),
        'name': 'Tidak boleh dibuat mahasiswa',
        'sks': 3,
        'semester': 1,
        'available_semesters': '1',
        'category': 'Wajib',
        'capacity': 40,
    })
    assert response.status_code == 403
