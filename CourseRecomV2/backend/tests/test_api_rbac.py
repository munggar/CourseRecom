import csv
from io import StringIO
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.database import SessionLocal, ensure_schema
from app.deps import create_access_token, get_password_hash
from app.main import app
from app.models import (
    AdvisorCourseFeedback,
    AuditLog,
    Course,
    KhsDocument,
    KrsDocument,
    RecommendationCache,
    StudentRecord,
    StudyPlan,
    User,
)

client = TestClient(app)
ensure_schema()


def test_access_token_expiration_is_timezone_aware():
    token = create_access_token('timezone-test', 'mahasiswa')
    payload = jwt.decode(token, settings.jwt_secret, algorithms=['HS256'])
    assert payload['sub'] == 'timezone-test'
    assert isinstance(payload['exp'], int)


def test_health():
    # Readiness is only true after the FastAPI lifespan has completed
    # schema migration and seed initialization.
    with TestClient(app) as readiness_client:
        response = readiness_client.get('/api/health')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'


def test_cors_allows_localhost_and_loopback_frontend_origins():
    configured_origin = urlsplit(settings.frontend_url)
    if configured_origin.hostname not in {'localhost', '127.0.0.1'}:
        return
    port_suffix = f':{configured_origin.port}' if configured_origin.port else ''
    for host in ('localhost', '127.0.0.1'):
        origin = f'{configured_origin.scheme}://{host}{port_suffix}'
        response = client.options(
            '/api/auth/login',
            headers={
                'Origin': origin,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type',
            },
        )
        assert response.status_code == 200
        assert response.headers.get('access-control-allow-origin') == origin


def test_login_student():
    response = client.post('/api/auth/login', json={'username': '2203001', 'password': 'password123'})
    assert response.status_code == 200
    assert 'access_token' in response.json()

    mismatch = client.post('/api/auth/login', json={
        'username': '2203001',
        'password': 'password123',
        'role': 'dosen',
    })
    assert mismatch.status_code == 403


def test_krs_documents_and_plans_enforce_student_ownership():
    suffix = uuid4().hex[:12]
    student_a_nim = f'MA{suffix}'
    student_b_nim = f'MB{suffix}'
    db = SessionLocal()
    student_a = User(
        nim=student_a_nim,
        full_name='Mahasiswa A',
        role='mahasiswa',
        password_hash=get_password_hash('password-a'),
    )
    student_b = User(
        nim=student_b_nim,
        full_name='Mahasiswa B',
        role='mahasiswa',
        password_hash=get_password_hash('password-b'),
    )
    db.add_all([student_a, student_b])
    db.commit()
    db.refresh(student_a)
    db.refresh(student_b)
    student_a_id = student_a.id
    student_b_id = student_b.id
    plan_b = StudyPlan(
        student_id=student_b.id,
        semester=1,
        courses_json='[]',
        status='draft',
        advisor_note='',
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(plan_b)
    db.commit()
    db.refresh(plan_b)
    plan_b_id = plan_b.id
    db.close()

    try:
        token_a = create_access_token(student_a_nim, 'mahasiswa')
        headers_a = {'Authorization': 'Bearer ' + token_a}
        uploaded = client.post(
            '/api/mahasiswa/krs/dokumen',
            headers=headers_a,
            files={'file': ('krs-a.pdf', b'%PDF-1.4\nKRS UJI', 'application/pdf')},
        )
        assert uploaded.status_code == 201
        document_a_id = uploaded.json()['id']

        assert client.get(
            f'/api/mahasiswa/rencana-studi/{plan_b_id}',
            headers=headers_a,
        ).status_code == 404
        assert client.post(
            '/api/mahasiswa/krs/dokumen',
            headers=headers_a,
            files={'file': ('krs-b.pdf', b'%PDF-1.4\nDATA SALAH', 'application/pdf')},
            data={'plan_id': str(plan_b_id)},
        ).status_code == 404
        assert client.get(
            f'/api/mahasiswa/krs/dokumen/{document_a_id}',
            headers=headers_a,
        ).status_code == 200

        other_document = client.post(
            '/api/mahasiswa/krs/dokumen',
            headers={
                'Authorization': 'Bearer ' + create_access_token(student_b_nim, 'mahasiswa'),
            },
            files={'file': ('krs-b.pdf', b'%PDF-1.4\nKRS B', 'application/pdf')},
        )
        assert other_document.status_code == 201
        document_b_id = other_document.json()['id']
        assert client.get(
            f'/api/mahasiswa/krs/dokumen/{document_b_id}',
            headers=headers_a,
        ).status_code == 404
        assert client.delete(
            f'/api/mahasiswa/krs/dokumen/{document_b_id}',
            headers=headers_a,
        ).status_code == 404

        own_delete = client.delete(
            f'/api/mahasiswa/krs/dokumen/{document_a_id}',
            headers=headers_a,
        )
        assert own_delete.status_code == 204

        db = SessionLocal()
        upload_events = db.query(AuditLog).filter(
            AuditLog.actor_id.in_([student_a_id, student_b_id]),
            AuditLog.action == 'krs_document_uploaded',
        ).all()
        delete_events = db.query(AuditLog).filter(
            AuditLog.actor_id == student_a_id,
            AuditLog.action == 'krs_document_deleted',
            AuditLog.entity_id == str(document_a_id),
        ).all()
        assert len(upload_events) == 2
        assert len(delete_events) == 1

        db.close()
        own_plan_delete = client.delete(
            f'/api/mahasiswa/rencana-studi/{plan_b_id}',
            headers={
                'Authorization': 'Bearer ' + create_access_token(student_b_nim, 'mahasiswa'),
            },
        )
        assert own_plan_delete.status_code == 204
        db = SessionLocal()
        plan_delete_audit = db.query(AuditLog).filter(
            AuditLog.actor_id == student_b_id,
            AuditLog.action == 'study_plan_deleted',
            AuditLog.entity_id == str(plan_b_id),
        ).one()
        assert 'draft' in plan_delete_audit.old_value
        db.close()
    finally:
        db = SessionLocal()
        student_ids = [
            student_id for (student_id,) in db.query(User.id).filter(
                User.nim.in_([student_a_nim, student_b_nim])
            ).all()
        ]
        db.query(KrsDocument).filter(KrsDocument.student_id.in_(student_ids)).delete(
            synchronize_session=False,
        )
        db.query(AuditLog).filter(AuditLog.actor_id.in_(student_ids)).delete(
            synchronize_session=False,
        )
        db.query(StudyPlan).filter(StudyPlan.student_id.in_(
            db.query(User.id).filter(User.nim.in_([student_a_nim, student_b_nim]))
        )).delete(synchronize_session=False)
        db.query(User).filter(User.nim.in_([student_a_nim, student_b_nim])).delete(
            synchronize_session=False,
        )
        db.commit()
        db.close()


def test_admin_forbidden_for_student():
    response = client.post('/api/auth/login', json={'username': '2203001', 'password': 'password123'})
    token = response.json()['access_token']
    admin_response = client.get('/api/admin/courses', headers={'Authorization': f'Bearer {token}'})
    assert admin_response.status_code == 403


def test_student_curriculum_is_read_only_and_limited_to_semesters_one_through_eight():
    course_code = f'CUR{uuid4().hex[:12]}'.upper()
    db = SessionLocal()
    db.add_all([
        Course(
            code=course_code,
            name='Mata Kuliah Kurikulum Uji',
            sks=3,
            semester=1,
            available_semesters='1,8,9',
            category='Wajib',
            description='Keterangan kurikulum uji.',
            prerequisite_text='Lulus mata kuliah dasar.',
            prerequisite_codes='DASAR',
            is_active=True,
        ),
        Course(
            code=f'{course_code}9',
            name='Mata Kuliah di Luar Kurikulum',
            sks=3,
            semester=9,
            available_semesters='9',
            category='Pilihan',
            is_active=True,
        ),
    ])
    db.commit()
    db.close()

    try:
        student_token = create_access_token('2203001', 'mahasiswa')
        response = client.get(
            '/api/mahasiswa/kurikulum',
            headers={'Authorization': 'Bearer ' + student_token},
        )
        assert response.status_code == 200
        curriculum = response.json()
        course = next(item for item in curriculum if item['code'] == course_code)
        assert course['available_semesters'] == '1,8'
        assert course['sks'] == 3
        assert course['category'] == 'Wajib'
        assert course['prerequisite_text'] == 'Lulus mata kuliah dasar.'
        assert course['prerequisite_codes'] == 'DASAR'
        assert course['description'] == 'Keterangan kurikulum uji.'
        assert all('9' not in item['available_semesters'].split(',') for item in curriculum)

        admin_token = create_access_token('admin', 'admin')
        assert client.get(
            '/api/mahasiswa/kurikulum',
            headers={'Authorization': 'Bearer ' + admin_token},
        ).status_code == 403
        assert client.get('/api/mahasiswa/kurikulum').status_code == 401
        assert client.post('/api/mahasiswa/kurikulum', json={}).status_code == 405
    finally:
        db = SessionLocal()
        db.query(Course).filter(Course.code.in_([course_code, f'{course_code}9'])).delete(
            synchronize_session=False,
        )
        db.commit()
        db.close()


def test_admin_override_can_unlock_and_replace_courses():
    suffix = uuid4().hex[:12]
    db = SessionLocal()
    student = User(
        nim=f'OV{suffix}',
        full_name='Mahasiswa Override',
        role='mahasiswa',
        password_hash=get_password_hash('password-a'),
        semester=4,
        ipk=3.0,
    )
    admin = User(
        nim=f'ADM{suffix}',
        full_name='Admin Override',
        role='admin',
        password_hash=get_password_hash('password-a'),
    )
    course = Course(
        code=f'OV{suffix[:6]}'.upper(),
        name='Mata Kuliah Override',
        sks=3,
        semester=5,
        available_semesters='5',
        category='Wajib',
        description='Test override',
        prerequisite_text='',
        prerequisite_codes='',
        is_active=True,
    )
    db.add_all([student, admin, course])
    db.commit()
    db.refresh(student)
    db.add(KhsDocument(
        student_id=student.id,
        filename='riwayat.json',
        sha256='c' * 64,
        status='confirmed',
        parsed_data='{"metadata":{"current_semester":4,"ipk":3.0}}',
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db.commit()
    plan = StudyPlan(
        student_id=student.id,
        semester=5,
        courses_json='[]',
        status='approved',
        advisor_note='',
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    plan_id = plan.id
    student_id = student.id
    admin_id = admin.id
    course_code = course.code
    admin_nim = admin.nim
    student_nim = student.nim
    db.close()

    try:
        headers = {'Authorization': 'Bearer ' + create_access_token(admin_nim, 'admin')}
        response = client.patch(
            f'/api/admin/study-plans/{plan_id}/override',
            headers=headers,
            json={
                'status': 'draft',
                'reason': 'Override akademik untuk koreksi mata kuliah.',
                'course_codes': [course_code],
            },
        )
        assert response.status_code == 200
        assert response.json()['status'] == 'draft'

        db = SessionLocal()
        updated = db.query(StudyPlan).filter(StudyPlan.id == plan_id).first()
        assert updated.status == 'draft'
        assert course_code in updated.courses_json
        db.close()
    finally:
        db = SessionLocal()
        db.query(StudyPlan).filter(StudyPlan.id == plan_id).delete(synchronize_session=False)
        db.query(KhsDocument).filter(KhsDocument.student_id == student_id).delete(synchronize_session=False)
        db.query(Course).filter(Course.code == course_code).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.actor_id == admin_id).delete(synchronize_session=False)
        db.query(User).filter(User.nim.in_([student_nim, admin_nim])).delete(synchronize_session=False)

def test_student_public_registration_is_disabled():
    nim = f'NEW{uuid4().hex[:12]}'
    response = client.post('/api/auth/register', json={
        'nim': nim,
        'full_name': 'Mahasiswa Baru',
        'program_study': 'Sistem dan Teknologi Informasi',
        'interests': 'Manajemen Teknologi Informasi',
        'angkatan': '2022',
        'password': 'password-baru-123',
        'role': 'admin',
    })
    assert response.status_code == 403
    assert 'Admin Prodi' in response.text

    db = SessionLocal()
    try:
        assert db.query(User).filter(User.nim == nim).count() == 0
    finally:
        db.close()


def test_admin_roster_import_rejects_invalid_angkatan():
    admin_login = client.post('/api/auth/login', json={
        'username': 'admin',
        'password': 'password123',
        'role': 'admin',
    })
    assert admin_login.status_code == 200, admin_login.text
    headers = {'Authorization': f"Bearer {admin_login.json()['access_token']}"}
    admin_id = admin_login.json().get('user', {}).get('id')

    academic_year = client.get('/api/auth/academic-year')
    assert academic_year.status_code == 200
    max_year = int(academic_year.json()['max_angkatan'])
    nims = [f'BADYEAR{uuid4().hex[:8]}' for _ in range(2)]

    try:
        for nim, angkatan in zip(nims, [f'{max_year}A', str(max_year + 1)]):
            output = StringIO(newline='')
            writer = csv.writer(output)
            writer.writerow(['NIM', 'Nama Lengkap', 'Program Studi', 'Angkatan'])
            writer.writerow([nim, 'Mahasiswa Angkatan Tidak Valid', 'Sistem dan Teknologi Informasi', angkatan])
            response = client.post(
                '/api/admin/student-roster/import',
                headers=headers,
                files={'file': ('roster-invalid.csv', output.getvalue().encode('utf-8'), 'text/csv')},
            )
            assert response.status_code == 422
            assert str(max_year) in response.text
            db = SessionLocal()
            try:
                assert db.query(User).filter(User.nim == nim).count() == 0
            finally:
                db.close()
    finally:
        db = SessionLocal()
        try:
            db.query(AuditLog).filter(
                AuditLog.actor_id == admin_id,
                AuditLog.entity_type == 'student_roster',
                AuditLog.entity_id == 'batch',
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def test_admin_dashboard_lists_students_and_advisors_and_only_admin_can_delete_students():
    ensure_schema()
    suffix = uuid4().hex[:12]
    student_nim = f'MHS{suffix}'
    advisor_nim = f'DOSEN{suffix}'
    db = SessionLocal()
    student = User(
        nim=student_nim,
        full_name='Mahasiswa Hapus',
        role='mahasiswa',
        password_hash=get_password_hash('password-mhs'),
        semester=3,
        ipk=3.5,
    )
    advisor = User(
        nim=advisor_nim,
        full_name='Dosen PA Uji',
        role='dosen',
        password_hash=get_password_hash('password-dosen'),
    )
    db.add_all([student, advisor])
    db.commit()
    db.refresh(student)
    student_id = student.id
    db.add_all([
        StudentRecord(
            student_id=student_id,
            course_code='TST101',
            grade='A',
            semester=1,
        ),
        RecommendationCache(
            student_id=student_id,
            course_code='TST201',
            score=80,
            reasons='Sesuai kurikulum',
        ),
        KhsDocument(
            student_id=student_id,
            filename='riwayat.pdf',
            sha256='a' * 64,
            status='confirmed',
            parsed_data='{}',
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ),
        StudyPlan(
            student_id=student_id,
            semester=4,
            courses_json='[]',
            status='pending',
            advisor_note='',
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ),
    ])
    db.commit()
    db.close()

    try:
        admin_headers = {
            'Authorization': 'Bearer ' + create_access_token('admin', 'admin'),
        }
        student_headers = {
            'Authorization': 'Bearer ' + create_access_token(student_nim, 'mahasiswa'),
        }
        dashboard = client.get('/api/admin/dashboard', headers=admin_headers)
        assert dashboard.status_code == 200
        data = dashboard.json()
        listed_student = next(item for item in data['students'] if item['nim'] == student_nim)
        assert listed_student['full_name'] == 'Mahasiswa Hapus'
        assert listed_student['semester'] == 3
        assert listed_student['khs_confirmed'] is True
        assert {'nim': advisor_nim, 'full_name': 'Dosen PA Uji'} in data['advisors']
        assert client.get('/api/admin/dashboard', headers=student_headers).status_code == 403
        assert client.delete(
            f'/api/admin/students/{student_nim}',
            headers=student_headers,
        ).status_code == 403

        deleted = client.delete(
            f'/api/admin/students/{student_nim}',
            headers=admin_headers,
        )
        assert deleted.status_code == 204
        assert client.delete(
            f'/api/admin/students/{student_nim}',
            headers=admin_headers,
        ).status_code == 404

        db = SessionLocal()
        assert db.query(User).filter(User.id == student_id).first() is None
        assert db.query(StudentRecord).filter(StudentRecord.student_id == student_id).count() == 0
        assert db.query(RecommendationCache).filter(RecommendationCache.student_id == student_id).count() == 0
        assert db.query(KhsDocument).filter(KhsDocument.student_id == student_id).count() == 0
        assert db.query(StudyPlan).filter(StudyPlan.student_id == student_id).count() == 0
        assert db.query(User).filter(User.nim == advisor_nim).one().role == 'dosen'
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == 'user',
            AuditLog.entity_id == str(student_id),
            AuditLog.action == 'student_deleted',
        ).count() == 1
        db.close()
    finally:
        db = SessionLocal()
        db.query(AuditLog).filter(
            AuditLog.entity_type == 'user',
            AuditLog.entity_id == str(student_id),
            AuditLog.action == 'student_deleted',
        ).delete(synchronize_session=False)
        db.query(User).filter(User.nim == student_nim).delete(synchronize_session=False)
        db.query(User).filter(User.nim == advisor_nim).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_teacher_dashboard_lists_registered_students_and_actual_interest_data():
    suffix = uuid4().hex[:12]
    teacher_nim = f'DOSEN{suffix}'
    student_nim = f'MHS{suffix}'
    db = SessionLocal()
    db.add_all([
        teacher := User(
            nim=teacher_nim,
            full_name='Dosen Uji',
            role='dosen',
            password_hash=get_password_hash('password-dosen'),
        ),
        student := User(
            nim=student_nim,
            full_name='Mahasiswa Terdaftar',
            role='mahasiswa',
            password_hash=get_password_hash('password-mhs'),
            interests='Manajemen Sistem Informasi,Kecerdasan Bisnis',
        ),
    ])
    db.commit()
    student.advisor_id = teacher.id
    db.commit()
    db.close()

    try:
        token = create_access_token(teacher_nim, 'dosen')
        response = client.get(
            '/api/dosen/mahasiswa',
            headers={'Authorization': 'Bearer ' + token},
        )
        assert response.status_code == 200
        students = response.json()
        student = next(item for item in students if item['nim'] == student_nim)
        assert student['full_name'] == 'Mahasiswa Terdaftar'
        assert student['interests'] == 'Manajemen Sistem Informasi,Kecerdasan Bisnis'
        assert student['khs_confirmed'] is False
        assert 'status' not in student
        assert all(item['nim'] != teacher_nim for item in students)
    finally:
        db = SessionLocal()
        db.query(User).filter(User.nim.in_([teacher_nim, student_nim])).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_teacher_reviews_submitted_study_plan_with_guidance_note():
    ensure_schema()
    suffix = uuid4().hex[:12]
    teacher_nim = f'DOSEN{suffix}'
    student_nim = f'MHS{suffix}'
    db = SessionLocal()
    student = User(
        nim=student_nim,
        full_name='Mahasiswa Review',
        role='mahasiswa',
        password_hash=get_password_hash('password-mhs'),
        semester=3,
        ipk=3.0,
    )
    teacher = User(
        nim=teacher_nim,
        full_name='Dosen Reviewer',
        role='dosen',
        password_hash=get_password_hash('password-dosen'),
    )
    db.add_all([teacher, student])
    db.commit()
    db.refresh(teacher)
    db.refresh(student)
    student.advisor_id = teacher.id
    db.add(Course(
        code='TST401',
        name='Sistem Informasi',
        sks=3,
        semester=4,
        available_semesters='4',
        category='Pilihan',
        prerequisite_codes='TST301',
        is_active=True,
    ))
    db.add(Course(
        code='TST402',
        name='Analisis Proses Bisnis',
        sks=3,
        semester=4,
        available_semesters='4',
        category='Pilihan',
        prerequisite_codes='',
        is_active=True,
    ))
    db.add(StudentRecord(
        student_id=student.id,
        course_code='TST301',
        course_name='Dasar',
        grade='A',
        semester=1,
        sks=3,
        grade_point=4.0,
        is_passed=True,
    ))
    db.add(KhsDocument(
        student_id=student.id,
        filename='riwayat.json',
        sha256='b' * 64,
        status='confirmed',
        parsed_data='{"metadata":{"current_semester":3,"ipk":3.0}}',
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db.commit()
    plan = StudyPlan(
        student_id=student.id,
        semester=4,
        courses_json='[{"code":"TST401","name":"Sistem Informasi","sks":3,"score":80,"reasons":["Sesuai kurikulum"],"prerequisite_text":"TST301"}]',
        status='pending',
        advisor_note='',
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(plan)
    db.commit()
    plan_id = plan.id
    student_id = student.id
    teacher_id = teacher.id
    db.close()

    try:
        teacher_headers = {
            'Authorization': 'Bearer ' + create_access_token(teacher_nim, 'dosen'),
        }
        student_headers = {
            'Authorization': 'Bearer ' + create_access_token(student_nim, 'mahasiswa'),
        }
        listed = client.get('/api/dosen/rencana-studi', headers=teacher_headers)
        assert listed.status_code == 200
        item = next(plan for plan in listed.json() if plan['id'] == plan_id)
        assert item['student_nim'] == student_nim
        assert item['courses'][0]['code'] == 'TST401'

        missing_note = client.patch(
            f'/api/dosen/rencana-studi/{plan_id}',
            headers=teacher_headers,
            json={'status': 'revision_requested', 'advisor_note': ''},
        )
        assert missing_note.status_code == 422
        revision = client.patch(
            f'/api/dosen/rencana-studi/{plan_id}',
            headers=teacher_headers,
            json={'status': 'revision_requested', 'advisor_note': 'Tinjau kembali beban SKS.', 'rejected_course_codes': ['TST401']},
        )
        assert revision.status_code == 200
        assert revision.json()['status'] == 'revision_requested'
        assert revision.json()['advisor_note'] == 'Tinjau kembali beban SKS.'
        feedback_rows = db.query(AdvisorCourseFeedback).filter(
            AdvisorCourseFeedback.study_plan_id == plan_id,
        ).all()
        assert len(feedback_rows) == 1
        assert feedback_rows[0].course_code == 'TST401'
        assert feedback_rows[0].reason == 'Tinjau kembali beban SKS.'
        student_plans = client.get('/api/mahasiswa/rencana-studi', headers=student_headers)
        assert student_plans.status_code == 200
        assert student_plans.json()[0]['advisor_feedback'][0]['course_code'] == 'TST401'
        deletion_attempt = client.delete(
            f'/api/mahasiswa/rencana-studi/{plan_id}',
            headers=student_headers,
        )
        assert deletion_attempt.status_code == 409
        assert 'riwayat evaluasi' in deletion_attempt.json()['detail'].lower()

        replacement = client.patch(
            f'/api/mahasiswa/rencana-studi/{plan_id}',
            headers=student_headers,
            json={'course_codes': ['TST402']},
        )
        assert replacement.status_code == 200, replacement.text
        alternatives = client.get('/api/rekomendasi', headers=student_headers)
        assert alternatives.status_code == 200, alternatives.text
        assert all(item['code'] != 'TST401' for item in alternatives.json())

        resubmitted = client.post(
            f'/api/mahasiswa/rencana-studi/{plan_id}/submit',
            headers=student_headers,
        )
        assert resubmitted.status_code == 200, resubmitted.text
        assert resubmitted.json()['status'] == 'pending'

        db = SessionLocal()
        plan_audit_actions = {
            item.action for item in db.query(AuditLog).filter(
                AuditLog.entity_type == 'study_plan',
                AuditLog.entity_id == str(plan_id),
            ).all()
        }
        assert {'study_plan_updated', 'study_plan_resubmitted', 'study_plan_review'} <= plan_audit_actions
        db.close()

        approved = client.patch(
            f'/api/dosen/rencana-studi/{plan_id}',
            headers=teacher_headers,
            json={'status': 'approved', 'advisor_note': 'Sudah sesuai.'},
        )
        assert approved.status_code == 200
        assert approved.json()['status'] == 'approved'
        assert client.get('/api/dosen/rencana-studi', headers=student_headers).status_code == 403
        assert client.patch(
            f'/api/dosen/rencana-studi/{plan_id}',
            headers=teacher_headers,
            json={'status': 'revision_requested', 'advisor_note': 'Ubah lagi.'},
        ).status_code == 409
    finally:
        db = SessionLocal()
        try:
            db.query(AdvisorCourseFeedback).filter(AdvisorCourseFeedback.study_plan_id == plan_id).delete()
            db.query(StudyPlan).filter(StudyPlan.id == plan_id).delete()
            db.query(KhsDocument).filter(KhsDocument.student_id == student_id).delete()
            db.query(StudentRecord).filter(StudentRecord.student_id == student_id).delete()
            db.query(Course).filter(Course.code.in_(['TST401', 'TST402'])).delete()
            db.query(AuditLog).filter(
                AuditLog.actor_id.in_([student_id, teacher_id]),
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id == student_id).delete(synchronize_session=False)
            db.query(User).filter(User.nim == teacher_nim).delete()
            db.commit()
        finally:
            db.close()



def test_admin_dashboard_returns_live_totals_and_course_counts_for_semesters_one_to_eight():
    ensure_schema()
    suffix = uuid4().hex[:10].upper()
    student_nim = f'AN{suffix}'
    advisor_nim = f'AD{suffix}'
    course_code = f'CH{suffix}'
    db = SessionLocal()
    student = User(
        nim=student_nim,
        full_name='Mahasiswa Analitik',
        role='mahasiswa',
        password_hash=get_password_hash('password-mhs'),
    )
    advisor = User(
        nim=advisor_nim,
        full_name='Dosen Analitik',
        role='dosen',
        password_hash=get_password_hash('password-dosen'),
    )
    course = Course(
        code=course_code,
        name='Mata Kuliah Analitik',
        sks=3,
        semester=1,
        available_semesters='1,8,9',
        category='Pilihan',
        is_active=True,
    )
    db.add_all([student, advisor, course])
    db.commit()
    db.refresh(student)
    db.add(KhsDocument(
        student_id=student.id,
        filename='analitik.pdf',
        sha256='d' * 64,
        status='confirmed',
        parsed_data='{}',
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db.commit()
    db.close()

    try:
        token = create_access_token('admin', 'admin')
        response = client.get('/api/admin/dashboard', headers={'Authorization': 'Bearer ' + token})
        assert response.status_code == 200
        analytics = response.json()['analytics']
        assert analytics['total_students'] >= 1
        assert analytics['confirmed_khs_students'] >= 1
        assert analytics['total_advisors'] >= 1
        assert len(analytics['courses_by_semester']) == 8
        semester_counts = {item['semester']: item['count'] for item in analytics['courses_by_semester']}
        assert semester_counts[1] >= 1
        assert semester_counts[8] >= 1
        assert 9 not in semester_counts
        assert analytics['total_active_courses'] >= 1
    finally:
        db = SessionLocal()
        db.query(KhsDocument).filter(KhsDocument.filename == 'analitik.pdf').delete(synchronize_session=False)
        db.query(Course).filter(Course.code == course_code).delete(synchronize_session=False)
        db.query(User).filter(User.nim.in_([student_nim, advisor_nim])).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_student_recommendations_separate_mandatory_courses_from_optional_recommendations():
    ensure_schema()
    suffix = uuid4().hex[:10].upper()
    student_nim = f'RC{suffix}'
    mandatory_code = f'WM{suffix[:6]}'
    optional_code = f'PL{suffix[:6]}'
    db = SessionLocal()
    student = User(
        nim=student_nim,
        full_name='Mahasiswa Rekomendasi',
        role='mahasiswa',
        password_hash=get_password_hash('password-mhs'),
        semester=4,
        ipk=3.5,
        interests='Kecerdasan Bisnis',
    )
    mandatory_course = Course(
        code=mandatory_code,
        name='Mata Kuliah Wajib Uji',
        sks=3,
        semester=5,
        available_semesters='5',
        category='Inti Teknologi & Pemrograman',
        description='Wajib Semester 5',
        is_active=True,
    )
    optional_course = Course(
        code=optional_code,
        name='Mata Kuliah Pilihan Uji',
        sks=3,
        semester=5,
        available_semesters='5',
        category='Pilihan',
        is_active=True,
    )
    db.add_all([student, mandatory_course, optional_course])
    db.commit()
    db.refresh(student)
    db.add(KhsDocument(
        student_id=student.id,
        filename='rekomendasi-uji.json',
        sha256='e' * 64,
        status='confirmed',
        parsed_data='{"metadata":{"current_semester":4,"ipk":3.5,"full_name":"Mahasiswa Rekomendasi"}}',
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db.commit()
    db.close()

    try:
        token = create_access_token(student_nim, 'mahasiswa')
        response = client.get(
            '/api/mahasiswa/rekomendasi',
            headers={'Authorization': 'Bearer ' + token},
        )
        assert response.status_code == 200
        result = response.json()
        assert all(item['mandatory'] is False for item in result['recommendations'])
        assert [item['code'] for item in result['mandatory_courses']] == [mandatory_code]
        assert result['mandatory_courses'][0]['mandatory'] is True
        assert result['mandatory_courses'][0]['description'] == 'Wajib Semester 5'
        assert optional_code in [item['code'] for item in result['recommendations']]
    finally:
        db = SessionLocal()
        db.query(KhsDocument).filter(KhsDocument.filename == 'rekomendasi-uji.json').delete(synchronize_session=False)
        db.query(Course).filter(Course.code.in_([mandatory_code, optional_code])).delete(synchronize_session=False)
        db.query(User).filter(User.nim == student_nim).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_khs_confirmation_rejects_program_study_mismatch_with_student_account():
    ensure_schema()
    suffix = uuid4().hex[:10]
    nim = f'KHS{suffix}'
    db = SessionLocal()
    student = User(
        nim=nim,
        full_name='Mahasiswa KHS Program Test',
        role='mahasiswa',
        password_hash=get_password_hash('password-khs-test'),
        program_study='Sistem dan Teknologi Informasi',
        interests='Manajemen Teknologi Informasi',
        semester=1,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    document = KhsDocument(
        student_id=student.id,
        filename='khs-program-test.json',
        sha256='e' * 64,
        status='pending',
        parsed_data='{"metadata":{"current_semester":1},"semesters":[{"semester":1,"courses":[]}],"courses":[]}',
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    document_id = document.id
    student_id = student.id
    token = create_access_token(nim, 'mahasiswa')
    db.close()

    try:
        response = client.post(
            f'/api/mahasiswa/khs/{document_id}/confirm',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'nim': nim,
                'full_name': 'Mahasiswa KHS Program Test',
                'program_study': 'Teknik Informatika',
                'current_semester': 1,
                'ip_semesters': {'1': 3.25},
                'courses': [
                    {'semester': 1, 'code': 'KHS101', 'name': 'Pengantar Komputasi', 'sks': 3, 'grade': 'A', 'numeric_grade': 88},
                ],
            },
        )
        assert response.status_code == 422, response.text
        db = SessionLocal()
        stored_document = db.query(KhsDocument).filter(KhsDocument.id == document_id).one()
        assert stored_document.status == 'pending'
        assert db.query(StudentRecord).filter(StudentRecord.student_id == student_id).count() == 0
        db.close()
    finally:
        db = SessionLocal()
        db.query(KhsDocument).filter(KhsDocument.id == document_id).delete(synchronize_session=False)
        db.query(StudentRecord).filter(StudentRecord.student_id == student_id).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.actor_id == student_id).delete(synchronize_session=False)
        db.query(User).filter(User.id == student_id).delete(synchronize_session=False)
        db.commit()
        db.close()
