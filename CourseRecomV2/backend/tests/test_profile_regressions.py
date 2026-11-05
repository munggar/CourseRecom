from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal, ensure_schema
from app.deps import create_access_token, get_password_hash
from app.main import app
from app.models import Course, StudentRecord, User


client = TestClient(app)


def _new_student(db, prefix: str) -> User:
    suffix = uuid4().hex[:12]
    student = User(
        nim=f'{prefix}{suffix}',
        full_name='Mahasiswa Uji Profil',
        role='mahasiswa',
        password_hash=get_password_hash('test-password'),
        interests='Kecerdasan Bisnis',
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def test_profile_not_taken_codes_use_only_active_database_catalog():
    ensure_schema()
    db = SessionLocal()
    student = _new_student(db, 'PRFCAT')
    previous_course_states = {
        course.id: course.is_active for course in db.query(Course).all()
    }
    active_available = Course(
        code='DBCAT9001', name='Mata Kuliah Aktif Belum Diambil',
        sks=3, semester=1, category='Data', is_active=True,
    )
    active_taken = Course(
        code='DBCAT9002', name='Mata Kuliah Aktif Sudah Diambil',
        sks=3, semester=1, category='Data', is_active=True,
    )
    inactive_course = Course(
        code='DBCAT9003', name='Mata Kuliah Tidak Aktif',
        sks=3, semester=1, category='Data', is_active=False,
    )
    db.query(Course).update({'is_active': False}, synchronize_session=False)
    db.add_all([active_available, active_taken, inactive_course])
    db.commit()
    db.add(StudentRecord(
        student_id=student.id,
        course_code=active_taken.code,
        course_name=active_taken.name,
        grade='B',
        semester=1,
        sks=3,
    ))
    db.commit()

    token = create_access_token(student.nim, 'mahasiswa')
    try:
        response = client.get(
            '/api/mahasiswa/profil',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 200
        assert response.json()['not_taken_course_codes'] == ['DBCAT9001']
    finally:
        db.query(StudentRecord).filter(StudentRecord.student_id == student.id).delete()
        db.query(Course).filter(Course.code.in_(['DBCAT9001', 'DBCAT9002', 'DBCAT9003'])).delete()
        db.query(User).filter(User.id == student.id).delete()
        for course_id, is_active in previous_course_states.items():
            db.query(Course).filter(Course.id == course_id).update(
                {'is_active': is_active}, synchronize_session=False,
            )
        db.commit()
        db.close()


def test_profile_update_rejects_empty_and_overlong_interests():
    ensure_schema()
    db = SessionLocal()
    student = _new_student(db, 'PRFVAL')
    student_nim = student.nim
    student_id = student.id
    db.close()

    token = create_access_token(student_nim, 'mahasiswa')
    headers = {'Authorization': f'Bearer {token}'}
    try:
        for invalid_value in ('', '   ', 'Pilihan A,Pilihan B', 'x' * 256, 'x' * 300):
            response = client.put(
                '/api/mahasiswa/profil',
                headers=headers,
                json={'interests': invalid_value},
            )
            assert response.status_code == 422

        valid_value = 'x' * 255
        response = client.put(
            '/api/mahasiswa/profil',
            headers=headers,
            json={'interests': valid_value},
        )
        assert response.status_code == 200
        assert response.json()['interests'] == valid_value
    finally:
        cleanup_db = SessionLocal()
        cleanup_db.query(User).filter(User.id == student_id).delete()
        cleanup_db.commit()
        cleanup_db.close()
