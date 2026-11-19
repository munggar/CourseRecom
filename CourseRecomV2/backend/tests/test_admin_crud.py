import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import create_access_token
from app.main import app
from app.models import AdvisorCourseFeedback, AuditLog, Course, CourseClass, KprsRequest, StudyPlan, User, Room, LecturerDirectory


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
    room_301_code = f'FT3{int(suffix[:2], 16) % 90 + 10}'
    room_302_code = f'FT4{int(suffix[2:4], 16) % 90 + 10}'
    room_301 = Room(
        code=room_301_code, floor=3, room_number=room_301_code[3:],
        capacity=40, room_type='Ruang kuliah', is_active=True,
        source_status='test', source_url=None, notes='Room test fixture',
        verified_at=now, created_at=now,
    )
    room_302 = Room(
        code=room_302_code, floor=4, room_number=room_302_code[3:],
        capacity=40, room_type='Ruang kuliah', is_active=True,
        source_status='test', source_url=None, notes='Room test fixture',
        verified_at=now, created_at=now,
    )
    db.add_all([student, course, room_301, room_302])
    db.flush()
    section = CourseClass(
        course_code=code,
        class_name='A',
        room=room_301_code,
        day='Senin',
        start_time='08:00',
        end_time='10:30',
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
        'room': room_301_code,
        'day': 'Senin',
        'start_time': '08:00',
        'end_time': '10:30',
        'capacity': 5,
        'semester': '1',
        'is_open': True,
    }
    try:
        changed_schedule = client.put(
            f'/api/admin/classes/{class_id}',
            headers=ADMIN_HEADERS,
            json={**base_payload, 'room': room_302_code, 'day': 'Selasa'},
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
        assert stored_class.room == room_301_code
        assert stored_class.day == 'Senin'
        assert stored_class.is_open is True
        assert stored_class.capacity == 8
        assert json.loads(stored_plan.courses_json)[0]['room'] == room_301_code
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
        db.query(Room).filter(Room.code.in_([room_301_code, room_302_code])).delete(synchronize_session=False)
        db.query(User).filter(User.id == student_id).delete(synchronize_session=False)
        db.commit()
        db.close()



def test_admin_room_schedule_rules_and_separate_exports():
    suffix = uuid4().hex[:8].upper()
    room_a = f'FT2{int(suffix[:2], 16) % 90 + 10}'
    room_b = f'FT3{int(suffix[2:4], 16) % 90 + 10}'
    code_a = f'SCH{suffix}A'
    code_b = f'SCH{suffix}B'
    lecturer_nip = f'SCHD{suffix}'
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    lecturer = User(
        nim=lecturer_nip,
        username=f'sched-{suffix.lower()}',
        full_name='Dosen Jadwal Uji',
        role='dosen',
        password_hash='unused-hash',
    )
    course_a = Course(
        code=code_a, name='Mata Kuliah Jadwal 3 SKS', sks=3, semester=2,
        available_semesters='2', category='Pilihan', capacity=30, is_active=True,
    )
    course_b = Course(
        code=code_b, name='Mata Kuliah Jadwal 2 SKS', sks=2, semester=4,
        available_semesters='4', category='Pilihan', capacity=30, is_active=True,
    )
    code_c = f'SCH{suffix}C'
    course_c = Course(
        code=code_c, name='Mata Kuliah Jadwal 1 SKS', sks=1, semester=6,
        available_semesters='6', category='Pilihan', capacity=30, is_active=True,
    )
    db.add_all([lecturer, course_a, course_b, course_c])
    db.commit()
    lecturer_id = lecturer.id
    db.close()

    created_rooms = []
    created_classes = []
    try:
        for room_code in (room_a, room_b):
            created = client.post('/api/admin/rooms', headers=ADMIN_HEADERS, json={
                'code': room_code,
                'capacity': 40,
                'room_type': 'Ruang kuliah',
                'is_active': True,
                'notes': 'Ruang untuk pengujian jadwal otomatis.',
            })
            assert created.status_code == 201, created.text
            created_rooms.append(room_code)

        duration_preview = client.get(
            '/api/admin/schedule-options',
            headers=ADMIN_HEADERS,
            params={'course_code': code_a, 'room_code': room_a, 'day': 'Senin', 'lecturer_id': lecturer_id},
        )
        assert duration_preview.status_code == 200, duration_preview.text
        preview_data = duration_preview.json()
        assert preview_data['duration_minutes'] == 150
        assert preview_data['slots'][0] == {
            'start_time': '07:00', 'end_time': '09:30', 'duration_minutes': 150,
        }

        one_sks_preview = client.get(
            '/api/admin/schedule-options',
            headers=ADMIN_HEADERS,
            params={'course_code': code_c, 'room_code': room_b, 'day': 'Minggu'},
        )
        assert one_sks_preview.status_code == 200, one_sks_preview.text
        one_sks_slots = one_sks_preview.json()['slots']
        assert one_sks_preview.json()['duration_minutes'] == 50
        assert one_sks_slots[0]['start_time'] == '07:00'
        assert one_sks_slots[0]['end_time'] == '07:50'
        assert one_sks_slots[-1]['start_time'] == '17:10'
        assert one_sks_slots[-1]['end_time'] == '18:00'

        two_sks_preview = client.get(
            '/api/admin/schedule-options',
            headers=ADMIN_HEADERS,
            params={'course_code': code_b, 'room_code': room_b, 'day': 'Selasa'},
        )
        assert two_sks_preview.status_code == 200, two_sks_preview.text
        assert two_sks_preview.json()['duration_minutes'] == 100
        assert two_sks_preview.json()['slots'][0]['end_time'] == '08:40'

        created = client.post('/api/admin/classes', headers=ADMIN_HEADERS, json={
            'course_code': code_a,
            'class_name': 'A',
            'lecturer_id': lecturer_id,
            'room': room_a,
            'day': 'Senin',
            'start_time': '07:00',
            'capacity': 20,
            'semester': '2',
            'is_open': True,
        })
        assert created.status_code == 201, created.text
        assert created.json()['end_time'] == '09:30'
        created_classes.append(created.json()['id'])

        room_capacity_clash = client.post('/api/admin/classes', headers=ADMIN_HEADERS, json={
            'course_code': code_b,
            'class_name': 'MELEBIHI-KAPASITAS-RUANG',
            'lecturer_id': None,
            'room': room_b,
            'day': 'Kamis',
            'start_time': '07:00',
            'capacity': 50,
            'semester': '4',
            'is_open': True,
        })
        assert room_capacity_clash.status_code == 409
        assert 'kapasitas fisik' in room_capacity_clash.json()['detail']

        room_clash = client.post('/api/admin/classes', headers=ADMIN_HEADERS, json={
            'course_code': code_b,
            'class_name': 'A',
            'lecturer_id': None,
            'room': room_a,
            'day': 'Senin',
            'start_time': '08:00',
            'capacity': 20,
            'semester': '4',
            'is_open': True,
        })
        assert room_clash.status_code == 409
        assert 'Ruangan' in room_clash.json()['detail']

        lecturer_clash = client.post('/api/admin/classes', headers=ADMIN_HEADERS, json={
            'course_code': code_b,
            'class_name': 'B',
            'lecturer_id': lecturer_id,
            'room': room_b,
            'day': 'Senin',
            'start_time': '08:00',
            'capacity': 20,
            'semester': '4',
            'is_open': True,
        })
        assert lecturer_clash.status_code == 409
        assert 'Dosen' in lecturer_clash.json()['detail']

        reduce_room_capacity = client.patch(
            f'/api/admin/rooms/{room_a}',
            headers=ADMIN_HEADERS,
            json={
                'code': room_a, 'capacity': 10, 'room_type': 'Ruang kuliah',
                'is_active': True, 'notes': 'Tidak boleh di bawah kapasitas kelas terkait.',
            },
        )
        assert reduce_room_capacity.status_code == 409
        assert 'kuota kelas' in reduce_room_capacity.json()['detail']

        outside_window = client.post('/api/admin/classes', headers=ADMIN_HEADERS, json={
            'course_code': code_a,
            'class_name': 'C',
            'lecturer_id': None,
            'room': room_b,
            'day': 'Selasa',
            'start_time': '16:00',
            'capacity': 20,
            'semester': '2',
            'is_open': True,
        })
        assert outside_window.status_code == 409
        assert '07:00–18:00' in outside_window.json()['detail']

        wrong_duration = client.post('/api/admin/classes', headers=ADMIN_HEADERS, json={
            'course_code': code_a,
            'class_name': 'D',
            'lecturer_id': None,
            'room': room_b,
            'day': 'Rabu',
            'start_time': '07:00',
            'end_time': '09:00',
            'capacity': 20,
            'semester': '2',
            'is_open': True,
        })
        assert wrong_duration.status_code == 422
        assert 'dihitung otomatis' in wrong_duration.json()['detail']

        invalid_room = client.post('/api/admin/rooms', headers=ADMIN_HEADERS, json={
            'code': 'LAB301', 'capacity': 20, 'is_active': True,
        })
        assert invalid_room.status_code == 422

        no_capacity_activation = client.post('/api/admin/rooms', headers=ADMIN_HEADERS, json={
            'code': f'FT4{int(suffix[4:6], 16) % 90 + 10}',
            'capacity': None,
            'room_type': 'Ruang kuliah',
            'is_active': True,
            'notes': '',
        })
        assert no_capacity_activation.status_code == 422

        lecturer_export = client.get('/api/admin/lecturers/export', headers=ADMIN_HEADERS)
        room_export = client.get('/api/admin/rooms/export', headers=ADMIN_HEADERS)
        xlsx_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert lecturer_export.status_code == 200
        assert room_export.status_code == 200
        assert lecturer_export.headers['content-type'].startswith(xlsx_type)
        assert room_export.headers['content-type'].startswith(xlsx_type)
        assert lecturer_export.content[:2] == b'PK'
        assert room_export.content[:2] == b'PK'
    finally:
        db = SessionLocal()
        if created_classes:
            db.query(AuditLog).filter(
                AuditLog.entity_type == 'course_class',
                AuditLog.entity_id.in_([str(item) for item in created_classes]),
            ).delete(synchronize_session=False)
            db.query(CourseClass).filter(CourseClass.id.in_(created_classes)).delete(synchronize_session=False)
        db.query(AuditLog).filter(
            AuditLog.entity_type == 'room',
            AuditLog.entity_id.in_(created_rooms),
        ).delete(synchronize_session=False)
        db.query(Room).filter(Room.code.in_(created_rooms)).delete(synchronize_session=False)
        db.query(Course).filter(Course.code.in_([code_a, code_b, code_c])).delete(synchronize_session=False)
        db.query(User).filter(User.id == lecturer_id).delete(synchronize_session=False)
        db.commit()
        db.close()



def test_admin_can_manually_link_lecturer_directory_profile_to_account():
    suffix = uuid4().hex[:8].upper()
    first_nip = f'LINKA{suffix}'
    second_nip = f'LINKB{suffix}'
    first_profile_nidn = f'9900{suffix}'
    second_profile_nidn = f'9910{suffix}'
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    first_account = User(
        nim=first_nip, username=f'link-a-{suffix.lower()}',
        full_name='Dosen A untuk tautan', role='dosen', password_hash='unused-hash',
    )
    second_account = User(
        nim=second_nip, username=f'link-b-{suffix.lower()}',
        full_name='Dosen B untuk tautan', role='dosen', password_hash='unused-hash',
    )
    first_profile = LecturerDirectory(
        nidn=first_profile_nidn,
        full_name='Profil Dosen A',
        program_study='Sistem dan Teknologi Informasi',
        source_type='official_program_profile',
        profile_url='https://ft.uhamka.ac.id/dosen-sti/',
        notes='Fixture uji mapping',
    )
    second_profile = LecturerDirectory(
        nidn=second_profile_nidn,
        full_name='Profil Dosen B',
        program_study='Teknik Informatika',
        source_type='official_program_profile',
        profile_url='https://ft.uhamka.ac.id/dosen-ti/',
        notes='Fixture uji mapping',
    )
    db.add_all([first_account, second_account, first_profile, second_profile])
    db.commit()
    first_account_id = first_account.id
    second_account_id = second_account.id
    first_profile_id = first_profile.id
    second_profile_id = second_profile.id
    db.close()

    try:
        linked = client.patch(
            f'/api/admin/lecturer-directory/{first_profile_id}/link',
            headers=ADMIN_HEADERS,
            json={'user_id': first_account_id},
        )
        assert linked.status_code == 200, linked.text
        assert linked.json()['status'] == 'akun_terhubung'
        assert linked.json()['linked_user_id'] == first_account_id

        duplicate = client.patch(
            f'/api/admin/lecturer-directory/{second_profile_id}/link',
            headers=ADMIN_HEADERS,
            json={'user_id': first_account_id},
        )
        assert duplicate.status_code == 409, duplicate.text

        unlinked = client.patch(
            f'/api/admin/lecturer-directory/{first_profile_id}/link',
            headers=ADMIN_HEADERS,
            json={'user_id': None},
        )
        assert unlinked.status_code == 200, unlinked.text
        assert unlinked.json()['status'] == 'belum_ada_akun'
    finally:
        db = SessionLocal()
        db.query(AuditLog).filter(
            AuditLog.entity_type == 'lecturer_directory',
            AuditLog.entity_id.in_([str(first_profile_id), str(second_profile_id)]),
        ).delete(synchronize_session=False)
        db.query(LecturerDirectory).filter(
            LecturerDirectory.id.in_([first_profile_id, second_profile_id])
        ).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_([first_account_id, second_account_id])).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_admin_supports_ftti_lab_and_detects_manual_lecturer_overlap():
    suffix = uuid4().hex[:8].upper()
    room_class = f'FT3{int(suffix[:2], 16) % 90 + 10}'
    code_three = f'LAB{suffix}A'
    code_two = f'LAB{suffix}B'
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    first_course = Course(
        code=code_three, name='Mata Kuliah Laboratorium 3 SKS', sks=3,
        semester=5, available_semesters='5', category='Praktik',
        capacity=35, is_active=True,
    )
    second_course = Course(
        code=code_two, name='Mata Kuliah Laboratorium 2 SKS', sks=2,
        semester=5, available_semesters='5', category='Praktik',
        capacity=35, is_active=True,
    )
    db.add_all([first_course, second_course])
    db.commit()
    db.close()

    created_classes = []
    created_rooms = []
    try:
        created = client.post('/api/admin/rooms', headers=ADMIN_HEADERS, json={
            'code': room_class,
            'capacity': 35,
            'room_type': 'Ruang kuliah',
            'is_active': True,
            'notes': 'Sudah diverifikasi untuk tes jadwal.',
        })
        assert created.status_code == 201, created.text
        created_rooms.append(room_class)

        db = SessionLocal()
        lab_room = db.query(Room).filter(Room.code == 'FTTI1').one()
        assert lab_room.is_active is True
        assert lab_room.capacity == 35
        db.close()

        lab_class = client.post('/api/admin/classes', headers=ADMIN_HEADERS, json={
            'course_code': code_three,
            'class_name': 'LAB-A',
            'lecturer_id': None,
            'lecturer_name': 'Dosen Uji Tanpa Akun',
            'room': 'FTTI1',
            'day': 'Senin',
            'start_time': '07:00',
            'capacity': 30,
            'semester': '5',
            'is_open': True,
        })
        assert lab_class.status_code == 201, lab_class.text
        assert lab_class.json()['end_time'] == '09:30'
        created_classes.append(lab_class.json()['id'])

        overlap = client.post('/api/admin/classes', headers=ADMIN_HEADERS, json={
            'course_code': code_two,
            'class_name': 'LAB-B',
            'lecturer_id': None,
            'lecturer_name': 'dosen uji tanpa akun',
            'room': room_class,
            'day': 'Senin',
            'start_time': '08:00',
            'capacity': 30,
            'semester': '5',
            'is_open': True,
        })
        assert overlap.status_code == 409
        assert 'Dosen pengampu' in overlap.json()['detail']
    finally:
        db = SessionLocal()
        if created_classes:
            db.query(AuditLog).filter(
                AuditLog.entity_type == 'course_class',
                AuditLog.entity_id.in_([str(item) for item in created_classes]),
            ).delete(synchronize_session=False)
            db.query(CourseClass).filter(CourseClass.id.in_(created_classes)).delete(synchronize_session=False)
        for room_code in created_rooms:
            db.query(AuditLog).filter(
                AuditLog.entity_type == 'room',
                AuditLog.entity_id == room_code,
            ).delete(synchronize_session=False)
        if created_rooms:
            db.query(Room).filter(Room.code.in_(created_rooms)).delete(synchronize_session=False)
        db.query(Course).filter(Course.code.in_([code_three, code_two])).delete(synchronize_session=False)
        db.commit()
        db.close()
