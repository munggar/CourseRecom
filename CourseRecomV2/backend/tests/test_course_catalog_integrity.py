from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import create_access_token, get_password_hash
from app.main import app
from app.models import AuditLog, Course, StudentRecord, StudyPlan, User


def test_course_code_rename_is_blocked_while_history_or_prerequisites_reference_it():
    suffix = uuid4().hex[:8].upper()
    old_code = 'RN' + suffix
    new_code = 'NW' + suffix
    prerequisite_code = 'RQ' + suffix
    student_nim = 'RS' + suffix
    db = SessionLocal()
    student = User(
        nim=student_nim,
        full_name='Mahasiswa Histori',
        role='mahasiswa',
        password_hash=get_password_hash('student-password'),
    )
    course = Course(
        code=old_code,
        name='Mata Kuliah Histori',
        sks=3,
        semester=3,
        available_semesters='3',
        category='Wajib',
        capacity=40,
        is_active=True,
    )
    dependent_course = Course(
        code=prerequisite_code,
        name='Mata Kuliah Prasyarat',
        sks=3,
        semester=4,
        available_semesters='4',
        category='Wajib',
        prerequisite_codes=old_code,
        capacity=40,
        is_active=True,
    )
    db.add_all([student, course, dependent_course])
    db.flush()
    db.add(StudentRecord(
        student_id=student.id,
        course_code=old_code,
        course_name=course.name,
        grade='A',
        semester=2,
    ))
    course_id = course.id
    student_id = student.id
    db.commit()
    db.close()

    client = TestClient(app)
    headers = {
        'Authorization': 'Bearer ' + create_access_token('admin', 'admin'),
    }
    payload = {
        'code': new_code,
        'name': 'Mata Kuliah Histori',
        'sks': 3,
        'semester': 3,
        'available_semesters': '3',
        'category': 'Wajib',
        'prerequisite_codes': '',
        'capacity': 40,
        'is_active': True,
    }
    try:
        blocked = client.put(f'/api/admin/courses/{old_code}', headers=headers, json=payload)
        assert blocked.status_code == 409

        db = SessionLocal()
        db.query(StudentRecord).filter(StudentRecord.student_id == student_id).delete(
            synchronize_session=False,
        )
        db.query(Course).filter(Course.code == prerequisite_code).delete(
            synchronize_session=False,
        )
        db.commit()
        db.close()

        renamed = client.put(f'/api/admin/courses/{old_code}', headers=headers, json=payload)
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()['code'] == new_code
    finally:
        db = SessionLocal()
        db.query(StudentRecord).filter(StudentRecord.student_id == student_id).delete(
            synchronize_session=False,
        )
        db.query(AuditLog).filter(AuditLog.actor_id == student_id).delete(
            synchronize_session=False,
        )
        db.query(User).filter(User.id == student_id).delete(synchronize_session=False)
        db.query(Course).filter(Course.id == course_id).delete(synchronize_session=False)
        db.query(Course).filter(Course.code == prerequisite_code).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_course_capacity_cannot_be_lowered_below_existing_krs_reservations():
    suffix = uuid4().hex[:8].upper()
    code = 'CP' + suffix
    students = [
        User(
            nim=f'CU{suffix}{number}',
            full_name=f'Mahasiswa Kapasitas {number}',
            role='mahasiswa',
            password_hash=get_password_hash('student-password'),
        )
        for number in (1, 2)
    ]
    course = Course(
        code=code,
        name='Mata Kuliah Kapasitas',
        sks=3,
        semester=3,
        available_semesters='3',
        category='Wajib',
        capacity=20,
        is_active=True,
    )
    db = SessionLocal()
    db.add_all([*students, course])
    db.flush()
    now = datetime.now()
    db.add_all([
        StudyPlan(
            student_id=student.id,
            semester=3,
            courses_json=f'[{{"code":"{code}","name":"Mata Kuliah Kapasitas","sks":3}}]',
            status='pending',
            advisor_note='',
            created_at=now,
            updated_at=now,
        )
        for student in students
    ])
    student_ids = [student.id for student in students]
    db.commit()
    db.close()

    client = TestClient(app)
    headers = {
        'Authorization': 'Bearer ' + create_access_token('admin', 'admin'),
    }
    payload = {
        'code': code,
        'name': 'Mata Kuliah Kapasitas',
        'sks': 3,
        'semester': 3,
        'available_semesters': '3',
        'category': 'Wajib',
        'prerequisite_codes': '',
        'capacity': 1,
        'is_active': True,
    }
    try:
        rejected = client.put(f'/api/admin/courses/{code}', headers=headers, json=payload)
        assert rejected.status_code == 409
        assert '2 kursi yang sudah terpakai' in rejected.json()['detail']

        payload['capacity'] = 2
        updated = client.put(f'/api/admin/courses/{code}', headers=headers, json=payload)
        assert updated.status_code == 200, updated.text
    finally:
        db = SessionLocal()
        db.query(StudyPlan).filter(StudyPlan.student_id.in_(student_ids)).delete(
            synchronize_session=False,
        )
        db.query(AuditLog).filter(
            AuditLog.entity_type == 'course',
            AuditLog.entity_id == code,
        ).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(student_ids)).delete(synchronize_session=False)
        db.query(Course).filter(Course.code == code).delete(synchronize_session=False)
        db.commit()
        db.close()
