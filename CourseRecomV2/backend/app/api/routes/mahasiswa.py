import hashlib
import json
from pathlib import PurePath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db, require_roles
from app.models import Course, KhsDocument, KrsDocument, OfficialKrsDocument, StudentRecord, StudyPlan, User, KprsRequest
from app.schemas import KhsConfirm, ProfileUpdate, RecommendationItem, StudyPlanSubmit, StudyPlanUpdate, KprsMutation
from app.services.khs_parser import (
    GRADE_POINTS,
    deduplicate_course_entries,
    parse_khs_images,
    parse_khs_pdf,
)
from app.services.recommendation import PASSING_GRADES, _passed, build_recommendation_result
from app.services.academic import earned_credits, latest_attempt_gpa, validate_course_selection
from app.services.capacity import (
    CapacityError,
    assert_course_capacity,
    begin_capacity_transaction,
    lock_capacity_courses,
)
from app.services.validation import assert_kprs_period_open, assert_krs_period_open, get_sks_quota
from app.services.official_krs import (
    build_official_krs_pdf,
    build_verification_url,
    create_verification_token,
    verify_token,
)
from app.services.audit import write_audit
from app.services.time_utils import utc_now_naive, WIB

router = APIRouter()
MAX_KHS_BYTES = 20 * 1024 * 1024
MAX_KHS_FILES = 10
MAX_KRS_BYTES = 10 * 1024 * 1024
KHS_IMAGE_EXTENSIONS = {'.bmp', '.jpeg', '.jpg', '.png', '.tif', '.tiff', '.webp'}


@router.get('/mahasiswa/kurikulum')
def get_curriculum(
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    courses = (
        db.query(Course)
        .filter(Course.is_active.is_(True))
        .order_by(Course.semester, Course.code)
        .all()
    )
    curriculum = []
    for course in courses:
        offered_semesters = {
            int(value.strip())
            for value in (course.available_semesters or '').split(',')
            if value.strip().isdigit() and 1 <= int(value.strip()) <= 8
        }
        if not offered_semesters and 1 <= course.semester <= 8:
            offered_semesters.add(course.semester)
        if not offered_semesters:
            continue

        curriculum.append({
            'code': course.code,
            'name': course.name,
            'sks': course.sks,
            'semester': course.semester,
            'available_semesters': ','.join(
                str(semester) for semester in sorted(offered_semesters)
            ),
            'category': course.category,
            'description': course.description or '',
            'prerequisite_text': course.prerequisite_text or '',
            'prerequisite_codes': course.prerequisite_codes or '',
            'day': course.day or '',
            'time': course.time or '',
        })
    return curriculum


def _serialize_document(document: KhsDocument) -> dict:
    data = json.loads(document.parsed_data)
    return {
        'id': document.id,
        'filename': document.filename,
        'status': document.status,
        'created_at': document.created_at.isoformat(),
        **data,
    }


@router.post('/mahasiswa/khs/preview')
async def preview_khs(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    uploads = files or ([file] if file else [])
    if not uploads:
        raise HTTPException(status_code=422, detail='Pilih satu PDF atau satu sampai sepuluh gambar KHS.')
    if len(uploads) > MAX_KHS_FILES:
        raise HTTPException(status_code=413, detail='Unggah maksimal 10 gambar halaman KHS sekaligus.')

    filenames = [PurePath(upload.filename or 'khs').name for upload in uploads]
    extensions = [PurePath(name).suffix.lower() for name in filenames]
    is_pdf = extensions == ['.pdf']
    if not is_pdf and (
        any(extension not in KHS_IMAGE_EXTENSIONS for extension in extensions)
        or any(extension == '.pdf' for extension in extensions)
    ):
        raise HTTPException(
            status_code=415,
            detail='Unggah satu PDF atau gambar JPG, PNG, WEBP, TIFF, atau BMP saja.',
        )

    contents = []
    total_size = 0
    for upload in uploads:
        content = await upload.read(MAX_KHS_BYTES - total_size + 1)
        total_size += len(content)
        if total_size > MAX_KHS_BYTES:
            raise HTTPException(status_code=413, detail='Total ukuran dokumen KHS maksimal 20 MB.')
        contents.append(content)

    try:
        parsed = parse_khs_pdf(contents[0]) if is_pdf else parse_khs_images(contents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    filename = ', '.join(filenames)[:255]
    parsed['metadata']['nim'] = parsed['metadata'].get('nim') or current_user.nim
    parsed['metadata']['full_name'] = parsed['metadata'].get('full_name') or current_user.full_name
    if not parsed['metadata'].get('program_study'):
        parsed['warnings'].append('Program studi tidak terbaca; periksa dan lengkapi sebelum konfirmasi.')
    if parsed['metadata']['nim'] != current_user.nim:
        parsed['warnings'].append('NIM hasil pembacaan berbeda dari akun; koreksi NIM sebelum konfirmasi.')

    document = KhsDocument(
        student_id=current_user.id,
        filename=filename[:255],
        sha256=hashlib.sha256(
            b''.join(len(content).to_bytes(8, 'big') + content for content in contents)
        ).hexdigest(),
        status='pending',
        parsed_data=json.dumps(parsed, ensure_ascii=False),
        content=b''.join(len(content).to_bytes(8, 'big') + content for content in contents),
        updated_at=utc_now_naive(),
        created_at=utc_now_naive(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return _serialize_document(document)


@router.get('/mahasiswa/khs')
def list_khs_documents(
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    documents = (
        db.query(KhsDocument)
        .filter(KhsDocument.student_id == current_user.id)
        .order_by(KhsDocument.created_at.desc(), KhsDocument.id.desc())
        .all()
    )
    return [_serialize_document(document) for document in documents]


@router.get('/mahasiswa/khs/{document_id}/file')
def download_khs_file(
    document_id: int,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    document = db.query(KhsDocument).filter(KhsDocument.id == document_id, KhsDocument.student_id == current_user.id).first()
    if not document or not document.content:
        raise HTTPException(status_code=404, detail='File KHS tidak tersedia.')
    return Response(
        content=document.content,
        media_type='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename="{document.filename}"'},
    )


@router.delete('/mahasiswa/khs/{document_id}')
def discard_khs_preview(
    document_id: int,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    document = (
        db.query(KhsDocument)
        .filter(
            KhsDocument.id == document_id,
            KhsDocument.student_id == current_user.id,
            KhsDocument.status == 'pending',
        )
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail='Pratinjau KHS tidak ditemukan atau sudah diproses.')
    db.delete(document)
    db.commit()
    return {'status': 'discarded'}


@router.post('/mahasiswa/khs/{document_id}/confirm')
def confirm_khs(
    document_id: int,
    payload: KhsConfirm,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    document = (
        db.query(KhsDocument)
        .filter(
            KhsDocument.id == document_id,
            KhsDocument.student_id == current_user.id,
            KhsDocument.status == 'pending',
        )
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail='Pratinjau KHS tidak ditemukan atau sudah dikonfirmasi.')
    if payload.nim.strip() != current_user.nim:
        raise HTTPException(status_code=422, detail='NIM KHS harus sama dengan NIM akun yang sedang masuk.')
    if not payload.full_name.strip():
        raise HTTPException(status_code=422, detail='Nama mahasiswa wajib diisi.')
    if not payload.courses:
        raise HTTPException(status_code=422, detail='KHS harus memiliki minimal satu mata kuliah.')

    cleaned_courses = []
    for course in payload.courses:
        code = course.code.strip().upper()
        grade = course.grade.strip().upper()
        if not code or not course.name.strip():
            raise HTTPException(status_code=422, detail='Kode dan nama mata kuliah wajib diisi.')
        if grade not in GRADE_POINTS:
            raise HTTPException(status_code=422, detail=f'Grade {grade} untuk {code} tidak dikenali.')
        if course.numeric_grade is not None and not 0 <= course.numeric_grade <= 100:
            raise HTTPException(status_code=422, detail=f'Nilai angka {code} harus berada di antara 0 dan 100.')
        cleaned_courses.append({
            'semester': course.semester,
            'code': code,
            'name': course.name.strip(),
            'sks': course.sks,
            'grade': grade,
            'numeric_grade': course.numeric_grade,
            'grade_point': GRADE_POINTS[grade],
        })

    parsed = json.loads(document.parsed_data)
    original_semesters = [
        int(item['semester']) for item in parsed.get('semesters', [])
        if str(item.get('semester', '')).isdigit()
    ]
    original_semester = int(
        parsed.get('metadata', {}).get('current_semester')
        or (max(original_semesters) if original_semesters else 0)
    )
    submitted_latest_semester = max(course['semester'] for course in cleaned_courses)
    if (
        payload.current_semester != original_semester
        or submitted_latest_semester > original_semester
    ):
        raise HTTPException(
            status_code=422,
            detail=f'Semester saat ini harus sama dengan semester terakhir dalam KHS ({original_semester}).',
        )

    cleaned_courses, _ = deduplicate_course_entries(cleaned_courses)
    seen = set()
    for course in cleaned_courses:
        key = (course['semester'], course['code'])
        if key in seen:
            raise HTTPException(
                status_code=422,
                detail=f'Mata kuliah {course["code"]} tercatat lebih dari sekali pada semester {course["semester"]}.',
            )
        seen.add(key)

    latest_semester = payload.current_semester
    parsed['metadata'] = {
        'nim': payload.nim.strip(),
        'full_name': payload.full_name.strip(),
        'program_study': payload.program_study.strip(),
        'current_semester': latest_semester,
        'ipk': payload.ipk,
    }
    parsed['courses'] = cleaned_courses
    old_semester_data = {
        item['semester']: item for item in parsed['semesters']
    }
    parsed['semesters'] = [
        {
            'semester': semester,
            'ip_semester': payload.ip_semesters.get(
                semester,
                old_semester_data.get(semester, {}).get('ip_semester'),
            ),
            'courses': [course for course in cleaned_courses if course['semester'] == semester],
        }
        for semester in sorted(
            set(old_semester_data)
            | {course['semester'] for course in cleaned_courses}
        )
    ]

    db.query(StudentRecord).filter(StudentRecord.student_id == current_user.id).delete()
    db.query(KhsDocument).filter(
        KhsDocument.student_id == current_user.id,
        KhsDocument.status == 'confirmed',
    ).update({'status': 'superseded'}, synchronize_session=False)

    for course in cleaned_courses:
        db.add(StudentRecord(
            student_id=current_user.id,
            course_code=course['code'],
            course_name=course['name'],
            semester=course['semester'],
            sks=course['sks'],
            grade=course['grade'],
            numeric_grade=course['numeric_grade'],
            grade_point=course['grade_point'],
            is_passed=course['grade'] in PASSING_GRADES,
        ))
    document.parsed_data = json.dumps(parsed, ensure_ascii=False)
    document.status = 'confirmed'
    document.updated_at = utc_now_naive()
    current_user.semester = latest_semester
    current_user.full_name = payload.full_name.strip()
    if payload.ipk is not None:
        current_user.ipk = payload.ipk
    current_user.sks_lulus = earned_credits(cleaned_courses, PASSING_GRADES)
    current_user.sks_sisa = max(settings.total_curriculum_sks - current_user.sks_lulus, 0)
    if payload.ipk is None:
        current_user.ipk = latest_attempt_gpa(cleaned_courses)
    current_user.kuota_sks = get_sks_quota(current_user.ipk, db)
    db.commit()
    db.refresh(document)
    return {'status': 'confirmed', 'document': _serialize_document(document)}


@router.get('/mahasiswa/profil')
def get_profile(
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    records = db.query(StudentRecord).filter(StudentRecord.student_id == current_user.id).all()
    latest = (
        db.query(KhsDocument)
        .filter(KhsDocument.student_id == current_user.id, KhsDocument.status == 'confirmed')
        .order_by(KhsDocument.created_at.desc(), KhsDocument.id.desc())
        .first()
    )
    parsed = json.loads(latest.parsed_data) if latest else {}
    metadata = parsed.get('metadata', {})
    passed = [record for record in records if _passed(record)]
    passed_courses = {record.course_code for record in passed}
    latest_attempts = {}
    for record in records:
        if record.course_code not in latest_attempts or (record.semester or 0) > (latest_attempts[record.course_code].semester or 0):
            latest_attempts[record.course_code] = record
    failed_courses = {code for code, record in latest_attempts.items() if not _passed(record)}
    total_sks = earned_credits([
        {
            'code': record.course_code,
            'grade': record.grade,
            'sks': record.sks or 0,
        }
        for record in records
    ], PASSING_GRADES)
    advisor = db.query(User).filter(User.id == current_user.advisor_id, User.role == 'dosen').first() if current_user.advisor_id else None
    return {
        'nim': current_user.nim,
        'full_name': current_user.full_name,
        'program_study': metadata.get('program_study', ''),
        'semester': metadata.get('current_semester'),
        'ipk': metadata.get('ipk') if metadata.get('ipk') is not None else current_user.ipk,
        'sks_lulus': total_sks,
        'sks_sisa': max(settings.total_curriculum_sks - total_sks, 0) if latest else None,
        'kuota_sks': get_sks_quota(
            metadata.get('ipk') if metadata.get('ipk') is not None else current_user.ipk,
            db,
        ),
        'interests': current_user.interests,
        'advisor': {
            'nim': advisor.nim,
            'full_name': advisor.full_name,
            'email': advisor.email,
        } if advisor else None,
        'total_sks': total_sks,
        'passed_courses': len(passed_courses),
        'failed_courses': len(failed_courses),
        'taken_courses': [
            {
                'semester': record.semester,
                'code': record.course_code,
                'name': record.course_name,
                'sks': record.sks,
                'grade': record.grade,
                'numeric_grade': record.numeric_grade,
                'grade_point': record.grade_point,
                'passed': _passed(record),
            }
            for record in sorted(records, key=lambda item: (item.semester or 0, item.course_code))
        ],
        'not_taken_course_codes': sorted(
            {code for (code,) in db.query(Course.code).filter(Course.is_active.is_(True)).all()}
            - {record.course_code for record in records}
        ),
        'khs_confirmed': latest is not None,
    }


@router.put('/mahasiswa/profil')
def update_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    current_user.interests = payload.interests
    db.commit()
    return {'status': 'updated', 'interests': payload.interests}


@router.get('/mahasiswa/rekomendasi')
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('mahasiswa')),
):
    return build_recommendation_result(db, current_user)


def _serialize_study_plan(plan: StudyPlan) -> dict:
    return {
        'id': plan.id,
        'semester': plan.semester,
        'courses': json.loads(plan.courses_json),
        'status': plan.status,
        'advisor_note': plan.advisor_note,
        'created_at': plan.created_at.isoformat(),
        'updated_at': plan.updated_at.isoformat(),
    }


def _owned_study_plan(db: Session, plan_id: int, student_id: int) -> StudyPlan:
    plan = db.query(StudyPlan).filter(
        StudyPlan.id == plan_id,
        StudyPlan.student_id == student_id,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail='Rencana studi tidak ditemukan.')
    return plan


@router.get('/mahasiswa/rencana-studi')
def list_my_study_plans(
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    plans = (
        db.query(StudyPlan)
        .filter(StudyPlan.student_id == current_user.id)
        .order_by(StudyPlan.created_at.desc(), StudyPlan.id.desc())
        .all()
    )
    return [_serialize_study_plan(plan) for plan in plans]


@router.get('/mahasiswa/rencana-studi/{plan_id}')
def get_my_study_plan(
    plan_id: int,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    return _serialize_study_plan(_owned_study_plan(db, plan_id, current_user.id))


@router.patch('/mahasiswa/rencana-studi/{plan_id}')
def update_my_study_plan(
    plan_id: int,
    payload: StudyPlanUpdate,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    begin_capacity_transaction(db)
    plan = _owned_study_plan(db, plan_id, current_user.id)
    if plan.status == 'approved':
        raise HTTPException(status_code=409, detail='KRS yang sudah disetujui terkunci.')
    if plan.status not in {'draft', 'revision_requested'}:
        raise HTTPException(status_code=409, detail='KRS yang sedang menunggu persetujuan tidak dapat diubah.')

    try:
        courses = validate_course_selection(db, current_user, payload.course_codes, plan.semester)
        lock_capacity_courses(db, [course['code'] for course in courses])
        assert_course_capacity(db, courses)
    except CapacityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    plan.courses_json = json.dumps(courses, ensure_ascii=False)
    plan.status = 'draft'
    plan.updated_at = utc_now_naive()
    db.commit()
    db.refresh(plan)
    return _serialize_study_plan(plan)


@router.post('/mahasiswa/kprs', status_code=status.HTTP_201_CREATED)
def submit_kprs(payload: KprsMutation, current_user: User = Depends(require_roles('mahasiswa')), db: Session = Depends(get_db)):
    begin_capacity_transaction(db)
    original = (
        db.query(StudyPlan)
        .with_for_update()
        .filter(
            StudyPlan.id == payload.study_plan_id,
            StudyPlan.student_id == current_user.id,
            StudyPlan.status == 'approved',
        )
        .first()
    )
    if not original:
        raise HTTPException(status_code=404, detail='KRS approved tidak ditemukan.')
    try:
        assert_kprs_period_open(db)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if db.query(KprsRequest).filter(
        KprsRequest.student_id == current_user.id,
        KprsRequest.status == 'pending',
    ).first():
        raise HTTPException(status_code=409, detail='Masih ada pengajuan KPRS aktif.')
    before = json.loads(original.courses_json)
    codes = [code.strip().upper() for code in payload.course_codes]
    if {item.get('code') for item in before} == set(codes):
        raise HTTPException(status_code=422, detail='Perubahan KPRS harus berbeda dari KRS sebelumnya.')
    try:
        courses = validate_course_selection(db, current_user, codes, original.semester)
        lock_capacity_courses(db, [course['code'] for course in courses])
        assert_course_capacity(db, courses, exclude_plan_id=original.id)
    except CapacityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    now = utc_now_naive()
    request = KprsRequest(
        student_id=current_user.id,
        study_plan_id=original.id,
        before_json=json.dumps(before, ensure_ascii=False),
        after_json=json.dumps(courses, ensure_ascii=False),
        reason=payload.reason,
        status='pending',
        created_at=now,
        updated_at=now,
    )
    db.add(request)
    write_audit(db, current_user, 'kprs_submitted', 'kprs_request', original.id, {'plan_id': original.id}, {'reason': payload.reason})
    db.commit()
    db.refresh(request)
    return {'id': request.id, 'status': request.status, 'before': before, 'after': courses}


@router.get('/mahasiswa/kprs')
def list_kprs(current_user: User = Depends(require_roles('mahasiswa')), db: Session = Depends(get_db)):
    return [{
        'id': item.id,
        'study_plan_id': item.study_plan_id,
        'before': json.loads(item.before_json),
        'after': json.loads(item.after_json),
        'reason': item.reason,
        'status': item.status,
        'reviewer_note': item.reviewer_note,
        'created_at': item.created_at.isoformat(),
        'updated_at': item.updated_at.isoformat(),
    } for item in db.query(KprsRequest).filter(KprsRequest.student_id == current_user.id).order_by(KprsRequest.created_at.desc()).all()]


@router.delete('/mahasiswa/kprs/{request_id}', status_code=status.HTTP_204_NO_CONTENT)
def cancel_kprs(
    request_id: int,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    begin_capacity_transaction(db)
    request = db.query(KprsRequest).filter(
        KprsRequest.id == request_id,
        KprsRequest.student_id == current_user.id,
        KprsRequest.status == 'pending',
    ).with_for_update().first()
    if not request:
        raise HTTPException(status_code=404, detail='Pengajuan KPRS pending tidak ditemukan.')
    request.status = 'cancelled'
    request.updated_at = utc_now_naive()
    write_audit(
        db,
        current_user,
        'kprs_cancelled',
        'kprs_request',
        request.id,
        {'status': 'pending'},
        {'status': 'cancelled'},
    )
    db.commit()


@router.post('/mahasiswa/rencana-studi/{plan_id}/submit')
def resubmit_my_study_plan(
    plan_id: int,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    begin_capacity_transaction(db)
    try:
        assert_krs_period_open(db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    plan = (
        db.query(StudyPlan)
        .with_for_update()
        .filter(StudyPlan.id == plan_id, StudyPlan.student_id == current_user.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail='Rencana studi tidak ditemukan.')
    if plan.status not in {'draft', 'revision_requested'}:
        raise HTTPException(status_code=409, detail='KRS hanya dapat diajukan dari draft atau revisi.')
    if current_user.advisor_id is None:
        raise HTTPException(status_code=409, detail='Mahasiswa belum memiliki Dosen Pembimbing Akademik.')
    if db.query(StudyPlan).filter(
        StudyPlan.student_id == current_user.id,
        StudyPlan.status == 'pending',
        StudyPlan.id != plan.id,
    ).first():
        raise HTTPException(status_code=409, detail='Masih ada KRS menunggu persetujuan.')
    try:
        courses = validate_course_selection(
            db,
            current_user,
            [item['code'] for item in json.loads(plan.courses_json)],
            plan.semester,
        )
        lock_capacity_courses(db, [course['code'] for course in courses])
        assert_course_capacity(db, courses)
    except CapacityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=f'KRS tidak lagi valid: {exc}') from exc
    plan.status = 'pending'
    plan.advisor_note = ''
    plan.updated_at = utc_now_naive()
    db.commit()
    db.refresh(plan)
    return _serialize_study_plan(plan)


@router.delete('/mahasiswa/rencana-studi/{plan_id}', status_code=204)
def delete_my_study_plan(
    plan_id: int,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    plan = _owned_study_plan(db, plan_id, current_user.id)
    if plan.status not in {'draft', 'revision_requested'}:
        raise HTTPException(status_code=409, detail='KRS draft atau hasil revisi saja yang dapat dihapus.')
    db.query(KrsDocument).filter(KrsDocument.study_plan_id == plan.id).delete(synchronize_session=False)
    db.delete(plan)
    db.commit()


@router.post('/mahasiswa/krs/dokumen', status_code=status.HTTP_201_CREATED)
async def upload_krs_document(
    file: UploadFile = File(...),
    plan_id: int | None = Form(None),
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    filename = PurePath(file.filename or 'rencana-studi.pdf').name
    if not filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=415, detail='Dokumen KRS harus berformat PDF.')
    content = await file.read(MAX_KRS_BYTES + 1)
    if len(content) > MAX_KRS_BYTES:
        raise HTTPException(status_code=413, detail='Dokumen KRS maksimal 10 MB.')
    if len(content) < 5 or not content.startswith(b'%PDF-'):
        raise HTTPException(status_code=422, detail='Isi berkas bukan PDF yang valid.')
    if plan_id is not None:
        _owned_study_plan(db, plan_id, current_user.id)

    document = KrsDocument(
        student_id=current_user.id,
        study_plan_id=plan_id,
        filename=filename[:255],
        content_type='application/pdf',
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
        content=content,
        created_at=utc_now_naive(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return {
        'id': document.id,
        'filename': document.filename,
        'size': document.size,
        'sha256': document.sha256,
        'created_at': document.created_at.isoformat(),
    }


@router.get('/mahasiswa/krs/dokumen/{document_id}')
def download_my_krs_document(
    document_id: int,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    document = db.query(KrsDocument).filter(
        KrsDocument.id == document_id,
        KrsDocument.student_id == current_user.id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail='Dokumen KRS tidak ditemukan.')
    return Response(
        content=document.content,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{document.filename}"'},
    )


@router.delete('/mahasiswa/krs/dokumen/{document_id}', status_code=204)
def delete_my_krs_document(
    document_id: int,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    document = db.query(KrsDocument).filter(
        KrsDocument.id == document_id,
        KrsDocument.student_id == current_user.id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail='Dokumen KRS tidak ditemukan.')
    if document.study_plan_id:
        plan = db.query(StudyPlan).filter(StudyPlan.id == document.study_plan_id).first()
        if plan and plan.status == 'approved':
            raise HTTPException(status_code=409, detail='Dokumen KRS yang sudah disetujui tidak dapat dihapus.')
    db.delete(document)
    db.commit()


@router.post('/mahasiswa/rencana-studi', status_code=status.HTTP_201_CREATED)
def submit_study_plan(
    payload: StudyPlanSubmit,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    begin_capacity_transaction(db)
    try:
        assert_krs_period_open(db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if current_user.advisor_id is None:
        raise HTTPException(status_code=409, detail='Mahasiswa belum memiliki Dosen Pembimbing Akademik.')
    if db.query(StudyPlan).filter(
        StudyPlan.student_id == current_user.id,
        StudyPlan.status == 'pending',
    ).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Rencana studi masih menunggu review dosen PA.',
        )

    result = build_recommendation_result(db, current_user)
    if result['status'] != 'ready':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result['message'])
    approved_plan = db.query(StudyPlan).filter(
        StudyPlan.student_id == current_user.id,
        StudyPlan.semester == result['target_semester'],
        StudyPlan.status == 'approved',
    ).first()
    if approved_plan:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='KRS sudah disetujui dan tidak dapat diubah.',
        )
    try:
        courses = validate_course_selection(
            db,
            current_user,
            payload.course_codes,
            result['target_semester'],
        )
        lock_capacity_courses(db, [course['code'] for course in courses])
        assert_course_capacity(db, courses)
    except CapacityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    now = utc_now_naive()
    plan = StudyPlan(
        student_id=current_user.id,
        semester=result['target_semester'],
        courses_json=json.dumps(courses, ensure_ascii=False),
        status='pending',
        advisor_note='',
        created_at=now,
        updated_at=now,
    )
    db.add(plan)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Rencana studi masih menunggu review dosen PA.',
        ) from exc
    db.refresh(plan)
    return _serialize_study_plan(plan)


@router.get('/rekomendasi', response_model=list[RecommendationItem])
def list_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('mahasiswa')),
):
    result = build_recommendation_result(db, current_user)
    return result['recommendations']


@router.get('/mahasiswa/rencana-studi/{plan_id}/pdf-resmi')
def download_official_krs(
    plan_id: int,
    request: Request,
    current_user: User = Depends(require_roles('mahasiswa')),
    db: Session = Depends(get_db),
):
    plan = _owned_study_plan(db, plan_id, current_user.id)
    if plan.status != 'approved':
        raise HTTPException(status_code=409, detail='PDF resmi hanya tersedia setelah KRS disetujui.')

    issued = db.query(OfficialKrsDocument).filter(
        OfficialKrsDocument.study_plan_id == plan.id
    ).first()
    courses = json.loads(plan.courses_json)
    canonical = json.dumps({
        'plan_id': plan.id,
        'student_id': current_user.id,
        'status': plan.status,
        'semester': plan.semester,
        'courses': courses,
    }, sort_keys=True, separators=(',', ':'))
    canonical_hash = hashlib.sha256(canonical.encode()).hexdigest()
    if issued:
        payload = verify_token(issued.verification_token)
        if (
            payload is None
            or payload.get('sha256') != canonical_hash
            or issued.sha256 != hashlib.sha256(issued.content).hexdigest()
        ):
            db.delete(issued)
            db.commit()
            issued = None
    if issued:
        return Response(content=issued.content, media_type='application/pdf', headers={
            'Content-Disposition': f'attachment; filename="KRS-{current_user.nim}-{plan.id}.pdf"',
            'X-Document-SHA256': issued.sha256,
        })

    token = create_verification_token(plan.id, current_user.id, canonical_hash)
    try:
        verification_url = build_verification_url(str(request.base_url), token)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    content, content_hash = build_official_krs_pdf(
        current_user.nim,
        current_user.full_name,
        plan.id,
        plan.semester,
        courses,
        verification_url,
    )
    issued = OfficialKrsDocument(
        study_plan_id=plan.id,
        student_id=current_user.id,
        sha256=content_hash,
        verification_token=token,
        content=content,
        issued_at=utc_now_naive(),
    )
    db.add(issued)
    write_audit(db, current_user, 'official_krs_issued', 'study_plan', plan.id, None, {'sha256': content_hash})
    db.commit()
    return Response(content=content, media_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="KRS-{current_user.nim}-{plan.id}.pdf"',
        'X-Document-SHA256': content_hash,
    })


@router.get('/krs/verify/{token}')
def verify_official_krs(token: str, db: Session = Depends(get_db)):
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=404, detail='Kode verifikasi tidak valid.')
    plan = db.query(StudyPlan).filter(StudyPlan.id == payload['plan']).first()
    issued = db.query(OfficialKrsDocument).filter(
        OfficialKrsDocument.study_plan_id == payload['plan'],
        OfficialKrsDocument.verification_token == token,
    ).first()
    if not plan or plan.status != 'approved' or not issued or plan.student_id != payload['student']:
        raise HTTPException(status_code=404, detail='Dokumen KRS tidak valid atau sudah tidak aktif.')
    if not _official_krs_is_current(plan, issued, payload):
        raise HTTPException(status_code=404, detail='Dokumen KRS sudah tidak merupakan versi terbaru.')
    return {
        'valid': True,
        'plan_id': plan.id,
        'status': plan.status,
        'document_sha256': issued.sha256,
        'issued_at': issued.issued_at.isoformat(),
    }


@router.post('/krs/verify/{token}/document')
async def verify_official_krs_document(
    token: str,
    document: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=404, detail='Kode verifikasi tidak valid.')
    issued = db.query(OfficialKrsDocument).filter(
        OfficialKrsDocument.study_plan_id == payload['plan'],
        OfficialKrsDocument.verification_token == token,
    ).first()
    plan = db.query(StudyPlan).filter(StudyPlan.id == payload['plan']).first()
    if not issued or not plan or plan.status != 'approved' or plan.student_id != payload['student']:
        raise HTTPException(status_code=404, detail='Dokumen KRS tidak valid atau sudah tidak aktif.')
    if not _official_krs_is_current(plan, issued, payload):
        raise HTTPException(status_code=404, detail='Dokumen KRS sudah tidak merupakan versi terbaru.')

    content = await document.read(MAX_KRS_BYTES + 1)
    if len(content) > MAX_KRS_BYTES:
        raise HTTPException(status_code=413, detail='Ukuran dokumen melebihi batas yang diizinkan.')
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != issued.sha256 or actual_hash != hashlib.sha256(issued.content).hexdigest():
        return {'valid': False, 'document_sha256': actual_hash}
    return {'valid': True, 'document_sha256': actual_hash}


def _official_krs_is_current(plan: StudyPlan, issued: OfficialKrsDocument, payload: dict) -> bool:
    if (
        payload.get('plan') != plan.id
        or payload.get('student') != plan.student_id
        or payload.get('sha256') is None
    ):
        return False
    canonical = json.dumps({
        'plan_id': plan.id,
        'student_id': plan.student_id,
        'status': plan.status,
        'semester': plan.semester,
        'courses': json.loads(plan.courses_json),
    }, sort_keys=True, separators=(',', ':'))
    return (
        payload['sha256'] == hashlib.sha256(canonical.encode()).hexdigest()
        and issued.sha256 == hashlib.sha256(issued.content).hexdigest()
    )
