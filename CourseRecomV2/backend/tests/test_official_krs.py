import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.deps import get_password_hash
from app.main import app
from app.models import OfficialKrsDocument, StudyPlan, User
from app.services.official_krs import (
    build_official_krs_pdf,
    build_verification_url,
    create_verification_token,
    verify_token,
)


def test_official_krs_pdf_has_hmac_verified_qr_token():
    canonical_hash = hashlib.sha256(b'approved krs payload').hexdigest()
    token = create_verification_token(15, 3, canonical_hash)
    verified = verify_token(token)

    content, content_hash = build_official_krs_pdf(
        '2203001',
        'Mahasiswa Uji',
        15,
        5,
        [{'code': 'IF101', 'name': 'Pengujian', 'sks': 3}],
        'http://localhost/api/krs/verify/' + token,
    )

    assert verified['plan'] == 15
    assert verified['student'] == 3
    assert verified['sha256'] == canonical_hash
    assert verify_token(token + 'tampered') is None
    assert content.startswith(b'%PDF')
    assert hashlib.sha256(content).hexdigest() == content_hash


def test_verification_url_uses_configured_public_api_and_rejects_internal_hosts(monkeypatch):
    monkeypatch.setattr(settings, 'environment', 'testing')
    monkeypatch.setattr(settings, 'public_api_base_url', 'https://api.example.edu/api')
    assert build_verification_url('http://backend:8000/', 'signed-token') == (
        'https://api.example.edu/api/krs/verify/signed-token'
    )

    monkeypatch.setattr(settings, 'public_api_base_url', 'http://backend:8000/api')
    try:
        build_verification_url('http://localhost:8000/', 'signed-token')
    except ValueError as exc:
        assert 'internal' in str(exc)
    else:
        raise AssertionError('Internal Docker hostnames must not be used in QR URLs.')


def test_verification_url_does_not_fallback_to_localhost_in_production(monkeypatch):
    monkeypatch.setattr(settings, 'environment', 'production')
    monkeypatch.setattr(settings, 'public_api_base_url', '')

    try:
        build_verification_url('http://localhost:8000/', 'signed-token')
    except ValueError as exc:
        assert 'production' in str(exc)
    else:
        raise AssertionError('Production must not derive a localhost QR URL.')


def test_old_official_krs_is_rejected_after_plan_changes():
    suffix = uuid4().hex[:8].upper()
    student_nim = 'QR' + suffix
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    student = User(
        nim=student_nim,
        full_name='Mahasiswa Verifikasi',
        role='mahasiswa',
        password_hash=get_password_hash('student-password'),
    )
    db.add(student)
    db.flush()
    courses = [{'code': 'QR101', 'name': 'Mata Kuliah QR', 'sks': 3}]
    plan = StudyPlan(
        student_id=student.id,
        semester=3,
        courses_json=json.dumps(courses),
        status='approved',
        advisor_note='',
        created_at=now,
        updated_at=now,
    )
    db.add(plan)
    db.flush()
    canonical = json.dumps({
        'plan_id': plan.id,
        'student_id': student.id,
        'status': plan.status,
        'semester': plan.semester,
        'courses': courses,
    }, sort_keys=True, separators=(',', ':'))
    canonical_hash = hashlib.sha256(canonical.encode()).hexdigest()
    token = create_verification_token(plan.id, student.id, canonical_hash)
    content, content_hash = build_official_krs_pdf(
        student.nim,
        student.full_name,
        plan.id,
        plan.semester,
        courses,
        f'https://api.example.edu/api/krs/verify/{token}',
    )
    db.add(OfficialKrsDocument(
        study_plan_id=plan.id,
        student_id=student.id,
        sha256=content_hash,
        verification_token=token,
        content=content,
        issued_at=now,
    ))
    plan_id = plan.id
    student_id = student.id
    db.commit()
    plan.courses_json = json.dumps([
        {'code': 'QR102', 'name': 'Mata Kuliah Pengganti', 'sks': 3},
    ])
    db.commit()
    db.close()

    client = TestClient(app)
    try:
        verification = client.get(f'/api/krs/verify/{token}')
        assert verification.status_code == 404
        document_verification = client.post(
            f'/api/krs/verify/{token}/document',
            files={'document': ('KRS.pdf', content, 'application/pdf')},
        )
        assert document_verification.status_code == 404
    finally:
        db = SessionLocal()
        db.query(OfficialKrsDocument).filter(
            OfficialKrsDocument.study_plan_id == plan_id,
        ).delete(synchronize_session=False)
        db.query(StudyPlan).filter(StudyPlan.id == plan_id).delete(synchronize_session=False)
        db.query(User).filter(User.id == student_id).delete(synchronize_session=False)
        db.commit()
        db.close()
