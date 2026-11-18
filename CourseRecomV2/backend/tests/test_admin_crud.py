from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import create_access_token
from app.main import app
from app.models import AdvisorCourseFeedback, AuditLog, Course, CourseClass, KprsRequest, StudyPlan, User


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
    stored_id = None
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
            stored_id = lecturer.id
            db.delete(lecturer)
        if stored_id is not None:
            db.query(AuditLog).filter(
                AuditLog.entity_type == 'user',
                AuditLog.entity_id == str(stored_id),
                AuditLog.action.in_(('lecturer_created', 'lecturer_updated', 'lecturer_deleted')),
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


def test_admin_delete_lecturer_preserves_review_history_and_nulls_foreign_keys():
    ensure = SessionLocal()
    suffix = uuid4().hex[:10].upper()
    lecturer_nim = f'DEL{suffix}'
    student_nim = f'DELM{suffix}'
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    lecturer = User(
        nim=lecturer_nim,
        username=f'del-{suffix.lower()}',
        full_name='Dosen yang Akan Dihapus',
        role='dosen',
        password_hash='unused-hash',
    )
    student = User(
        nim=student_nim,
        username=f'delm-{suffix.lower()}',
        full_name='Mahasiswa Uji Penghapusan Dosen',
        role='mahasiswa',
        password_hash='unused-hash',
    )
    ensure.add_all([lecturer, student])
    ensure.commit()
    ensure.refresh(lecturer)
    ensure.refresh(student)
    student.advisor_id = lecturer.id
    plan = StudyPlan(
        student_id=student.id,
        semester=2,
        courses_json='[]',
        status='approved',
        advisor_note='Disetujui',
        reviewer_id=lecturer.id,
        created_at=now,
        updated_at=now,
    )
    ensure.add(plan)
    ensure.commit()
    ensure.refresh(plan)
    request = KprsRequest(
        student_id=student.id,
        study_plan_id=plan.id,
        reviewer_id=lecturer.id,
        before_json='[]',
        after_json='[]',
        reason='Perubahan jadwal kuliah',
        status='approved',
        reviewer_note='Disetujui dosen PA',
        created_at=now,
        updated_at=now,
    )
    feedback = AdvisorCourseFeedback(
        student_id=student.id,
        study_plan_id=plan.id,
        reviewer_id=lecturer.id,
        semester=2,
        course_code='DEL101',
        reason='Tinjau kembali mata kuliah pilihan ini.',
        created_at=now,
    )
    course_class = CourseClass(
        course_code='DEL101',
        class_name='A',
        lecturer_id=lecturer.id,
        room='R.101',
        day='Senin',
        start_time='08:00',
        end_time='10:00',
        capacity=30,
        semester='2026/2027 Genap',
        is_open=True,
    )
    audit = AuditLog(
        actor_id=lecturer.id,
        actor_name=lecturer.full_name,
        action='review_test',
        entity_type='study_plan',
        entity_id=str(plan.id),
        old_value='{}',
        new_value='{}',
        created_at=now,
    )
    ensure.add_all([request, feedback, course_class, audit])
    ensure.commit()
    lecturer_id, student_id, plan_id, request_id = lecturer.id, student.id, plan.id, request.id
    feedback_id, class_id, audit_id = feedback.id, course_class.id, audit.id
    ensure.close()

    try:
        response = client.delete(
            f'/api/admin/lecturers/{lecturer_nim}',
            headers=ADMIN_HEADERS,
        )
        assert response.status_code == 204, response.text
        db = SessionLocal()
        assert db.query(User).filter(User.id == lecturer_id).first() is None
        assert db.query(User).filter(User.id == student_id).one().advisor_id is None
        assert db.query(StudyPlan).filter(StudyPlan.id == plan_id).one().reviewer_id is None
        assert db.query(KprsRequest).filter(KprsRequest.id == request_id).one().reviewer_id is None
        assert db.query(AdvisorCourseFeedback).filter(AdvisorCourseFeedback.id == feedback_id).one().reviewer_id is None
        assert db.query(CourseClass).filter(CourseClass.id == class_id).one().lecturer_id is None
        retained_audit = db.query(AuditLog).filter(AuditLog.id == audit_id).one()
        assert retained_audit.actor_id is None
        assert retained_audit.actor_name == 'Dosen yang Akan Dihapus'
        db.close()
    finally:
        db = SessionLocal()
        db.query(KprsRequest).filter(KprsRequest.student_id == student_id).delete(synchronize_session=False)
        db.query(AdvisorCourseFeedback).filter(AdvisorCourseFeedback.student_id == student_id).delete(synchronize_session=False)
        db.query(StudyPlan).filter(StudyPlan.id == plan_id).delete(synchronize_session=False)
        db.query(CourseClass).filter(CourseClass.id == class_id).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.id == audit_id).delete(synchronize_session=False)
        db.query(AuditLog).filter(
            AuditLog.entity_type == 'user',
            AuditLog.entity_id == str(lecturer_id),
            AuditLog.action == 'lecturer_deleted',
        ).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_([student_id, lecturer_id])).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_admin_cannot_change_or_close_parallel_class_with_active_krs_reservations():
    suffix = uuid4().hex[:10].upper()
    code = f'LOCK{suffix}'
    student_nim = f'LOCKM{suffix}'
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    student = User(
        nim=student_nim,
        username=f'lock-{suffix.lower()}',
        full_name='Mahasiswa dengan KRS aktif',
        role='mahasiswa',
        password_hash='unused-hash',
    )
    course = Course(
        code=code,
        name='Mata Kuliah Kelas Terkunci',
        sks=3,
        semester=1,
        available_semesters='1',
        category='Pilihan',
        capacity=20,
        is_active=True,
    )
    db.add_all([student, course])
    db.flush()
    section = CourseClass(
        course_code=code,
        class_name='A',
        room='R.101',
        day='Senin',
        start_time='08:00',
        end_time='10:00',
        capacity=5,
        semester='1',
        is_open=True,
    )
    db.add(section)
    db.flush()
    plan = StudyPlan(
        student_id=student.id,
        semester=1,
        courses_json=json.dumps([{
            'code': code,
            'name': course.name,
            'sks': 3,
            'class_id': section.id,
            'class_name': section.class_name,
            'room': section.room,
            'day': section.day,
            'start_time': section.start_time,
            'end_time': section.end_time,
        }]),
        status='approved',
        advisor_note='',
        created_at=now,
        updated_at=now,
    )
    db.add(plan)
    db.commit()
    class_id, plan_id, student_id = section.id, plan.id, student.id
    db.close()

    base_payload = {
        'course_code': code,
        'class_name': 'A',
        'lecturer_id': None,
        'room': 'R.101',
        'day': 'Senin',
        'start_time': '08:00',
        'end_time': '10:00',
        'capacity': 5,
        'semester': '1',
        'is_open': True,
    }
    try:
        changed_schedule = client.put(
            f'/api/admin/classes/{class_id}',
            headers=ADMIN_HEADERS,
            json={**base_payload, 'room': 'R.202', 'day': 'Selasa'},
        )
        assert changed_schedule.status_code == 409, changed_schedule.text
        assert 'dikunci' in changed_schedule.json()['detail']

        close_through_update = client.put(
            f'/api/admin/classes/{class_id}',
            headers=ADMIN_HEADERS,
            json={**base_payload, 'is_open': False},
        )
        assert close_through_update.status_code == 409, close_through_update.text

        close_through_endpoint = client.delete(
            f'/api/admin/classes/{class_id}',
            headers=ADMIN_HEADERS,
        )
        assert close_through_endpoint.status_code == 409, close_through_endpoint.text

        increase_capacity = client.put(
            f'/api/admin/classes/{class_id}',
            headers=ADMIN_HEADERS,
            json={**base_payload, 'capacity': 8},
        )
        assert increase_capacity.status_code == 200, increase_capacity.text
        assert increase_capacity.json()['capacity'] == 8

        db = SessionLocal()
        stored_class = db.query(CourseClass).filter(CourseClass.id == class_id).one()
        stored_plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id).one()
        assert stored_class.room == 'R.101'
        assert stored_class.day == 'Senin'
        assert stored_class.is_open is True
        assert stored_class.capacity == 8
        assert json.loads(stored_plan.courses_json)[0]['room'] == 'R.101'
        db.close()
    finally:
        db = SessionLocal()
        db.query(AuditLog).filter(
            AuditLog.entity_type == 'course_class',
            AuditLog.entity_id == str(class_id),
        ).delete(synchronize_session=False)
        db.query(StudyPlan).filter(StudyPlan.id == plan_id).delete(synchronize_session=False)
        db.query(CourseClass).filter(CourseClass.id == class_id).delete(synchronize_session=False)
        db.query(Course).filter(Course.code == code).delete(synchronize_session=False)
        db.query(User).filter(User.id == student_id).delete(synchronize_session=False)
        db.commit()
        db.close()
