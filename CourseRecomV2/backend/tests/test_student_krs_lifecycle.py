import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.deps import create_access_token, get_password_hash
from app.main import app
from app.models import (
    AuditLog,
    Course,
    KhsDocument,
    OfficialKrsDocument,
    StudentRecord,
    StudyPlan,
    SystemSetting,
    User,
)


def test_student_can_submit_krs_and_receive_official_pdf_after_advisor_approval(monkeypatch):
    suffix = uuid4().hex[:8].upper()
    student_nim = f'E2ESTU{suffix}'
    advisor_nim = f'E2EDOS{suffix}'
    mandatory_code = f'E2E{suffix}01'
    previous_code = f'E2E{suffix}PRE'
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()

    advisor = User(
        nim=advisor_nim,
        username=advisor_nim.casefold(),
        full_name='Dosen PA E2E Uji',
        role='dosen',
        password_hash=get_password_hash('advisor-e2e-password'),
        is_active=True,
    )
    student = User(
        nim=student_nim,
        username=student_nim.casefold(),
        full_name='Mahasiswa E2E Uji',
        role='mahasiswa',
        password_hash=get_password_hash('student-e2e-password'),
        program_study='Sistem dan Teknologi Informasi',
        angkatan='2022',
        semester=1,
        ipk=3.5,
        sks_lulus=3,
        sks_sisa=141,
        kuota_sks=24,
        interests='Manajemen Teknologi Informasi',
        is_active=True,
    )
    course = Course(
        code=mandatory_code,
        name='Mata Kuliah Wajib Pengujian KRS',
        sks=3,
        semester=2,
        available_semesters='2',
        category='Wajib',
        description='Mata kuliah wajib untuk tes alur pengajuan KRS.',
        prerequisite_codes='',
        day='',
        time='',
        capacity=40,
        is_active=True,
    )
    try:
        db.add_all([advisor, student, course])
        db.flush()
        student.advisor_id = advisor.id
        db.add(StudentRecord(
            student_id=student.id,
            course_code=previous_code,
            course_name='Mata Kuliah Prasyarat yang Sudah Lulus',
            grade='A',
            semester=1,
            sks=3,
            numeric_grade=90,
            grade_point=4.0,
            is_passed=True,
        ))
        parsed = {
            'metadata': {
                'nim': student_nim,
                'full_name': student.full_name,
                'program_study': student.program_study,
                'current_semester': 1,
                'ipk': 3.5,
            },
            'semesters': [
                {
                    'semester': 1,
                    'ip_semester': 3.5,
                    'courses': [
                        {
                            'semester': 1,
                            'code': previous_code,
                            'name': 'Mata Kuliah Prasyarat yang Sudah Lulus',
                            'sks': 3,
                            'grade': 'A',
                            'numeric_grade': 90,
                            'grade_point': 4,
                        }
                    ],
                }
            ],
        }
        db.add(KhsDocument(
            student_id=student.id,
            filename='khs-e2e.json',
            sha256=uuid4().hex * 2,
            status='confirmed',
            parsed_data=json.dumps(parsed, ensure_ascii=False),
            content=None,
            created_at=now,
            updated_at=now,
        ))

        start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        setting_values = {
            'krs_period_start': start,
            'krs_period_end': end,
            'krs_fill_deadline': end,
            'active_academic_year': '2026/2027',
        }
        previous_settings = {
            key: db.query(SystemSetting).filter(SystemSetting.key == key).first()
            for key in setting_values
        }
        old_setting_values = {
            key: row.value if row else None
            for key, row in previous_settings.items()
        }
        for key, value in setting_values.items():
            row = previous_settings[key]
            if row:
                row.value = value
                row.updated_at = now
            else:
                db.add(SystemSetting(key=key, value=value, updated_at=now))
        db.commit()

        student_id = student.id
        advisor_id = advisor.id
        db.close()

        monkeypatch.setattr(settings, 'public_api_base_url', 'https://api.example.edu/api')
        client = TestClient(app)
        student_headers = {
            'Authorization': 'Bearer ' + create_access_token(student_nim, 'mahasiswa'),
        }
        advisor_headers = {
            'Authorization': 'Bearer ' + create_access_token(advisor_nim, 'dosen'),
        }

        try:
            recommendations = client.get('/api/mahasiswa/rekomendasi', headers=student_headers)
            assert recommendations.status_code == 200, recommendations.text
            mandatory = next(
                item for item in recommendations.json()
                if item['code'] == mandatory_code
            )
            assert mandatory['mandatory'] is True

            submitted = client.post(
                '/api/mahasiswa/rencana-studi',
                headers=student_headers,
                json={'course_codes': [mandatory_code], 'class_selections': {}},
            )
            assert submitted.status_code == 201, submitted.text
            plan_id = submitted.json()['id']
            assert submitted.json()['status'] == 'pending'
            assert [item['code'] for item in submitted.json()['courses']] == [mandatory_code]

            # A Dosen PA from another account must not be able to review the plan.
            unauthorized_review = client.patch(
                f'/api/dosen/rencana-studi/{plan_id}',
                headers={'Authorization': 'Bearer ' + create_access_token('pa001', 'dosen')},
                json={'status': 'approved', 'advisor_note': ''},
            )
            assert unauthorized_review.status_code == 404

            approved = client.patch(
                f'/api/dosen/rencana-studi/{plan_id}',
                headers=advisor_headers,
                json={'status': 'approved', 'advisor_note': 'KRS telah diperiksa dan disetujui.'},
            )
            assert approved.status_code == 200, approved.text
            assert approved.json()['status'] == 'approved'

            official_pdf = client.get(
                f'/api/mahasiswa/rencana-studi/{plan_id}/pdf-resmi',
                headers=student_headers,
            )
            assert official_pdf.status_code == 200, official_pdf.text
            assert official_pdf.headers['content-type'].startswith('application/pdf')
            assert official_pdf.content.startswith(b'%PDF')

            db = SessionLocal()
            plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id).one()
            assert plan.status == 'approved'
            assert plan.reviewer_id == advisor_id
            issued = db.query(OfficialKrsDocument).filter(
                OfficialKrsDocument.study_plan_id == plan_id
            ).one()
            assert issued.content == official_pdf.content
            assert db.query(AuditLog).filter(
                AuditLog.actor_id == student_id,
                AuditLog.action == 'study_plan_submitted',
                AuditLog.entity_id == str(plan_id),
            ).first()
            db.close()
        finally:
            client.close()
    finally:
        cleanup = SessionLocal()
        cleanup.query(OfficialKrsDocument).filter(
            OfficialKrsDocument.study_plan_id.in_(
                cleanup.query(StudyPlan.id).filter(
                    StudyPlan.student_id == cleanup.query(User.id).filter(User.nim == student_nim).scalar_subquery()
                )
            )
        ).delete(synchronize_session=False)
        cleanup.query(StudyPlan).filter(
            StudyPlan.student_id == cleanup.query(User.id).filter(User.nim == student_nim).scalar_subquery()
        ).delete(synchronize_session=False)
        cleanup.query(KhsDocument).filter(
            KhsDocument.student_id == cleanup.query(User.id).filter(User.nim == student_nim).scalar_subquery()
        ).delete(synchronize_session=False)
        cleanup.query(StudentRecord).filter(
            StudentRecord.student_id == cleanup.query(User.id).filter(User.nim == student_nim).scalar_subquery()
        ).delete(synchronize_session=False)
        cleanup.query(Course).filter(Course.code == mandatory_code).delete(synchronize_session=False)
        cleanup.query(AuditLog).filter(
            AuditLog.actor_id.in_(
                cleanup.query(User.id).filter(User.nim.in_([student_nim, advisor_nim]))
            )
        ).delete(synchronize_session=False)
        cleanup.query(User).filter(User.nim.in_([student_nim, advisor_nim])).delete(synchronize_session=False)
        for key in ['krs_period_start', 'krs_period_end', 'krs_fill_deadline', 'active_academic_year']:
            row = cleanup.query(SystemSetting).filter(SystemSetting.key == key).first()
            if row:
                if old_setting_values.get(key) is None:
                    cleanup.delete(row)
                else:
                    row.value = old_setting_values[key]
                    row.updated_at = now
        cleanup.commit()
        cleanup.close()
