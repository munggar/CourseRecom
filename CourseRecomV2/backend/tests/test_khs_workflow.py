from fastapi.testclient import TestClient

from app.database import SessionLocal, ensure_schema
from app.deps import get_password_hash
from app.main import app
from app.models import AuditLog, Course, KhsDocument, StudentRecord, StudyPlan, User
from app.services.recommendation import _interest_matches, _similarity


def test_two_student_interests_match_course_catalog_specializations():
    assert _interest_matches('Peminatan Manajemen SI', 'Manajemen Sistem Informasi')
    assert _interest_matches('Kecerdasan Bisnis (KB)', 'Data')
    assert _interest_matches('Manajemen & Sistem Informasi', 'Manajemen Sistem Informasi')
    assert _interest_matches('Peminatan Kecerdasan Bisnis', 'Kecerdasan Bisnis')
    assert _interest_matches('Data', 'Kecerdasan Bisnis')
    assert not _interest_matches('Peminatan Kecerdasan Bisnis', 'Manajemen Sistem Informasi')
    assert not _interest_matches('Peminatan Manajemen SI', 'Kecerdasan Bisnis')


def test_student_similarity_matches_course_names_when_codes_differ():
    student_records = [
        StudentRecord(course_code='TI101', course_name='Algoritma Dasar', grade='A'),
        StudentRecord(course_code='TI201', course_name='Basis Data', grade='B'),
    ]
    peer_records = [
        StudentRecord(course_code='03045018', course_name='Algoritma-Dasar', grade='A'),
        StudentRecord(course_code='03045022', course_name='Basis Data', grade='B'),
    ]

    assert _similarity(student_records, peer_records) == 1.0


def test_khs_preview_is_not_saved_until_confirmation_and_rules_filter_courses(monkeypatch):
    ensure_schema()
    nim = 'TESTKHS9001'
    db = SessionLocal()
    db.query(Course).filter(Course.code.in_([
        'TST301', 'TST302', 'TST305', 'TST306', '03045026', 'TST309',
        'TST308', 'TST303', 'TST304',
    ])).delete(synchronize_session=False)
    db.query(User).filter(User.nim.in_([nim, 'TESTPEER9001'])).delete(synchronize_session=False)
    db.commit()
    student = User(
        nim=nim,
        full_name='Mahasiswa Uji',
        role='mahasiswa',
        password_hash=get_password_hash('test-password'),
        ipk=3.4,
        kuota_sks=22,
        interests='Data',
    )
    advisor = db.query(User).filter(User.nim == 'pa001', User.role == 'dosen').first()
    if advisor:
        student.advisor_id = advisor.id
    peer = User(
        nim='TESTPEER9001',
        full_name='Mahasiswa Pembanding',
        role='mahasiswa',
        password_hash=get_password_hash('test-password'),
    )
    eligible = Course(
        code='TST301', name='Kursus Layak', sks=3, semester=3, category='Data',
        prerequisite_codes='PRE001',
    )
    missing_prereq = Course(
        code='TST302', name='Kursus Prasyarat', sks=3, semester=3, category='Data',
        prerequisite_codes='MISSING',
    )
    d_grade_prereq = Course(
        code='TST305', name='Prasyarat Nilai D', sks=3, semester=3, category='Data',
        prerequisite_codes='PRE002',
    )
    failed_grade_prereq = Course(
        code='TST306', name='Prasyarat Nilai E', sks=3, semester=3, category='Data',
        prerequisite_codes='PRE003',
    )
    jaringan_course = Course(
        code='03045026', name='Jaringan Komputer dan Komunikasi Data', sks=3,
        semester=3, category='Jaringan',
    )
    jaringan_prereq_course = Course(
        code='TST309', name='Kursus dengan Prasyarat Jaringan', sks=3, semester=3,
        category='Jaringan', prerequisite_codes='03045026',
    )
    failed_repeat_course = Course(
        code='TST308', name='Kursus yang Harus Diulang', sks=3, semester=3, category='Data',
    )
    previously_passed = Course(
        code='TST303', name='Kursus Pernah Lulus', sks=3, semester=3, category='Data',
        prerequisite_codes='',
    )
    multi_semester_course = Course(
        code='TST304', name='Kursus Multi Semester', sks=2, semester=5,
        available_semesters='3,5', category='Data', description='Catatan dari katalog.',
        prerequisite_text='PRE001 wajib lulus', prerequisite_codes='PRE001',
    )
    db.add_all([
        student, eligible, missing_prereq, d_grade_prereq, failed_grade_prereq,
        jaringan_course, jaringan_prereq_course, failed_repeat_course,
        previously_passed, multi_semester_course,
    ])
    db.add(peer)
    db.commit()
    student_id = student.id
    peer_id = peer.id
    db.add_all([
        StudentRecord(
            student_id=peer_id,
            course_code='PEER-PRE',
            course_name='Prasyarat',
            semester=1,
            grade='A',
        ),
        StudentRecord(
            student_id=peer_id,
            course_code='PEER301',
            course_name='Kursus Layak',
            semester=3,
            grade='A',
        ),
    ])
    db.commit()
    db.close()

    def parsed_khs(_content):
        return {
            'metadata': {
                'nim': nim,
                'full_name': 'Mahasiswa Uji',
                'program_study': 'Teknik Informatika',
                'current_semester': 2,
                'ipk': 3.4,
            },
            'semesters': [
                {
                    'semester': 1,
                    'ip_semester': 3.5,
                    'courses': [
                        {'semester': 1, 'code': 'PRE001', 'name': 'Prasyarat', 'sks': 3, 'grade': 'A', 'numeric_grade': 90, 'grade_point': 4},
                        {'semester': 1, 'code': 'TST303', 'name': 'Kursus Pernah Lulus', 'sks': 3, 'grade': 'B', 'numeric_grade': 80, 'grade_point': 3},
                        {'semester': 1, 'code': 'PRE002', 'name': 'Prasyarat Nilai D', 'sks': 3, 'grade': 'D', 'numeric_grade': 60, 'grade_point': 1},
                        {'semester': 1, 'code': 'PRE003', 'name': 'Prasyarat Nilai E', 'sks': 3, 'grade': 'E', 'numeric_grade': 40, 'grade_point': 0},
                        {'semester': 1, 'code': '030450026', 'name': 'Jaringan Komp. & Kom.Data', 'sks': 3, 'grade': 'A', 'numeric_grade': 90, 'grade_point': 4},
                        {'semester': 1, 'code': 'TST308', 'name': 'Kursus yang Harus Diulang', 'sks': 3, 'grade': 'E', 'numeric_grade': 40, 'grade_point': 0},
                        {'semester': 1, 'code': 'OTHER0', 'name': 'Kursus Lain', 'sks': 3, 'grade': 'C', 'numeric_grade': 70, 'grade_point': 2},
                    ],
                },
                {
                    'semester': 2,
                    'ip_semester': 3.4,
                    'courses': [
                        {'semester': 2, 'code': 'OTHER1', 'name': 'Kursus Lain', 'sks': 3, 'grade': 'B', 'numeric_grade': 80, 'grade_point': 3},
                    ],
                },
            ],
            'warnings': [],
        }

    monkeypatch.setattr('app.api.routes.mahasiswa.parse_khs_pdf', parsed_khs)
    try:
        with TestClient(app) as client:
            login = client.post('/api/auth/login', json={'username': nim, 'password': 'test-password'})
            assert login.status_code == 200
            headers = {'Authorization': f"Bearer {login.json()['access_token']}"}

            preview = client.post(
                '/api/mahasiswa/khs/preview',
                headers=headers,
                files={'file': ('riwayat.pdf', b'%PDF-test', 'application/pdf')},
            )
            assert preview.status_code == 200, preview.text
            preview_data = preview.json()
            assert preview_data['status'] == 'pending'

            db = SessionLocal()
            assert db.query(StudentRecord).filter(StudentRecord.student_id == student_id).count() == 0
            db.close()

            confirmation = client.post(
                f"/api/mahasiswa/khs/{preview_data['id']}/confirm",
                headers=headers,
                json={
                    'nim': nim,
                    'full_name': 'Mahasiswa Uji',
                    'program_study': 'Teknik Informatika',
                    'current_semester': 2,
                    'ipk': 3.4,
                    'ip_semesters': {'1': 3.5, '2': 3.4},
                    'courses': [
                        course
                        for semester in preview_data['semesters']
                        for course in semester['courses']
                    ],
                },
            )
            assert confirmation.status_code == 200
            assert confirmation.json()['status'] == 'confirmed'
            db = SessionLocal()
            saved_duplicate_records = (
                db.query(StudentRecord)
                .filter(
                    StudentRecord.student_id == student_id,
                    StudentRecord.course_name == 'Kursus Lain',
                )
                .all()
            )
            assert len(saved_duplicate_records) == 2
            assert {record.semester for record in saved_duplicate_records} == {1, 2}
            grades_by_semester = {
                record.semester: record.grade
                for record in saved_duplicate_records
            }
            assert grades_by_semester == {1: 'C', 2: 'B'}
            db.close()

            result = client.get('/api/mahasiswa/rekomendasi', headers=headers)
            assert result.status_code == 200
            recommendation_data = result.json()
            assert recommendation_data['target_semester'] == 3
            assert recommendation_data['profile']['kuota_sks'] == 24
            recommended_codes = {item['code'] for item in recommendation_data['recommendations']}
            rejected_codes = {item['code'] for item in recommendation_data['rejected']}
            assert 'TST301' in recommended_codes
            similar_course = next(
                item for item in recommendation_data['recommendations']
                if item['code'] == 'TST301'
            )
            assert similar_course['factors']['similar_students'] > 0
            assert similar_course['factors']['interest'] > 0
            assert similar_course['factors']['course_pattern'] > 0
            assert 'TST304' in recommended_codes
            assert 'TST305' in recommended_codes
            assert 'TST309' in recommended_codes
            assert 'TST302' in rejected_codes
            assert 'TST306' in rejected_codes
            assert 'TST303' in rejected_codes
            assert 'TST308' in rejected_codes
            profile = client.get('/api/mahasiswa/profil', headers=headers)
            assert profile.status_code == 200
            assert profile.json()['kuota_sks'] == 24
            multi_semester_recommendation = next(
                item for item in recommendation_data['recommendations'] if item['code'] == 'TST304'
            )
            assert multi_semester_recommendation['description'] == 'Catatan dari katalog.'
            assert multi_semester_recommendation['prerequisite_text'] == 'PRE001 wajib lulus'
            assert multi_semester_recommendation['semester'] == 3
            assert next(
                item for item in recommendation_data['recommendations'] if item['code'] == 'TST301'
            )['factors']['interest'] == 100
            assert next(
                item for item in recommendation_data['recommendations'] if item['code'] == 'TST309'
            )['factors']['interest'] == 0
            antara_courses = {
                item['code']: item for item in recommendation_data['semester_antara']
            }
            assert set(antara_courses) == {'PRE003', 'TST308'}
            assert antara_courses['TST308']['grade'] == 'E'
            assert antara_courses['PRE003']['grade'] == 'E'
            assert 'MISSING' in recommendation_data['rejected'][0]['reason_block'] or any(
                'MISSING' in item['reason_block'] for item in recommendation_data['rejected']
            )
            with monkeypatch.context() as quota_patch:
                mocked_recommendations = lambda *_: {
                    'status': 'ready',
                    'message': None,
                    'target_semester': 3,
                    'recommendations': [
                        {'code': f'CAP00{number}', 'sks': 9}
                        for number in range(1, 4)
                    ],
                    'rejected': [],
                    'profile': {'kuota_sks': 24},
                }
                quota_patch.setattr(
                    'app.api.routes.mahasiswa.build_recommendation_result',
                    mocked_recommendations,
                )
                quota_patch.setattr(
                    'app.services.academic.build_recommendation_result',
                    mocked_recommendations,
                )
                over_quota_submission = client.post(
                    '/api/mahasiswa/rencana-studi',
                    headers=headers,
                    json={'course_codes': ['CAP001', 'CAP002', 'CAP003']},
                )
                assert over_quota_submission.status_code == 422
                assert over_quota_submission.json()['detail'] == (
                    'Total SKS melebihi batas maksimum (24 SKS).'
                )
            invalid_submission = client.post(
                '/api/mahasiswa/rencana-studi',
                headers=headers,
                json={'course_codes': ['TST302']},
            )
            assert invalid_submission.status_code == 422
            submission = client.post(
                '/api/mahasiswa/rencana-studi',
                headers=headers,
                json={'course_codes': ['TST301']},
            )
            assert submission.status_code == 201, submission.text
            submitted_plan = submission.json()
            assert submitted_plan['semester'] == 3
            assert submitted_plan['status'] == 'pending'
            assert submitted_plan['courses'][0]['code'] == 'TST301'
            own_plans = client.get('/api/mahasiswa/rencana-studi', headers=headers)
            assert own_plans.status_code == 200
            assert own_plans.json()[0]['id'] == submitted_plan['id']
            duplicate_submission = client.post(
                '/api/mahasiswa/rencana-studi',
                headers=headers,
                json={'course_codes': ['TST301']},
            )
            assert duplicate_submission.status_code == 409
            db = SessionLocal()
            plan = db.query(StudyPlan).filter(StudyPlan.id == submitted_plan['id']).one()
            plan.status = 'approved'
            db.commit()
            db.close()
            locked_submission = client.post(
                '/api/mahasiswa/rencana-studi',
                headers=headers,
                json={'course_codes': ['TST301']},
            )
            assert locked_submission.status_code == 409
            assert locked_submission.json()['detail'] == (
                'KRS sudah disetujui dan tidak dapat diubah.'
            )
    finally:
        db = SessionLocal()
        db.query(StudentRecord).filter(StudentRecord.student_id == student_id).delete()
        db.query(KhsDocument).filter(KhsDocument.student_id == student_id).delete()
        db.query(StudyPlan).filter(StudyPlan.student_id == student_id).delete()
        db.query(StudentRecord).filter(StudentRecord.student_id == peer_id).delete()
        db.query(Course).filter(Course.code.in_([
            'TST301', 'TST302', 'TST303', 'TST304', 'TST305', 'TST306',
            'TST308', 'TST309', '03045026',
        ])).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.actor_id.in_([student_id, peer_id])).delete(
            synchronize_session=False,
        )
        db.query(User).filter(User.id == student_id).delete()
        db.query(User).filter(User.id == peer_id).delete()
        db.commit()
        db.close()


def test_multiple_khs_images_create_a_reviewable_preview(monkeypatch):
    ensure_schema()
    nim = 'TESTIMG9001'
    db = SessionLocal()
    student = User(
        nim=nim,
        full_name='Mahasiswa Foto',
        role='mahasiswa',
        password_hash=get_password_hash('test-password'),
    )
    db.add(student)
    db.commit()
    student_id = student.id
    db.close()

    def parsed_images(contents):
        assert contents == [b'page-one', b'page-two']
        return {
            'metadata': {
                'nim': nim,
                'full_name': 'Mahasiswa Foto',
                'program_study': 'Teknik Informatika',
                'current_semester': 1,
                'ipk': 3.5,
            },
            'semesters': [{
                'semester': 1,
                'ip_semester': 3.5,
                'courses': [{
                    'semester': 1,
                    'code': 'TI101',
                    'name': 'Algoritma Dasar',
                    'sks': 3,
                    'grade': 'A',
                    'numeric_grade': 90,
                    'grade_point': 4,
                }],
            }],
            'warnings': [],
            'source_type': 'image',
        }

    monkeypatch.setattr('app.api.routes.mahasiswa.parse_khs_images', parsed_images)
    try:
            with TestClient(app) as client:
                login = client.post('/api/auth/login', json={'username': nim, 'password': 'test-password'})
                assert login.status_code == 200
                headers = {'Authorization': f"Bearer {login.json()['access_token']}"}

                response = client.post(
                    '/api/mahasiswa/khs/preview',
                    headers=headers,
                    files=[
                        ('files', ('halaman-1.jpg', b'page-one', 'image/jpeg')),
                        ('files', ('halaman-2.jpg', b'page-two', 'image/jpeg')),
                    ],
                )

                assert response.status_code == 200, response.text
                preview = response.json()
                assert preview['status'] == 'pending'
                assert preview['source_type'] == 'image'
                assert preview['filename'] == 'halaman-1.jpg, halaman-2.jpg'
                db = SessionLocal()
                assert db.query(StudentRecord).filter(StudentRecord.student_id == student_id).count() == 0
                db.close()
    finally:
            db = SessionLocal()
            db.query(KhsDocument).filter(KhsDocument.student_id == student_id).delete()
            db.query(AuditLog).filter(AuditLog.actor_id == student_id).delete(
                synchronize_session=False,
            )
            db.query(User).filter(User.id == student_id).delete()
            db.commit()
            db.close()
