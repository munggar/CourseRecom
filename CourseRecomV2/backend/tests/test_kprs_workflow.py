import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import create_access_token, get_password_hash
from app.main import app
from app.models import AuditLog, Course, KhsDocument, KprsRequest, StudentRecord, StudyPlan, SystemSetting, User


def test_kprs_revalidates_reserves_capacity_and_releases_cancelled_seats():
    suffix = uuid4().hex[:8].upper()
    advisor_nim = 'ADV' + suffix
    student_a_nim = 'KPA' + suffix
    student_b_nim = 'KPB' + suffix
    original_code = 'KP' + suffix + 'A'
    replacement_code = 'KP' + suffix + 'B'
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    advisor = User(
        nim=advisor_nim,
        full_name='Dosen KPRS Uji',
        role='dosen',
        password_hash=get_password_hash('advisor-password'),
    )
    student_a = User(
        nim=student_a_nim,
        full_name='Mahasiswa KPRS A',
        role='mahasiswa',
        password_hash=get_password_hash('student-password'),
        semester=2,
        ipk=3.2,
    )
    student_b = User(
        nim=student_b_nim,
        full_name='Mahasiswa KPRS B',
        role='mahasiswa',
        password_hash=get_password_hash('student-password'),
        semester=2,
        ipk=3.2,
    )
    db.add_all([advisor, student_a, student_b])
    db.flush()
    student_a.advisor_id = advisor.id
    student_b.advisor_id = advisor.id
    db.add_all([
        Course(
            code=original_code,
            name='Mata Kuliah Awal',
            sks=3,
            semester=3,
            available_semesters='3',
            category='Wajib',
            capacity=40,
            is_active=True,
        ),
        Course(
            code=replacement_code,
            name='Mata Kuliah Pengganti',
            sks=3,
            semester=3,
            available_semesters='3',
            category='Wajib',
            capacity=1,
            prerequisite_codes='',
            is_active=True,
        ),
    ])
    for student in (student_a, student_b):
        db.add(KhsDocument(
            student_id=student.id,
            filename='riwayat.json',
            sha256=uuid4().hex * 2,
            status='confirmed',
            parsed_data='{"metadata":{"current_semester":2,"ipk":3.2}}',
            created_at=now,
            updated_at=now,
        ))
    original_plan = StudyPlan(
        student_id=student_a.id,
        semester=3,
        courses_json=json.dumps([{
            'code': original_code,
            'name': 'Mata Kuliah Awal',
            'sks': 3,
        }]),
        status='approved',
        advisor_note='',
        created_at=now,
        updated_at=now,
    )
    db.add(original_plan)
    start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    db.add_all([
        SystemSetting(key='kprs_period_start', value=start, updated_at=now),
        SystemSetting(key='kprs_period_end', value=end, updated_at=now),
    ])
    db.commit()
    student_a_id = student_a.id
    student_b_id = student_b.id
    plan_id = original_plan.id
    advisor_id = advisor.id
    db.close()

    client = TestClient(app)
    student_a_headers = {
        'Authorization': 'Bearer ' + create_access_token(student_a_nim, 'mahasiswa'),
    }
    student_b_headers = {
        'Authorization': 'Bearer ' + create_access_token(student_b_nim, 'mahasiswa'),
    }
    advisor_headers = {
        'Authorization': 'Bearer ' + create_access_token(advisor_nim, 'dosen'),
    }

    try:
        submitted = client.post(
            '/api/mahasiswa/kprs',
            headers=student_a_headers,
            json={
                'study_plan_id': plan_id,
                'course_codes': [replacement_code],
                'reason': 'Perubahan jadwal kuliah',
            },
        )
        assert submitted.status_code == 201, submitted.text
        request_id = submitted.json()['id']

        db = SessionLocal()
        replacement = db.query(Course).filter(Course.code == replacement_code).one()
        replacement.prerequisite_codes = 'NOTPASSED'
        db.commit()
        db.close()
        stale_approval = client.put(
            f'/api/dosen/kprs/{request_id}',
            headers=advisor_headers,
            json={'status': 'approved', 'note': 'Perlu validasi ulang.'},
        )
        assert stale_approval.status_code == 409

        db = SessionLocal()
        replacement = db.query(Course).filter(Course.code == replacement_code).one()
        replacement.prerequisite_codes = ''
        db.commit()
        db.close()
        while_reserved = client.post(
            '/api/mahasiswa/rencana-studi',
            headers=student_b_headers,
            json={'course_codes': [replacement_code]},
        )
        assert while_reserved.status_code == 409

        cancelled = client.delete(
            f'/api/mahasiswa/kprs/{request_id}',
            headers=student_a_headers,
        )
        assert cancelled.status_code == 204
        student_b_plan = client.post(
            '/api/mahasiswa/rencana-studi',
            headers=student_b_headers,
            json={'course_codes': [replacement_code]},
        )
        assert student_b_plan.status_code == 201, student_b_plan.text
        student_b_plan_id = student_b_plan.json()['id']

        revision = client.patch(
            f'/api/dosen/rencana-studi/{student_b_plan_id}',
            headers=advisor_headers,
            json={'status': 'revision_requested', 'advisor_note': 'Perbarui pilihan mata kuliah.'},
        )
        assert revision.status_code == 200
        second_request = client.post(
            '/api/mahasiswa/kprs',
            headers=student_a_headers,
            json={
                'study_plan_id': plan_id,
                'course_codes': [replacement_code],
                'reason': 'Perubahan jadwal kuliah',
            },
        )
        assert second_request.status_code == 201, second_request.text
        approved = client.put(
            f"/api/dosen/kprs/{second_request.json()['id']}",
            headers=advisor_headers,
            json={'status': 'approved', 'note': 'Validasi akademik lolos.'},
        )
        assert approved.status_code == 200, approved.text

        db = SessionLocal()
        updated_plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id).one()
        updated_request = db.query(KprsRequest).filter(
            KprsRequest.id == second_request.json()['id'],
        ).one()
        assert updated_plan.status == 'approved'
        assert json.loads(updated_plan.courses_json)[0]['code'] == replacement_code
        assert updated_request.status == 'approved'
        db.close()
    finally:
        db = SessionLocal()
        student_ids = [student_a_id, student_b_id]
        plan_ids = [
            item[0] for item in db.query(StudyPlan.id).filter(
                StudyPlan.student_id.in_(student_ids),
            ).all()
        ]
        db.query(KprsRequest).filter(
            KprsRequest.study_plan_id.in_(plan_ids),
        ).delete(synchronize_session=False)
        db.query(StudyPlan).filter(StudyPlan.id.in_(plan_ids)).delete(synchronize_session=False)
        db.query(KhsDocument).filter(KhsDocument.student_id.in_(student_ids)).delete(synchronize_session=False)
        db.query(StudentRecord).filter(StudentRecord.student_id.in_(student_ids)).delete(synchronize_session=False)
        db.query(AuditLog).filter(
            AuditLog.actor_id.in_([*student_ids, advisor_id]),
        ).delete(synchronize_session=False)
        db.query(SystemSetting).filter(SystemSetting.key.in_([
            'kprs_period_start',
            'kprs_period_end',
        ])).delete(synchronize_session=False)
        db.query(Course).filter(Course.code.in_([original_code, replacement_code])).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_([*student_ids, advisor_id])).delete(synchronize_session=False)
        db.commit()
        db.close()
