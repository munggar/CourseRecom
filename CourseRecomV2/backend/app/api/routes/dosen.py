import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_db, require_roles
from app.models import AdvisorFeedback, Course, KhsDocument, KrsDocument, KprsRequest, StudyPlan, User
from fastapi.responses import Response
from app.schemas import KprsReview, StudyPlanReview
from app.services.academic import validate_course_selection
from app.services.audit import write_audit
from app.services.capacity import (
    assert_course_capacity,
    begin_capacity_transaction,
    lock_capacity_courses,
)
from app.services.time_utils import utc_now_naive
from app.services.recommendation import is_mandatory_course
from app.services.validation import assert_kprs_period_open, assert_krs_period_open

router = APIRouter()


@router.get('/dosen/mahasiswa')
def list_mentees(db: Session = Depends(get_db), current_user: User = Depends(require_roles('dosen', 'admin'))):
    student_query = db.query(User).filter(User.role == 'mahasiswa')
    if current_user.role == 'dosen':
        student_query = student_query.filter(User.advisor_id == current_user.id)
    students = (
        student_query
        .order_by(User.nim)
        .all()
    )
    confirmed_student_ids = {
        student_id
        for (student_id,) in db.query(KhsDocument.student_id)
        .filter(KhsDocument.status == 'confirmed')
        .distinct()
        .all()
    }
    return [
        {
            'nim': student.nim,
            'full_name': student.full_name,
            'program_study': student.program_study or '',
            'ipk': student.ipk,
            'interests': student.interests or '',
            'khs_confirmed': student.id in confirmed_student_ids,
        }
        for student in students
    ]


@router.get('/dosen/rencana-studi')
def list_study_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('dosen')),
):
    plans_query = (
        db.query(StudyPlan, User)
        .join(User, StudyPlan.student_id == User.id)
        .filter(User.role == 'mahasiswa')
        .filter(User.advisor_id == current_user.id)
    )
    plans = (
        plans_query
        .order_by(StudyPlan.created_at.desc(), StudyPlan.id.desc())
        .all()
    )
    return [
        {
            'id': plan.id,
            'student_nim': student.nim,
            'student_name': student.full_name,
            'student_program_study': student.program_study or '',
            'student_ipk': student.ipk,
            'student_interests': student.interests or '',
            'semester': plan.semester,
            'courses': json.loads(plan.courses_json),
            'status': plan.status,
            'advisor_note': plan.advisor_note,
            'advisor_feedback': [
                {
                    'id': feedback.id,
                    'note': feedback.note,
                    'affected_course_codes': json.loads(feedback.affected_course_codes_json),
                    'reason_category': feedback.reason_category,
                    'created_at': feedback.created_at.isoformat(),
                }
                for feedback in plan.advisor_feedback
            ],
            'created_at': plan.created_at.isoformat(),
            'updated_at': plan.updated_at.isoformat(),
        }
        for plan, student in plans
    ]


@router.patch('/dosen/rencana-studi/{plan_id}')
def review_study_plan(
    plan_id: int,
    payload: StudyPlanReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('dosen')),
):
    begin_capacity_transaction(db)
    plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id).with_for_update().first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Rencana studi tidak ditemukan.')
    if plan.status == 'approved':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Rencana studi yang sudah disetujui tidak dapat diubah.',
        )
    if plan.status != 'pending':
        raise HTTPException(status_code=409, detail='Hanya KRS berstatus pending yang dapat direview.')
    student = db.query(User).filter(
        User.id == plan.student_id,
        User.role == 'mahasiswa',
        User.advisor_id == current_user.id,
    ).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Rencana studi tidak ditemukan.')

    stored_courses = json.loads(plan.courses_json)
    stored_by_code = {
        str(item.get('code', '')).strip().upper(): item
        for item in stored_courses
        if item.get('code')
    }
    if payload.status == 'revision_requested':
        unknown_codes = set(payload.affected_course_codes) - set(stored_by_code)
        if unknown_codes:
            raise HTTPException(
                status_code=422,
                detail=f'Mata kuliah terkait tidak ada dalam KRS ini: {", ".join(sorted(unknown_codes))}.',
            )
        catalog_courses = {
            course.code: course
            for course in db.query(Course).filter(
                Course.code.in_(payload.affected_course_codes)
            ).all()
        } if payload.affected_course_codes else {}
        mandatory_codes = [
            code for code in payload.affected_course_codes
            if (
                (code in catalog_courses and is_mandatory_course(catalog_courses[code]))
                or stored_by_code[code].get('mandatory') is True
            )
        ]
        if mandatory_codes:
            raise HTTPException(
                status_code=422,
                detail='Mata kuliah wajib tidak dapat ditandai untuk diganti: ' + ', '.join(mandatory_codes),
            )

    if payload.status == 'approved':
        if payload.affected_course_codes:
            raise HTTPException(status_code=422, detail='Persetujuan tidak dapat memuat daftar mata kuliah yang ditolak.')
        try:
            assert_krs_period_open(db)
            courses = validate_course_selection(
                db,
                student,
                [item['code'] for item in stored_courses],
                plan.semester,
            )
            lock_capacity_courses(db, [course['code'] for course in courses])
            assert_course_capacity(db, courses, exclude_plan_id=plan.id)
        except (KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=f'KRS tidak lagi valid: {exc}') from exc
        plan.courses_json = json.dumps(courses, ensure_ascii=False)

    plan.status = payload.status
    plan.advisor_note = payload.advisor_note
    plan.reviewer_id = current_user.id
    plan.updated_at = utc_now_naive()
    if payload.status == 'revision_requested':
        db.add(AdvisorFeedback(
            student_id=student.id,
            study_plan_id=plan.id,
            reviewer_id=current_user.id,
            semester=plan.semester,
            affected_course_codes_json=json.dumps(payload.affected_course_codes, ensure_ascii=False),
            reason_category=payload.reason_category,
            note=payload.advisor_note,
            feedback_type='revision_requested',
            created_at=plan.updated_at,
        ))
    write_audit(
        db,
        current_user,
        'study_plan_review',
        'study_plan',
        plan.id,
        {'status': 'pending'},
        {
            'status': payload.status,
            'advisor_note': payload.advisor_note,
            'affected_course_codes': payload.affected_course_codes,
            'reason_category': payload.reason_category,
        },
    )
    db.commit()
    db.refresh(plan)
    return {
        'id': plan.id,
        'status': plan.status,
        'advisor_note': plan.advisor_note,
        'affected_course_codes': payload.affected_course_codes,
        'reason_category': payload.reason_category,
        'updated_at': plan.updated_at.isoformat(),
    }


@router.get('/dosen/krs/dokumen/{document_id}')
def download_mentee_krs_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('dosen')),
):
    document = db.query(KrsDocument).join(User, KrsDocument.student_id == User.id).filter(
        KrsDocument.id == document_id,
        User.advisor_id == current_user.id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail='Dokumen KRS tidak ditemukan.')
    return Response(
        content=document.content,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{document.filename}"'},
    )


@router.get('/dosen/kprs')
def list_mentee_kprs(current_user: User = Depends(require_roles('dosen')), db: Session = Depends(get_db)):
    requests = (
        db.query(KprsRequest)
        .join(User, KprsRequest.student_id == User.id)
        .filter(User.advisor_id == current_user.id)
        .order_by(KprsRequest.created_at.desc())
        .all()
    )
    return [{
        'id': item.id,
        'student_id': item.student_id,
        'student_nim': db.query(User.nim).filter(User.id == item.student_id).scalar(),
        'student_name': db.query(User.full_name).filter(User.id == item.student_id).scalar(),
        'study_plan_id': item.study_plan_id,
        'before': json.loads(item.before_json),
        'after': json.loads(item.after_json),
        'reason': item.reason,
        'status': item.status,
        'reviewer_note': item.reviewer_note,
    } for item in requests]


@router.put('/dosen/kprs/{request_id}')
def review_kprs(request_id: int, payload: KprsReview, current_user: User = Depends(require_roles('dosen')), db: Session = Depends(get_db)):
    begin_capacity_transaction(db)
    request = (
        db.query(KprsRequest)
        .filter(KprsRequest.id == request_id)
        .with_for_update()
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail='Pengajuan KPRS tidak ditemukan.')
    student = db.query(User).filter(
        User.id == request.student_id,
        User.role == 'mahasiswa',
        User.advisor_id == current_user.id,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail='Pengajuan KPRS tidak ditemukan.')
    if request.status != 'pending':
        raise HTTPException(status_code=409, detail='Pengajuan KPRS sudah diproses.')
    old_status = request.status
    if payload.status == 'approved':
        plan = (
            db.query(StudyPlan)
            .filter(
                StudyPlan.id == request.study_plan_id,
                StudyPlan.student_id == request.student_id,
            )
            .with_for_update()
            .first()
        )
        if not plan or plan.status != 'approved':
            db.rollback()
            raise HTTPException(status_code=409, detail='KRS asal tidak lagi berstatus approved.')
        try:
            assert_kprs_period_open(db)
            before = json.loads(request.before_json)
            current_courses = json.loads(plan.courses_json)
            if before != current_courses:
                raise ValueError('KRS asal berubah setelah pengajuan KPRS dibuat.')
            after = json.loads(request.after_json)
            courses = validate_course_selection(
                db,
                student,
                [item['code'] for item in after],
                plan.semester,
            )
            lock_capacity_courses(db, [course['code'] for course in courses])
            assert_course_capacity(
                db,
                courses,
                exclude_plan_id=plan.id,
                exclude_kprs_request_id=request.id,
            )
        except (KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=f'KPRS tidak lagi valid: {exc}') from exc
        plan.courses_json = json.dumps(courses, ensure_ascii=False)
        plan.updated_at = utc_now_naive()

    request.status = payload.status
    request.reviewer_id = current_user.id
    request.reviewer_note = payload.note
    request.updated_at = utc_now_naive()
    write_audit(
        db,
        current_user,
        'kprs_review',
        'kprs_request',
        request.id,
        {'status': old_status},
        {'status': request.status, 'note': payload.note},
    )
    db.commit()
    db.refresh(request)
    return {'id': request.id, 'status': request.status, 'reviewer_note': request.reviewer_note}
