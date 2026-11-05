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
    response = client.get('/api/health')
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
        db.commit()
        db.close()


def test_student_registration_creates_student_only_account():
    nim = f'NEW{uuid4().hex[:12]}'
    try:
        response = client.post('/api/auth/register', json={
            'nim': nim,
            'full_name': 'Mahasiswa Baru',
            'password': 'password-baru-123',
            'role': 'admin',
        })
        assert response.status_code == 201, response.text
        assert response.json()['role'] == 'mahasiswa'

        duplicate = client.post('/api/auth/register', json={
            'nim': nim,
            'full_name': 'Nama Lain',
            'password': 'password-baru-123',
        })
        assert duplicate.status_code == 409

        login = client.post('/api/auth/login', json={
            'username': nim,
            'password': 'password-baru-123',
        })
        assert login.status_code == 200
        headers = {'Authorization': f'Bearer {login.json()["access_token"]}'}
        current_user = client.get('/api/auth/me', headers=headers)
        assert current_user.status_code == 200
        assert current_user.json()['role'] == 'mahasiswa'
        assert client.get('/api/admin/courses', headers=headers).status_code == 403
    finally:
        db = SessionLocal()
        db.query(AuditLog).filter(
            AuditLog.actor_id.in_(
                db.query(User.id).filter(User.nim == nim),
            ),
        ).delete(synchronize_session=False)
        db.query(User).filter(User.nim == nim).delete()
        db.commit()
        db.close()


def test_student_registration_rejects_short_password():
    response = client.post('/api/auth/register', json={
        'nim': f'NEW{uuid4().hex[:12]}',
        'full_name': 'Mahasiswa Baru',
        'password': 'short',
    })
    assert response.status_code == 422


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
        db.close()
    finally:
        db = SessionLocal()
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
        category='Wajib',
        prerequisite_codes='TST301',
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
            json={'status': 'revision_requested', 'advisor_note': 'Tinjau kembali beban SKS.'},
        )
        assert revision.status_code == 200
        assert revision.json()['status'] == 'revision_requested'
        assert revision.json()['advisor_note'] == 'Tinjau kembali beban SKS.'

        resubmitted = client.post(
            f'/api/mahasiswa/rencana-studi/{plan_id}/submit',
            headers=student_headers,
        )
        assert resubmitted.status_code == 200
        assert resubmitted.json()['status'] == 'pending'

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
            db.query(StudyPlan).filter(StudyPlan.id == plan_id).delete()
            db.query(KhsDocument).filter(KhsDocument.student_id == student_id).delete()
            db.query(StudentRecord).filter(StudentRecord.student_id == student_id).delete()
            db.query(Course).filter(Course.code == 'TST401').delete()
            db.query(AuditLog).filter(
                AuditLog.actor_id.in_([student_id, teacher_id]),
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id == student_id).delete(synchronize_session=False)
            db.query(User).filter(User.nim == teacher_nim).delete()
            db.commit()
        finally:
            db.close()
