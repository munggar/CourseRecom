import json
import re
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from openpyxl import Workbook as ExcelWorkbook, load_workbook
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import Font, PatternFill
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.deps import get_db, require_roles
from app.models import (
    AdvisorCourseFeedback,
    Course,
    KhsDocument,
    RecommendationCache,
    RecommendationModelVersion,
    StudentRecord,
    StudyPlan,
    SystemSetting,
    AuditLog,
    User,
    CourseClass,
    KrsDocument,
    OfficialKrsDocument,
    KprsRequest,
    Room,
    LecturerDirectory,
)
from app.schemas import CourseMutation, AdvisorMapping, SystemSettingUpdate, StudyPlanOverride, CourseClassMutation, LecturerRegistration, LecturerUpdate, RoomMutation, LecturerDirectoryLink
from app.services.academic import class_selection_map, validate_course_selection
from app.services.course_catalog import parse_course_catalog
from app.services.capacity import (
    CapacityError,
    assert_course_capacity,
    begin_capacity_transaction,
    class_occupancy,
    course_occupancy,
    lock_capacity_courses,
)
from app.services.recommendation import train_similarity_model
from app.services.audit import write_audit
from app.services.scheduling import ALLOWED_DAYS, build_available_start_times, validate_class_schedule, validate_room_code
from app.services.time_utils import utc_now_naive
from app.services.validation import assert_krs_period_open
from app.deps import get_password_hash

router = APIRouter()
MAX_IMPORT_BYTES = 10 * 1024 * 1024


@router.post('/admin/lecturers', status_code=201, response_model=None)
def register_lecturer(
    payload: LecturerRegistration,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    nip = payload.nip.strip()
    username = (payload.username or nip).strip()
    email = payload.email.strip() if payload.email else None
    if db.query(User).filter(User.nim == nip).first():
        raise HTTPException(status_code=409, detail='NIP / ID dosen sudah terdaftar.')
    if db.query(User).filter((User.username == username) | (User.nim == username)).first():
        raise HTTPException(status_code=409, detail='Username sudah terdaftar.')
    if email and db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail='Email sudah terdaftar.')

    lecturer = User(
        nim=nip,
        full_name=payload.full_name.strip(),
        username=username,
        email=email,
        role='dosen',
        password_hash=get_password_hash(payload.password),
    )
    db.add(lecturer)
    db.flush()
    directory_entry = db.query(LecturerDirectory).filter(LecturerDirectory.nidn == nip).first()
    if directory_entry:
        directory_entry.linked_user_id = lecturer.id
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='NIP / ID, username, atau email sudah terdaftar.') from exc
    db.refresh(lecturer)
    write_audit(db, current_user, 'lecturer_created', 'user', lecturer.id, None, {'role': 'dosen'})
    db.commit()
    return {
        'id': lecturer.id,
        'nim': lecturer.nim,
        'full_name': lecturer.full_name,
        'username': lecturer.username,
        'email': lecturer.email,
        'role': lecturer.role,
    }


@router.get('/admin/lecturers')
def list_lecturers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    lecturers = db.query(User).filter(User.role == 'dosen').order_by(User.nim).all()
    return [
        {
            'id': lecturer.id,
            'nim': lecturer.nim,
            'full_name': lecturer.full_name,
            'username': lecturer.username or lecturer.nim,
            'email': lecturer.email,
            'role': lecturer.role,
            'is_active': bool(lecturer.is_active),
        }
        for lecturer in lecturers
    ]


@router.get('/admin/lecturer-directory')
def lecturer_directory(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    entries = db.query(LecturerDirectory).order_by(
        LecturerDirectory.program_study,
        LecturerDirectory.full_name,
    ).all()
    result = []
    for entry in entries:
        linked = None
        if entry.linked_user_id:
            linked = db.query(User).filter(User.id == entry.linked_user_id, User.role == 'dosen').first()
        if not linked and entry.nidn:
            linked = db.query(User).filter(User.nim == entry.nidn, User.role == 'dosen').first()
        result.append({
            'id': entry.id,
            'nidn': entry.nidn,
            'full_name': entry.full_name,
            'program_study': entry.program_study,
            'email': entry.email,
            'education': entry.education,
            'expertise': entry.expertise,
            'source_type': entry.source_type,
            'profile_url': entry.profile_url,
            'notes': entry.notes,
            'linked_user_id': linked.id if linked else None,
            'account_nip': linked.nim if linked else None,
            'account_name': linked.full_name if linked else None,
            'account_status': 'akun_terhubung' if linked else 'belum_ada_akun',
        })
    return result


@router.patch('/admin/lecturer-directory/{entry_id}/link')
def link_lecturer_directory_account(
    entry_id: int,
    payload: LecturerDirectoryLink,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    entry = db.query(LecturerDirectory).filter(LecturerDirectory.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail='Profil dosen pada direktori tidak ditemukan.')
    if payload.user_id is None:
        previous = entry.linked_user_id
        entry.linked_user_id = None
        write_audit(
            db, current_user, 'lecturer_directory_unlinked', 'lecturer_directory',
            entry.id, {'linked_user_id': previous}, None,
        )
        db.commit()
        return {'id': entry.id, 'linked_user_id': None, 'status': 'belum_ada_akun'}
    lecturer = db.query(User).filter(
        User.id == payload.user_id,
        User.role == 'dosen',
        User.is_active.is_(True),
    ).first()
    if not lecturer:
        raise HTTPException(status_code=404, detail='Akun dosen aktif tidak ditemukan.')
    duplicate_link = db.query(LecturerDirectory).filter(
        LecturerDirectory.linked_user_id == lecturer.id,
        LecturerDirectory.id != entry.id,
    ).first()
    if duplicate_link:
        raise HTTPException(
            status_code=409,
            detail=f'Akun dosen sudah ditautkan ke profil {duplicate_link.full_name}.',
        )
    previous = entry.linked_user_id
    entry.linked_user_id = lecturer.id
    write_audit(
        db, current_user, 'lecturer_directory_linked', 'lecturer_directory',
        entry.id,
        {'linked_user_id': previous},
        {'linked_user_id': lecturer.id, 'account_nip': lecturer.nim},
    )
    db.commit()
    return {
        'id': entry.id,
        'linked_user_id': lecturer.id,
        'account_nip': lecturer.nim,
        'status': 'akun_terhubung',
    }


def _excel_response(workbook: ExcelWorkbook, filename: str) -> Response:
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.get('/admin/lecturers/export')
def export_lecturers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    workbook = ExcelWorkbook()
    directory_sheet = workbook.active
    directory_sheet.title = 'Direktori Dosen'
    directory_sheet.append(['NIDN', 'Nama Dosen', 'Program Studi', 'Email', 'Pendidikan Terakhir', 'Bidang Keahlian', 'Status Akun', 'NIP Akun', 'Sumber'])
    for entry in db.query(LecturerDirectory).order_by(LecturerDirectory.program_study, LecturerDirectory.full_name).all():
        linked = db.query(User).filter(
            User.id == entry.linked_user_id,
            User.role == 'dosen',
        ).first() if entry.linked_user_id else None
        if not linked and entry.nidn:
            linked = db.query(User).filter(User.nim == entry.nidn, User.role == 'dosen').first()
        directory_sheet.append([
            entry.nidn or '', entry.full_name, entry.program_study, entry.email or '',
            entry.education or '', entry.expertise or '',
            'Akun terhubung' if linked else 'Belum ada akun',
            linked.nim if linked else '', entry.profile_url,
        ])
    account_sheet = workbook.create_sheet('Akun Dosen')
    account_sheet.append(['NIP / ID', 'Nama Akun', 'Username', 'Email', 'Status Akun', 'Mahasiswa Bimbingan'])
    for lecturer in db.query(User).filter(User.role == 'dosen').order_by(User.nim).all():
        account_sheet.append([
            lecturer.nim, lecturer.full_name, lecturer.username or lecturer.nim,
            lecturer.email or '', 'Aktif' if lecturer.is_active else 'Nonaktif',
            db.query(User).filter(User.role == 'mahasiswa', User.advisor_id == lecturer.id).count(),
        ])
    for sheet in workbook.worksheets:
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='075E59')
        for column_cells in sheet.columns:
            letter = column_cells[0].column_letter
            sheet.column_dimensions[letter].width = min(42, max(14, max(len(str(cell.value or '')) for cell in column_cells) + 2))
    return _excel_response(workbook, 'Data_Dosen_CourseRecom.xlsx')


@router.put('/admin/lecturers/{lecturer_nip}')
def update_lecturer(
    lecturer_nip: str,
    payload: LecturerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    lecturer = db.query(User).filter(User.nim == lecturer_nip, User.role == 'dosen').first()
    if not lecturer:
        raise HTTPException(status_code=404, detail='Akun dosen tidak ditemukan.')
    username = payload.username.strip()
    email = payload.email.strip() if payload.email else None
    if db.query(User).filter(User.id != lecturer.id, User.username == username).first():
        raise HTTPException(status_code=409, detail='Username sudah digunakan akun lain.')
    if email and db.query(User).filter(User.id != lecturer.id, User.email == email).first():
        raise HTTPException(status_code=409, detail='Email sudah digunakan akun lain.')
    old_values = {'full_name': lecturer.full_name, 'username': lecturer.username, 'email': lecturer.email}
    lecturer.full_name = payload.full_name.strip()
    lecturer.username = username
    lecturer.email = email
    write_audit(db, current_user, 'lecturer_updated', 'user', lecturer.id, old_values, {
        'full_name': lecturer.full_name, 'username': lecturer.username, 'email': lecturer.email,
    })
    db.commit()
    return {
        'id': lecturer.id, 'nim': lecturer.nim, 'full_name': lecturer.full_name,
        'username': lecturer.username, 'email': lecturer.email, 'role': lecturer.role,
    }


@router.delete('/admin/lecturers/{lecturer_nip}', status_code=204)
def delete_lecturer(
    lecturer_nip: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    lecturer = db.query(User).filter(User.nim == lecturer_nip, User.role == 'dosen').first()
    if not lecturer:
        raise HTTPException(status_code=404, detail='Akun dosen tidak ditemukan.')
    db.query(User).filter(User.advisor_id == lecturer.id).update({'advisor_id': None}, synchronize_session=False)
    db.query(CourseClass).filter(CourseClass.lecturer_id == lecturer.id).update({'lecturer_id': None}, synchronize_session=False)
    db.query(StudyPlan).filter(StudyPlan.reviewer_id == lecturer.id).update(
        {'reviewer_id': None}, synchronize_session=False,
    )
    db.query(KprsRequest).filter(KprsRequest.reviewer_id == lecturer.id).update(
        {'reviewer_id': None}, synchronize_session=False,
    )
    db.query(AdvisorCourseFeedback).filter(AdvisorCourseFeedback.reviewer_id == lecturer.id).update(
        {'reviewer_id': None}, synchronize_session=False,
    )
    db.query(AuditLog).filter(AuditLog.actor_id == lecturer.id).update(
        {'actor_id': None}, synchronize_session=False,
    )
    write_audit(db, current_user, 'lecturer_deleted', 'user', lecturer.id, {'nim': lecturer.nim}, None)
    db.delete(lecturer)
    db.commit()


@router.patch('/admin/students/{student_nim}/advisor')
def assign_student_advisor(
    student_nim: str,
    payload: AdvisorMapping,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    student = db.query(User).filter(User.nim == student_nim, User.role == 'mahasiswa').first()
    if not student:
        raise HTTPException(status_code=404, detail='Mahasiswa tidak ditemukan.')
    advisor = db.query(User).filter(User.nim == payload.advisor_nim, User.role == 'dosen').first()
    if not advisor:
        raise HTTPException(status_code=404, detail='Dosen PA tidak ditemukan.')
    old_advisor_id = student.advisor_id
    reason = payload.reason.strip()
    student.advisor_id = advisor.id
    write_audit(
        db,
        current_user,
        'advisor_mapping_changed',
        'student',
        student.id,
        {'advisor_id': old_advisor_id},
        {'advisor_id': advisor.id, 'reason': reason or None},
    )
    db.commit()
    return {'student_nim': student.nim, 'advisor_nim': advisor.nim}


@router.get('/admin/advisor-history')
def advisor_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    entries = db.query(AuditLog).filter(
        AuditLog.action.in_(('advisor_mapping_changed', 'advisor_mapping_bulk'))
    ).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).all()
    history = []
    for entry in entries:
        student = db.query(User).filter(User.id == int(entry.entity_id)).first() if entry.entity_type == 'student' else None
        old_value = json.loads(entry.old_value) if entry.old_value else {}
        new_value = json.loads(entry.new_value) if entry.new_value else {}
        previous_advisor = db.query(User).filter(User.id == old_value.get('advisor_id')).first()
        current_advisor = db.query(User).filter(User.id == new_value.get('advisor_id')).first()
        history.append({
            'id': entry.id,
            'student_name': student.full_name if student else None,
            'student_nim': student.nim if student else None,
            'previous_advisor_name': previous_advisor.full_name if previous_advisor else None,
            'previous_advisor_nim': previous_advisor.nim if previous_advisor else None,
            'advisor_name': current_advisor.full_name if current_advisor else None,
            'advisor_nim': current_advisor.nim if current_advisor else None,
            'admin_name': entry.actor_name,
            'changed_at': entry.created_at.isoformat(),
            'reason': new_value.get('reason') or None,
        })
    return history


@router.post('/admin/students/advisors/bulk')
def assign_student_advisors_bulk(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    student_nims = payload.get('student_nims', [])
    advisor_nim = payload.get('advisor_nim')
    if not isinstance(student_nims, list) or not student_nims or not isinstance(advisor_nim, str):
        raise HTTPException(status_code=422, detail='Daftar mahasiswa dan dosen PA wajib diisi.')
    advisor = db.query(User).filter(User.nim == advisor_nim.strip(), User.role == 'dosen').first()
    if not advisor:
        raise HTTPException(status_code=404, detail='Dosen PA tidak ditemukan.')
    students = db.query(User).filter(User.role == 'mahasiswa', User.nim.in_(student_nims)).all()
    found = {student.nim for student in students}
    missing = sorted(set(student_nims) - found)
    if missing:
        raise HTTPException(status_code=404, detail=f'Mahasiswa tidak ditemukan: {", ".join(missing)}')
    for student in students:
        old_advisor_id = student.advisor_id
        student.advisor_id = advisor.id
        write_audit(db, current_user, 'advisor_mapping_bulk', 'student', student.id, {'advisor_id': old_advisor_id}, {'advisor_id': advisor.id})
    db.commit()
    return {'assigned': len(students), 'advisor_nim': advisor.nim}


def _course_payload(course: Course) -> dict:
    return {
        'code': course.code,
        'name': course.name,
        'sks': course.sks,
        'semester': course.semester,
        'available_semesters': course.available_semesters or str(course.semester),
        'category': course.category,
        'description': course.description or '',
        'prerequisite_text': course.prerequisite_text or '',
        'prerequisite_codes': course.prerequisite_codes or '',
        'day': course.day or '',
        'time': course.time or '',
        'capacity': course.capacity if course.capacity is not None else 40,
    }


@router.get('/admin/dashboard')
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    students = (
        db.query(User)
        .filter(User.role == 'mahasiswa')
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
    advisors = (
        db.query(User)
        .filter(User.role == 'dosen')
        .order_by(User.nim)
        .all()
    )

    # Count active catalog courses in every semester where they are offered.
    semester_course_counts = {semester: 0 for semester in range(1, 9)}
    active_courses = db.query(Course).filter(Course.is_active.is_(True)).all()
    for course in active_courses:
        raw_semesters = course.available_semesters or str(course.semester)
        parsed_semesters = {
            int(value.strip())
            for value in raw_semesters.replace(';', ',').split(',')
            if value.strip().isdigit() and 1 <= int(value.strip()) <= 14
        }
        offered_semesters = {semester for semester in parsed_semesters if semester <= 8}
        if not parsed_semesters and 1 <= course.semester <= 8:
            offered_semesters.add(course.semester)
        for semester in offered_semesters:
            semester_course_counts[semester] += 1

    return {
        'students': [
            {
                'nim': student.nim,
                'full_name': student.full_name,
                'semester': student.semester,
                'ipk': student.ipk,
                'interests': student.interests or '',
                'khs_confirmed': student.id in confirmed_student_ids,
                'advisor_nim': db.query(User.nim).filter(User.id == student.advisor_id).scalar(),
            }
            for student in students
        ],
        'advisors': [
            {'nim': advisor.nim, 'full_name': advisor.full_name}
            for advisor in advisors
        ],
        'analytics': {
            'total_students': len(students),
            'confirmed_khs_students': len(confirmed_student_ids),
            'total_advisors': len(advisors),
            'total_active_courses': len(active_courses),
            'courses_by_semester': [
                {'semester': semester, 'count': semester_course_counts[semester]}
                for semester in range(1, 9)
            ],
            'updated_at': utc_now_naive().isoformat(),
        },
    }

@router.delete('/admin/students/{student_nim}', status_code=204)
def delete_student(
    student_nim: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    student = (
        db.query(User)
        .filter(User.nim == student_nim, User.role == 'mahasiswa')
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail='Akun mahasiswa tidak ditemukan.')

    try:
        db.query(OfficialKrsDocument).filter(
            OfficialKrsDocument.student_id == student.id,
        ).delete(synchronize_session=False)
        db.query(KrsDocument).filter(KrsDocument.student_id == student.id).delete(
            synchronize_session=False,
        )
        db.query(KprsRequest).filter(KprsRequest.student_id == student.id).delete(
            synchronize_session=False,
        )
        db.query(AdvisorCourseFeedback).filter(
            (AdvisorCourseFeedback.student_id == student.id)
            | (AdvisorCourseFeedback.reviewer_id == student.id),
        ).delete(synchronize_session=False)
        db.query(StudyPlan).filter(StudyPlan.reviewer_id == student.id).update(
        {'reviewer_id': None},
        synchronize_session=False,
        )
        db.query(StudyPlan).filter(StudyPlan.student_id == student.id).delete(
            synchronize_session=False,
        )
        db.query(RecommendationCache).filter(
            RecommendationCache.student_id == student.id,
        ).delete(synchronize_session=False)
        db.query(KhsDocument).filter(KhsDocument.student_id == student.id).delete(
            synchronize_session=False,
        )
        db.query(StudentRecord).filter(StudentRecord.student_id == student.id).delete(
            synchronize_session=False,
        )
        db.query(AuditLog).filter(AuditLog.actor_id == student.id).update(
            {'actor_id': None},
            synchronize_session=False,
        )
        db.query(User).filter(User.advisor_id == student.id).update(
            {'advisor_id': None},
            synchronize_session=False,
        )
        write_audit(
            db,
            current_user,
            'student_deleted',
            'user',
            student.id,
            {'nim': student.nim, 'full_name': student.full_name},
            None,
        )
        db.delete(student)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail='Akun tidak dapat dihapus karena masih memiliki data akademik yang terkait.',
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail='Penghapusan akun mahasiswa gagal.') from exc


@router.get('/admin/courses')
def list_courses(db: Session = Depends(get_db), current_user: User = Depends(require_roles('admin'))):
    courses = (
        db.query(Course)
        .filter(Course.is_active.is_(True))
        .order_by(Course.semester, Course.code)
        .all()
    )
    return [_course_payload(course) for course in courses]


@router.post('/admin/courses', status_code=201)
def create_course(
    payload: CourseMutation,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    course = db.query(Course).filter(Course.code == payload.code).first()
    if course and course.is_active:
        raise HTTPException(status_code=409, detail=f'Kode mata kuliah {payload.code} sudah ada.')
    if not course:
        course = Course(code=payload.code)
        db.add(course)
    _apply_course_payload(course, payload)
    write_audit(db, current_user, 'course_saved', 'course', course.code, None, payload.model_dump())
    db.commit()
    db.refresh(course)
    return _course_payload(course)


@router.put('/admin/courses/{course_code}')
def update_course(
    course_code: str,
    payload: CourseMutation,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    begin_capacity_transaction(db)
    course = db.query(Course).filter(
        Course.code == course_code,
        Course.is_active.is_(True),
    ).with_for_update().first()
    if not course:
        raise HTTPException(status_code=404, detail='Mata kuliah tidak ditemukan.')
    duplicate = db.query(Course).filter(Course.code == payload.code, Course.id != course.id).first()
    if duplicate:
        raise HTTPException(status_code=409, detail=f'Kode mata kuliah {payload.code} sudah digunakan.')
    if payload.code != course.code and _course_code_is_referenced(db, course):
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail='Kode mata kuliah tidak dapat diubah karena sudah digunakan oleh data akademik atau prasyarat.',
        )
    try:
        occupied = course_occupancy(db, course.code)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if payload.capacity < occupied:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f'Kapasitas tidak dapat dikurangi di bawah {occupied} kursi yang sudah terpakai.',
        )
    _apply_course_payload(course, payload)
    write_audit(db, current_user, 'course_saved', 'course', course.code, {'code': course_code}, payload.model_dump())
    db.commit()
    db.refresh(course)
    return _course_payload(course)


def _course_code_is_referenced(db: Session, course: Course) -> bool:
    code = course.code
    if db.query(StudentRecord.id).filter(StudentRecord.course_code == code).first():
        return True
    if db.query(RecommendationCache.id).filter(RecommendationCache.course_code == code).first():
        return True
    if db.query(CourseClass.id).filter(CourseClass.course_code == code).first():
        return True

    prerequisite_rows = db.query(Course.prerequisite_codes).all()
    if any(
        code == item.strip().upper()
        for (prerequisites,) in prerequisite_rows
        for item in (prerequisites or '').replace(';', ',').split(',')
    ):
        return True

    if db.query(KhsDocument.id).filter(
        KhsDocument.parsed_data.like(f'%"{code}"%'),
    ).first():
        return True

    for (courses_json,) in db.query(StudyPlan.courses_json).all():
        try:
            courses = json.loads(courses_json)
        except (TypeError, json.JSONDecodeError):
            return True
        if not isinstance(courses, list):
            return True
        if any(isinstance(item, dict) and item.get('code') == code for item in courses):
            return True

    for request in db.query(KprsRequest.before_json, KprsRequest.after_json).all():
        try:
            before, after = (json.loads(value) for value in request)
        except (TypeError, json.JSONDecodeError):
            return True
        if not isinstance(before, list) or not isinstance(after, list):
            return True
        if any(
            isinstance(item, dict) and item.get('code') == code
            for item in before + after
        ):
            return True
    return False


def _apply_course_payload(course: Course, payload: CourseMutation) -> None:
    course.code = payload.code.upper()
    course.name = payload.name
    course.sks = payload.sks
    course.semester = payload.semester
    course.available_semesters = payload.available_semesters
    course.category = payload.category
    course.description = payload.description or None
    course.prerequisite_text = payload.prerequisite_text or None
    course.prerequisite_codes = payload.prerequisite_codes or ''
    course.day = payload.day or None
    course.time = payload.time or None
    course.capacity = payload.capacity
    course.is_active = True


@router.delete('/admin/courses/{course_code}', status_code=204)
def deactivate_course(
    course_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    course = db.query(Course).filter(Course.code == course_code, Course.is_active.is_(True)).first()
    if not course:
        raise HTTPException(status_code=404, detail='Mata kuliah tidak ditemukan.')
    course.is_active = False
    write_audit(db, current_user, 'course_deactivated', 'course', course.code, {'is_active': True}, {'is_active': False})
    db.commit()


@router.get('/admin/evaluasi')
def evaluation(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    model = db.query(RecommendationModelVersion).order_by(
        RecommendationModelVersion.trained_at.desc()
    ).first()
    if not model:
        return {'status': 'not_trained', 'message': 'Model belum pernah dilatih.', 'metrics': None}
    return {
        'version': model.version,
        'method': model.method,
        'trained_at': model.trained_at.replace(tzinfo=timezone.utc).isoformat(),
        'dataset_size': model.dataset_size,
        'metrics': json.loads(model.metrics),
        'status': 'ready',
    }


@router.get('/admin/model/versions')
def model_versions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    return [
        {
            'version': item.version,
            'method': item.method,
            'dataset_size': item.dataset_size,
            'metrics': json.loads(item.metrics),
            'trained_at': item.trained_at.replace(tzinfo=timezone.utc).isoformat(),
        }
        for item in db.query(RecommendationModelVersion)
        .order_by(RecommendationModelVersion.trained_at.desc())
        .all()
    ]


@router.post('/admin/model/train')
def train_model(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    model = train_similarity_model(db)
    return {
        'version': model.version,
        'method': model.method,
        'dataset_size': model.dataset_size,
        'metrics': json.loads(model.metrics),
        'trained_at': model.trained_at.replace(tzinfo=timezone.utc).isoformat(),
    }


@router.post('/admin/import-data')
async def import_data(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles('admin')),
    db: Session = Depends(get_db),
):
    filename = file.filename or ''
    if not filename.lower().endswith(('.csv', '.xlsx')):
        raise HTTPException(status_code=415, detail='Impor katalog hanya mendukung file Excel (.xlsx) atau CSV.')
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail='Ukuran file katalog maksimal 10 MB.')
    try:
        courses, replace_catalog = parse_course_catalog(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        previous_active_count = db.query(Course).filter(Course.is_active.is_(True)).count()
        previous_active_codes = [
            code for (code,) in db.query(Course.code)
            .filter(Course.is_active.is_(True))
            .order_by(Course.code)
            .all()
        ]

        if replace_catalog:
            db.query(Course).update({'is_active': False}, synchronize_session=False)

        for item in courses:
            course = db.query(Course).filter(Course.code == item['code']).first()
            if not course:
                course = Course(code=item['code'])
                db.add(course)
            for field, value in item.items():
                setattr(course, field, value)
            course.is_active = True

        write_audit(
            db,
            current_user,
            'course_catalog_imported',
            'course_catalog',
            'active',
            {
                'active_count': previous_active_count,
                'active_codes': previous_active_codes,
            },
            {
                'rows_received': len(courses),
                'catalog_replaced': replace_catalog,
                'file_name': filename,
            },
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {
        'status': 'ok',
        'rows_received': len(courses),
        'catalog_replaced': replace_catalog,
        'file_name': filename,
    }


@router.get('/admin/settings')
def list_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    return [
        {'key': item.key, 'value': item.value, 'updated_at': item.updated_at.isoformat()}
        for item in db.query(SystemSetting).order_by(SystemSetting.key).all()
    ]


@router.put('/admin/settings')
def update_setting(
    payload: SystemSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    if payload.key == 'max_sks_by_ips':
        try:
            json.loads(payload.value)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail='max_sks_by_ips harus berupa JSON yang valid.') from exc
    if payload.key == 'active_academic_year':
        match = re.fullmatch(r'(\d{4})/(\d{4})', payload.value.strip())
        if not match or int(match.group(2)) != int(match.group(1)) + 1:
            raise HTTPException(
                status_code=422,
                detail='Tahun ajaran harus menggunakan format berurutan, misalnya 2026/2027.',
            )
        payload.value = payload.value.strip()
    setting = db.query(SystemSetting).filter(SystemSetting.key == payload.key).first()
    old_value = setting.value if setting else None
    if not setting:
        setting = SystemSetting(key=payload.key, value=payload.value, updated_at=utc_now_naive())
        db.add(setting)
    else:
        setting.value = payload.value
        setting.updated_at = utc_now_naive()
    write_audit(db, current_user, 'setting_update', 'system_setting', payload.key, old_value, payload.value)
    db.commit()
    db.refresh(setting)
    return {'key': setting.key, 'value': setting.value, 'updated_at': setting.updated_at.isoformat()}


@router.get('/admin/study-plans/approved')
def list_approved_study_plans(db: Session = Depends(get_db), current_user: User = Depends(require_roles('admin'))):
    plans = db.query(StudyPlan).join(User, StudyPlan.student_id == User.id).filter(StudyPlan.status == 'approved').order_by(StudyPlan.updated_at.desc()).all()
    return [{
        'id': plan.id,
        'student_id': plan.student_id,
        'student_name': plan.student.full_name if getattr(plan, 'student', None) else db.query(User.full_name).filter(User.id == plan.student_id).scalar(),
        'semester': plan.semester,
        'status': plan.status,
        'courses': json.loads(plan.courses_json) if plan.courses_json else [],
    } for plan in plans]


@router.patch('/admin/study-plans/{plan_id}/override')
def override_study_plan(
    plan_id: int,
    payload: StudyPlanOverride,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    begin_capacity_transaction(db)
    plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id).with_for_update().first()
    if not plan:
        raise HTTPException(status_code=404, detail='Pengajuan KRS tidak ditemukan.')
    old_status = plan.status
    old_courses = json.loads(plan.courses_json) if plan.courses_json else []
    student = db.query(User).filter(
        User.id == plan.student_id,
        User.role == 'mahasiswa',
    ).first()
    if not student:
        db.rollback()
        raise HTTPException(status_code=409, detail='Mahasiswa pemilik KRS tidak ditemukan.')
    codes = payload.course_codes
    if codes is None:
        try:
            codes = [item['code'] for item in old_courses]
        except (KeyError, TypeError) as exc:
            raise HTTPException(status_code=409, detail='Data mata kuliah KRS tersimpan tidak valid.') from exc
    if payload.status in {'pending', 'approved'}:
        try:
            assert_krs_period_open(db)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        selections = class_selection_map(old_courses)
        selections.update(payload.class_selections)
        selections = {code: selections[code] for code in codes if code in selections}
        courses = validate_course_selection(db, student, codes, plan.semester, selections)
        lock_capacity_courses(db, [course['code'] for course in courses], [int(course['class_id']) for course in courses if course.get('class_id') is not None])
        assert_course_capacity(db, courses, exclude_plan_id=plan.id)
    except CapacityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    plan.courses_json = json.dumps(courses, ensure_ascii=False)
    plan.status = payload.status
    plan.advisor_note = payload.reason
    plan.updated_at = utc_now_naive()
    write_audit(
        db,
        current_user,
        'study_plan_override',
        'study_plan',
        plan.id,
        {'status': old_status, 'courses': old_courses},
        {'status': payload.status, 'courses': json.loads(plan.courses_json) if plan.courses_json else [], 'reason': payload.reason},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='Mahasiswa sudah memiliki pengajuan KRS pending lain.') from exc
    db.refresh(plan)
    return {
        'id': plan.id,
        'status': plan.status,
        'advisor_note': plan.advisor_note,
    }


@router.get('/admin/audit-logs')
def audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    return [
        {
            'id': item.id,
            'actor_id': item.actor_id,
            'actor_name': item.actor_name,
            'action': item.action,
            'entity_type': item.entity_type,
            'entity_id': item.entity_id,
            'old_value': item.old_value,
            'new_value': item.new_value,
            'created_at': item.created_at.isoformat(),
        }
        for item in db.query(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(500).all()
    ]


@router.get('/admin/reports/students-without-krs')
def students_without_krs(db: Session = Depends(get_db), current_user: User = Depends(require_roles('admin'))):
    students_with_plan = {
        student_id for (student_id,) in db.query(StudyPlan.student_id).distinct().all()
    }
    return [
        {'id': student.id, 'nim': student.nim, 'full_name': student.full_name}
        for student in db.query(User).filter(User.role == 'mahasiswa', User.is_active.is_(True)).order_by(User.nim).all()
        if student.id not in students_with_plan
    ]


@router.get('/admin/reports/course-participants')
def course_participants(db: Session = Depends(get_db), current_user: User = Depends(require_roles('admin'))):
    participants = {}
    plans = db.query(StudyPlan).filter(StudyPlan.status.in_(('pending', 'approved'))).all()
    for plan in plans:
        student = db.query(User).filter(User.id == plan.student_id).first()
        try:
            courses = json.loads(plan.courses_json)
        except json.JSONDecodeError:
            continue
        for course in courses:
            participants.setdefault(course['code'], []).append({
                'nim': student.nim if student else '',
                'full_name': student.full_name if student else '',
                'plan_id': plan.id,
            })
    return [
        {'code': code, 'participants': sorted(rows, key=lambda item: item['nim'])}
        for code, rows in sorted(participants.items())
    ]


@router.get('/admin/rooms')
def list_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    sections = db.query(CourseClass).all()
    section_counts = {}
    for section in sections:
        section_counts[section.room.strip().upper()] = section_counts.get(section.room.strip().upper(), 0) + 1
    return [{
        'code': room.code,
        'floor': room.floor,
        'room_number': room.room_number,
        'capacity': room.capacity,
        'room_type': room.room_type,
        'is_active': room.is_active,
        'source_status': room.source_status,
        'source_url': room.source_url,
        'notes': room.notes,
        'verified_at': room.verified_at.isoformat() if room.verified_at else None,
        'class_count': section_counts.get(room.code, 0),
    } for room in db.query(Room).order_by(Room.floor, Room.room_number).all()]


@router.post('/admin/rooms', status_code=201)
def create_room(
    payload: RoomMutation,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    code = validate_room_code(payload.code)
    if db.query(Room).filter(Room.code == code).first():
        raise HTTPException(status_code=409, detail=f'Ruang {code} sudah terdaftar.')
    if payload.is_active and payload.capacity is None:
        raise HTTPException(status_code=422, detail='Isi kapasitas ruang sebelum mengaktifkan ruang.')
    if payload.is_active and len(payload.notes.strip()) < 10:
        raise HTTPException(status_code=422, detail='Catatan verifikasi fisik minimal 10 karakter sebelum ruang diaktifkan.')
    room = Room(
        code=code,
        floor=int(code[2]) if code[2].isdigit() else None,
        room_number=code[3:] if code[2].isdigit() else code[-1:],
        capacity=payload.capacity,
        room_type=payload.room_type.strip(),
        is_active=payload.is_active,
        source_status='admin_verified' if payload.is_active else 'needs_verification',
        source_url=None,
        notes=payload.notes.strip() or None,
        verified_at=utc_now_naive() if payload.is_active else None,
        created_at=utc_now_naive(),
    )
    db.add(room)
    write_audit(db, current_user, 'room_created', 'room', code, None, payload.model_dump())
    db.commit()
    return {'code': room.code, 'is_active': room.is_active, 'capacity': room.capacity}


@router.patch('/admin/rooms/{room_code}')
def update_room(
    room_code: str,
    payload: RoomMutation,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    code = validate_room_code(room_code)
    if payload.code != code:
        raise HTTPException(status_code=422, detail='Kode ruang bersifat tetap. Tambahkan kode ruang baru untuk ruang berbeda.')
    room = db.query(Room).filter(Room.code == code).first()
    if not room:
        raise HTTPException(status_code=404, detail='Ruang tidak ditemukan.')
    if payload.is_active and payload.capacity is None:
        raise HTTPException(status_code=422, detail='Isi kapasitas ruang sebelum mengaktifkan ruang.')
    if payload.is_active and len(payload.notes.strip()) < 10:
        raise HTTPException(status_code=422, detail='Catatan verifikasi fisik minimal 10 karakter sebelum ruang diaktifkan.')
    room_classes = db.query(CourseClass).filter(CourseClass.room == code).all()
    if not payload.is_active:
        open_classes = sum(1 for item in room_classes if item.is_open)
        if open_classes:
            raise HTTPException(
                status_code=409,
                detail=f'Ruang masih dipakai {open_classes} kelas terbuka. Tutup kelas atau pindahkan jadwal sebelum menonaktifkan ruang.',
            )
    if payload.capacity is not None:
        oversized = [item for item in room_classes if item.capacity > payload.capacity]
        if oversized:
            max_class_capacity = max(item.capacity for item in oversized)
            raise HTTPException(
                status_code=409,
                detail=f'Kapasitas ruang tidak boleh kurang dari kuota kelas yang sudah dibuat ({max_class_capacity} kursi).',
            )
    old = {
        'capacity': room.capacity,
        'room_type': room.room_type,
        'is_active': room.is_active,
        'notes': room.notes,
    }
    room.capacity = payload.capacity
    room.room_type = payload.room_type.strip()
    room.is_active = payload.is_active
    room.notes = payload.notes.strip() or None
    room.source_status = 'admin_verified' if payload.is_active else 'needs_verification'
    room.verified_at = utc_now_naive() if payload.is_active else None
    write_audit(db, current_user, 'room_updated', 'room', code, old, {
        'capacity': room.capacity, 'room_type': room.room_type,
        'is_active': room.is_active, 'notes': room.notes,
    })
    db.commit()
    return {'code': room.code, 'is_active': room.is_active, 'capacity': room.capacity}


@router.get('/admin/rooms/export')
def export_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    workbook = ExcelWorkbook()
    inventory = workbook.active
    inventory.title = 'Inventaris Ruangan'
    inventory.append(['Kode Ruang', 'Lantai', 'Nomor Ruang', 'Kapasitas Ruang', 'Tipe', 'Status Aktif', 'Status Sumber', 'Jumlah Kelas', 'Sumber', 'Catatan'])
    classes_by_room = {}
    for section in db.query(CourseClass).all():
        classes_by_room[section.room.strip().upper()] = classes_by_room.get(section.room.strip().upper(), 0) + 1
    for room in db.query(Room).order_by(Room.floor, Room.room_number).all():
        inventory.append([
            room.code, room.floor, room.room_number, room.capacity or '',
            room.room_type, 'Aktif' if room.is_active else 'Perlu verifikasi / nonaktif',
            room.source_status, classes_by_room.get(room.code, 0),
            room.source_url or '', room.notes or '',
        ])
    schedule = workbook.create_sheet('Jadwal Kelas')
    schedule.append(['Kode Ruang', 'Mata Kuliah', 'Nama Kelas', 'Semester', 'Hari', 'Jam Mulai', 'Jam Selesai', 'Kampus', 'SKS', 'Dosen', 'Status'])
    for section in db.query(CourseClass).order_by(CourseClass.room, CourseClass.day, CourseClass.start_time).all():
        course = db.query(Course).filter(Course.code == section.course_code).first()
        lecturer = db.query(User).filter(User.id == section.lecturer_id, User.role == 'dosen').first() if section.lecturer_id else None
        schedule.append([
            section.room, f'{section.course_code} - {course.name if course else ""}',
            section.class_name, section.semester, section.day, section.start_time,
            section.end_time, 'Ps-Rebo FT', course.sks if course else '', section.lecturer_name or (lecturer.full_name if lecturer else ''),
            'Dibuka' if section.is_open else 'Ditutup',
        ])
    for sheet in workbook.worksheets:
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='075E59')
        for column_cells in sheet.columns:
            letter = column_cells[0].column_letter
            sheet.column_dimensions[letter].width = min(44, max(14, max(len(str(cell.value or '')) for cell in column_cells) + 2))
    return _excel_response(workbook, 'Data_Ruangan_CourseRecom.xlsx')


@router.get('/admin/schedule-options')
def schedule_options(
    course_code: str = Query(..., min_length=2, max_length=20),
    room_code: str = Query(..., min_length=5, max_length=10),
    day: str = Query(...),
    lecturer_id: int | None = Query(None),
    lecturer_name: str | None = Query(None, max_length=180),
    exclude_class_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    try:
        course = db.query(Course).filter(Course.code == course_code.strip().upper(), Course.is_active.is_(True)).first()
        if not course:
            raise ValueError('Mata kuliah aktif tidak ditemukan.')
        slots = build_available_start_times(
            db,
            course_code=course.code,
            room_code=room_code,
            day=day,
            lecturer_id=lecturer_id,
            lecturer_name=lecturer_name,
            exclude_class_id=exclude_class_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        'course_code': course.code,
        'sks': course.sks,
        'duration_minutes': course.sks * 50,
        'start_window': '07:00–18:00',
        'slots': slots,
    }


@router.get('/admin/classes')
def list_classes(db: Session = Depends(get_db), current_user: User = Depends(require_roles('admin'))):
    results = []
    for item in db.query(CourseClass).order_by(CourseClass.semester, CourseClass.course_code, CourseClass.class_name).all():
        course = db.query(Course).filter(Course.code == item.course_code).first()
        lecturer = db.query(User).filter(User.id == item.lecturer_id, User.role == 'dosen').first() if item.lecturer_id else None
        occupied = class_occupancy(db, item.id)
        results.append({
            'id': item.id,
            'course_code': item.course_code,
            'course_name': course.name if course else '',
            'class_name': item.class_name,
            'lecturer_id': item.lecturer_id,
            'lecturer_name': item.lecturer_name or (lecturer.full_name if lecturer else ''),
            'room': item.room,
            'day': item.day,
            'start_time': item.start_time,
            'end_time': item.end_time,
            'capacity': item.capacity,
            'occupied': occupied,
            'remaining_seats': max(0, item.capacity - occupied),
            'semester': item.semester,
            'is_open': item.is_open,
        })
    return results


CLASS_IMPORT_HEADERS = [
    'Kode Mata Kuliah',
    'Nama Kelas',
    'Nama Dosen (opsional)',
    'Kode Ruang',
    'Hari',
    'Jam Mulai (HH:MM)',
    'Kapasitas',
    'Semester',
    'Buka Kelas (Ya/Tidak)',
]


def _class_import_time(value) -> str:
    if isinstance(value, datetime):
        return value.strftime('%H:%M')
    if hasattr(value, 'hour') and hasattr(value, 'minute'):
        return f'{value.hour:02d}:{value.minute:02d}'
    if isinstance(value, (int, float)) and 0 <= float(value) < 1:
        total_minutes = round(float(value) * 24 * 60)
        return f'{total_minutes // 60:02d}:{total_minutes % 60:02d}'
    raw = str(value or '').strip().upper()
    for pattern in ('%H:%M', '%H.%M', '%I:%M %p', '%I.%M %p'):
        try:
            return datetime.strptime(raw, pattern).strftime('%H:%M')
        except ValueError:
            continue
    raise ValueError('Jam mulai harus ditulis HH:MM, misalnya 07:50.')


def _class_import_boolean(value) -> bool:
    if value is None or str(value).strip() == '':
        return True
    normalized = str(value).strip().casefold()
    if normalized in {'ya', 'yes', 'true', '1', 'buka', 'aktif'}:
        return True
    if normalized in {'tidak', 'no', 'false', '0', 'tutup', 'nonaktif'}:
        return False
    raise ValueError('Kolom Buka Kelas hanya menerima Ya atau Tidak.')


def _class_import_number(value, label: str, minimum: int, maximum: int) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{label} harus berupa angka.') from exc
    if not number.is_integer() or not minimum <= int(number) <= maximum:
        raise ValueError(f'{label} harus berupa bilangan bulat {minimum} sampai {maximum}.')
    return int(number)


@router.get('/admin/classes/template')
def download_class_import_template(
    current_user: User = Depends(require_roles('admin')),
):
    workbook = ExcelWorkbook()
    worksheet = workbook.active
    worksheet.title = 'Impor Kelas'
    worksheet.append(CLASS_IMPORT_HEADERS)
    worksheet.freeze_panes = 'A2'
    worksheet.auto_filter.ref = 'A1:I1'
    worksheet.row_dimensions[1].height = 34
    widths = [22, 18, 38, 16, 14, 21, 14, 12, 22]
    for index, width in enumerate(widths, start=1):
        worksheet.column_dimensions[chr(64 + index)].width = width
    for cell in worksheet[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='075E59')
        cell.alignment = __import__('openpyxl').styles.Alignment(
            horizontal='center', vertical='center', wrap_text=True,
        )
    for row in range(2, 202):
        worksheet.cell(row=row, column=1).number_format = '@'
        worksheet.cell(row=row, column=4).number_format = '@'
        worksheet.cell(row=row, column=6).number_format = '@'

    day_validation = DataValidation(
        type='list',
        formula1='"Senin,Selasa,Rabu,Kamis,Jumat,Sabtu,Minggu"',
        allow_blank=False,
    )
    open_validation = DataValidation(type='list', formula1='"Ya,Tidak"', allow_blank=True)
    worksheet.add_data_validation(day_validation)
    worksheet.add_data_validation(open_validation)
    day_validation.add('E2:E201')
    open_validation.add('I2:I201')

    guide = workbook.create_sheet('Panduan')
    guide.append(['PANDUAN IMPOR KELAS PARALEL'])
    guide.append(['Isi satu baris untuk setiap kelas paralel. Hapus baris kosong; jangan mengubah nama kolom pada sheet Impor Kelas.'])
    guide.append([])
    guide.append(['Kolom', 'Wajib', 'Keterangan'])
    instructions = [
        ('Kode Mata Kuliah', 'Ya', 'Harus sama dengan kode mata kuliah aktif yang sudah ada di CourseRecom.'),
        ('Nama Kelas', 'Ya', 'Contoh: A, B, 5A, 5B, atau 7P. Nama kelas tidak boleh duplikat untuk mata kuliah dan semester yang sama.'),
        ('Nama Dosen (opsional)', 'Tidak', 'Gunakan nama dari direktori dosen atau nama pengajar sesuai dokumen akademik. Akun login tidak wajib.'),
        ('Kode Ruang', 'Ya', 'Gunakan ruang aktif yang tercatat di Admin, misalnya FT301, FT401, FTTI1, atau FTTI2.'),
        ('Hari', 'Ya', 'Senin sampai Minggu.'),
        ('Jam Mulai (HH:MM)', 'Ya', 'Format 24 jam, contoh 07:50 atau 13:00. Slot harus berada pada rentang 07:00–18:00.'),
        ('Kapasitas', 'Ya', 'Bilangan bulat. Tidak boleh melebihi kapasitas fisik ruang.'),
        ('Semester', 'Ya', 'Angka 1 sampai 14.'),
        ('Buka Kelas (Ya/Tidak)', 'Tidak', 'Kosong atau Ya berarti kelas dibuka. Tidak berarti kelas disimpan tertutup.'),
    ]
    for item in instructions:
        guide.append(list(item))
    guide.append([])
    guide.append(['ATURAN OTOMATIS'])
    guide.append(['Jam selesai tidak perlu diisi. Sistem menghitung Jam Mulai + (SKS mata kuliah × 50 menit).'])
    guide.append(['Sistem menolak bentrok ruang/dosen, kode mata kuliah/ruang tidak valid, kelas duplikat, dan kapasitas melebihi ruangan.'])
    guide.append(['Impor bersifat menyeluruh: jika satu baris gagal, seluruh file dibatalkan dan tidak ada kelas yang disimpan sebagian.'])
    guide.freeze_panes = 'A5'
    guide.column_dimensions['A'].width = 33
    guide.column_dimensions['B'].width = 13
    guide.column_dimensions['C'].width = 105
    for cell in guide[1]:
        cell.font = Font(bold=True, size=15, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='075E59')
    for cell in guide[4]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='176B87')
    for row in guide.iter_rows():
        for cell in row:
            cell.alignment = __import__('openpyxl').styles.Alignment(
                vertical='top', wrap_text=True,
            )
    guide.row_dimensions[1].height = 28
    guide.row_dimensions[2].height = 34
    return _excel_response(workbook, 'Template_Impor_Kelas_CourseRecom.xlsx')


@router.post('/admin/classes/import', status_code=201)
async def import_parallel_classes(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles('admin')),
):
    filename = (file.filename or '').strip().lower()
    if not filename.endswith('.xlsx'):
        raise HTTPException(status_code=415, detail='Gunakan file Excel .xlsx dari template CourseRecom.')
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail='Ukuran file impor maksimal 10 MB.')
    if not content.startswith(b'PK'):
        raise HTTPException(status_code=415, detail='File bukan workbook Excel .xlsx yang valid.')

    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail='File Excel tidak dapat dibaca. Unduh template terbaru lalu isi kembali.') from exc
    try:
        if 'Impor Kelas' not in workbook.sheetnames:
            raise HTTPException(status_code=422, detail="Sheet 'Impor Kelas' tidak ditemukan. Gunakan template resmi CourseRecom.")
        worksheet = workbook['Impor Kelas']
        header_values = next(worksheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
        normalize_header = lambda value: ' '.join(str(value or '').strip().casefold().replace('_', ' ').split())
        header_positions = {normalize_header(value): index for index, value in enumerate(header_values) if value is not None}
        aliases = {
            'course': ('kode mata kuliah', 'kode mk', 'course code'),
            'class': ('nama kelas', 'kelas', 'class name'),
            'lecturer': ('nama dosen (opsional)', 'nama dosen', 'dosen pengampu', 'lecturer name'),
            'room': ('kode ruang', 'ruang', 'room'),
            'day': ('hari', 'day'),
            'start': ('jam mulai (hh:mm)', 'jam mulai', 'start time'),
            'capacity': ('kapasitas', 'kapasitas kursi', 'capacity'),
            'semester': ('semester',),
            'open': ('buka kelas (ya/tidak)', 'buka kelas', 'status kelas', 'is open'),
        }
        column_map = {
            key: next((header_positions[candidate] for candidate in candidates if candidate in header_positions), None)
            for key, candidates in aliases.items()
        }
        required = ('course', 'class', 'room', 'day', 'start', 'capacity', 'semester')
        missing = [key for key in required if column_map[key] is None]
        if missing:
            labels = {
                'course': 'Kode Mata Kuliah', 'class': 'Nama Kelas', 'room': 'Kode Ruang',
                'day': 'Hari', 'start': 'Jam Mulai', 'capacity': 'Kapasitas', 'semester': 'Semester',
            }
            raise HTTPException(
                status_code=422,
                detail='Kolom wajib tidak lengkap: ' + ', '.join(labels[key] for key in missing),
            )

        rows = []
        for row_number, values in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
            if not any(value is not None and str(value).strip() for value in values):
                continue
            if len(rows) >= 500:
                raise HTTPException(status_code=413, detail='Maksimal 500 kelas dalam satu file impor.')
            cell = lambda key: values[column_map[key]] if column_map[key] is not None and column_map[key] < len(values) else None
            try:
                course_code = str(cell('course') or '').strip().upper()
                if not course_code:
                    raise ValueError('Kode Mata Kuliah wajib diisi.')
                class_name = str(cell('class') or '').strip()
                if not class_name:
                    raise ValueError('Nama Kelas wajib diisi.')
                capacity = _class_import_number(cell('capacity'), 'Kapasitas', 1, 10000)
                semester = _class_import_number(cell('semester'), 'Semester', 1, 14)
                lecturer_name = str(cell('lecturer') or '').strip() or None
                payload = CourseClassMutation.model_validate({
                    'course_code': course_code,
                    'class_name': class_name,
                    'lecturer_id': None,
                    'lecturer_name': lecturer_name,
                    'room': str(cell('room') or '').strip().upper(),
                    'day': str(cell('day') or '').strip().title(),
                    'start_time': _class_import_time(cell('start')),
                    'end_time': None,
                    'capacity': capacity,
                    'semester': str(semester),
                    'is_open': _class_import_boolean(cell('open')),
                })
                rows.append((row_number, payload))
            except Exception as exc:
                message = str(exc).splitlines()[0]
                raise HTTPException(
                    status_code=422,
                    detail={'message': 'Format baris Excel tidak valid.', 'errors': [{'baris': row_number, 'pesan': message}]},
                ) from exc
    finally:
        workbook.close()

    if not rows:
        raise HTTPException(status_code=422, detail='Tidak ada baris kelas yang dapat diimpor.')

    begin_capacity_transaction(db)
    created = []
    row_errors = []
    try:
        # Lock all referenced room resources in deterministic order.
        room_codes = sorted({payload.room for _, payload in rows})
        locked_rooms = db.query(Room).filter(Room.code.in_(room_codes)).order_by(Room.code).with_for_update().all()
        room_map = {room.code: room for room in locked_rooms}
        lecturer_profiles = db.query(LecturerDirectory).all()
        profile_by_name = {profile.full_name.strip().casefold(): profile for profile in lecturer_profiles if profile.full_name}
        active_accounts = db.query(User).filter(
            User.role == 'dosen',
            User.is_active.is_(True),
        ).all()
        account_by_name = {account.full_name.strip().casefold(): account for account in active_accounts if account.full_name}

        for row_number, payload in rows:
            try:
                course = db.query(Course).filter(
                    Course.code == payload.course_code,
                    Course.is_active.is_(True),
                ).first()
                if not course:
                    raise ValueError(f'Mata kuliah {payload.course_code} tidak ditemukan atau tidak aktif.')
                if db.query(CourseClass.id).filter(
                    CourseClass.course_code == payload.course_code,
                    CourseClass.class_name.ilike(payload.class_name),
                    CourseClass.semester == payload.semester,
                ).first():
                    raise ValueError(f'Kelas {payload.course_code} {payload.class_name} semester {payload.semester} sudah terdaftar.')
                room = room_map.get(payload.room)
                if not room or not room.is_active:
                    raise ValueError(f'Ruang {payload.room} tidak ditemukan atau belum aktif.')
                if room.capacity is not None and payload.capacity > room.capacity:
                    raise ValueError(f'Kapasitas kelas {payload.capacity} melebihi kapasitas ruang {payload.room} ({room.capacity} kursi).')

                lecturer_id = None
                lecturer_name = payload.lecturer_name
                if lecturer_name:
                    profile = profile_by_name.get(lecturer_name.casefold())
                    mapped_id = profile.linked_user_id if profile else None
                    linked_account = next((item for item in active_accounts if item.id == mapped_id), None) if mapped_id else None
                    linked_account = linked_account or account_by_name.get(lecturer_name.casefold())
                    if linked_account:
                        lecturer_id = linked_account.id
                        lecturer_name = linked_account.full_name

                end_time = validate_class_schedule(
                    db,
                    course_code=course.code,
                    room_code=payload.room,
                    day=payload.day,
                    start_time=payload.start_time,
                    lecturer_id=lecturer_id,
                    lecturer_name=lecturer_name,
                )
                item = CourseClass(
                    course_code=course.code,
                    class_name=payload.class_name,
                    lecturer_id=lecturer_id,
                    lecturer_name=lecturer_name,
                    room=payload.room,
                    day=payload.day,
                    start_time=payload.start_time,
                    end_time=end_time,
                    capacity=payload.capacity,
                    semester=payload.semester,
                    is_open=payload.is_open,
                )
                db.add(item)
                db.flush()
                write_audit(
                    db, current_user, 'class_imported', 'course_class', item.id, None,
                    {
                        'excel_filename': filename,
                        'row_number': row_number,
                        'course_code': course.code,
                        'class_name': payload.class_name,
                        'lecturer_name': lecturer_name,
                        'room': payload.room,
                        'day': payload.day,
                        'start_time': payload.start_time,
                        'end_time': end_time,
                        'sks': course.sks,
                        'duration_minutes': course.sks * 50,
                        'capacity': payload.capacity,
                        'semester': payload.semester,
                        'is_open': payload.is_open,
                    },
                )
                created.append({
                    'id': item.id,
                    'course_code': item.course_code,
                    'class_name': item.class_name,
                    'lecturer_name': item.lecturer_name,
                    'room': item.room,
                    'day': item.day,
                    'start_time': item.start_time,
                    'end_time': item.end_time,
                })
            except (ValueError, TypeError) as exc:
                row_errors.append({'baris': row_number, 'pesan': str(exc)})

        if row_errors:
            db.rollback()
            raise HTTPException(
                status_code=422,
                detail={
                    'message': f'Impor dibatalkan. Ditemukan {len(row_errors)} baris bermasalah; tidak ada kelas yang disimpan.',
                    'errors': row_errors[:50],
                },
            )
        db.commit()
    except HTTPException:
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='Data impor bertabrakan dengan perubahan lain. Muat ulang data lalu coba kembali.') from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail='Impor gagal diproses. Tidak ada kelas yang disimpan.') from exc

    return {
        'message': f'{len(created)} kelas berhasil diimpor.',
        'created_count': len(created),
        'classes': created,
    }


@router.post('/admin/classes', status_code=201)
def create_class(payload: CourseClassMutation, db: Session = Depends(get_db), current_user: User = Depends(require_roles('admin'))):
    begin_capacity_transaction(db)
    course = db.query(Course).filter(
        Course.code == payload.course_code.upper(),
        Course.is_active.is_(True),
    ).first()
    if not course:
        raise HTTPException(status_code=422, detail='Mata kuliah tidak ditemukan atau tidak aktif.')
    if db.query(CourseClass.id).filter(
        CourseClass.course_code == payload.course_code.upper(),
        CourseClass.class_name.ilike(payload.class_name.strip()),
        CourseClass.semester == payload.semester,
    ).first():
        raise HTTPException(status_code=409, detail='Nama kelas paralel sudah digunakan untuk mata kuliah dan semester ini.')

    try:
        # Lock resources to serialize simultaneous bookings.
        room = db.query(Room).filter(Room.code == payload.room).with_for_update().first()
        if not room:
            raise ValueError(f'Ruang {payload.room} belum terdaftar.')
        if not room.is_active:
            raise ValueError(f'Ruang {payload.room} belum diaktifkan Admin setelah verifikasi.')
        if room.capacity is not None and payload.capacity > room.capacity:
            raise ValueError(f'Kapasitas kelas ({payload.capacity}) melebihi kapasitas fisik ruang {payload.room} ({room.capacity} kursi).')
        linked_lecturer = None
        if payload.lecturer_id is not None:
            linked_lecturer = db.query(User).filter(
                User.id == payload.lecturer_id,
                User.role == 'dosen',
                User.is_active.is_(True),
            ).with_for_update().first()
            if not linked_lecturer:
                raise ValueError('Dosen pengampu tidak valid atau nonaktif.')
        lecturer_display_name = (payload.lecturer_name or (linked_lecturer.full_name if linked_lecturer else '')).strip()
        end_time = validate_class_schedule(
            db,
            course_code=course.code,
            room_code=payload.room,
            day=payload.day,
            start_time=payload.start_time,
            lecturer_id=payload.lecturer_id,
            lecturer_name=lecturer_display_name or None,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if payload.end_time and payload.end_time != end_time:
        raise HTTPException(
            status_code=422,
            detail=f'Jam selesai dihitung otomatis berdasarkan {course.sks} SKS: {end_time} ({course.sks * 50} menit).',
        )
    item = CourseClass(
        course_code=course.code,
        class_name=payload.class_name.strip(),
        lecturer_id=payload.lecturer_id,
        lecturer_name=lecturer_display_name or None,
        room=payload.room,
        day=payload.day,
        start_time=payload.start_time,
        end_time=end_time,
        capacity=payload.capacity,
        semester=payload.semester,
        is_open=payload.is_open,
    )
    db.add(item)
    db.flush()
    write_audit(
        db, current_user, 'class_created', 'course_class', item.id, None,
        {
            **payload.model_dump(),
            'lecturer_name': item.lecturer_name,
            'end_time': end_time,
            'duration_minutes': course.sks * 50,
            'sks': course.sks,
        },
    )
    db.commit()
    db.refresh(item)
    return {
        'id': item.id, 'course_code': item.course_code, 'class_name': item.class_name,
        'lecturer_id': item.lecturer_id, 'lecturer_name': item.lecturer_name,
        'room': item.room, 'day': item.day, 'start_time': item.start_time,
        'end_time': item.end_time, 'is_open': item.is_open,
    }


@router.put('/admin/classes/{class_id}')
def update_class(class_id: int, payload: CourseClassMutation, db: Session = Depends(get_db), current_user: User = Depends(require_roles('admin'))):
    item = db.query(CourseClass).filter(CourseClass.id == class_id).first()
    if not item:
        raise HTTPException(status_code=404, detail='Kelas tidak ditemukan.')

    begin_capacity_transaction(db)
    lock_capacity_courses(db, [item.course_code, payload.course_code.upper()], [class_id])
    room_codes = sorted({item.room.strip().upper(), payload.room.strip().upper()})
    locked_rooms = db.query(Room).filter(Room.code.in_(room_codes)).order_by(Room.code).with_for_update().all()
    room_map = {room.code: room for room in locked_rooms}
    if payload.room not in room_map or not room_map[payload.room].is_active:
        raise HTTPException(status_code=409, detail=f'Ruang {payload.room} belum tersedia/aktif.')
    if room_map[payload.room].capacity is not None and payload.capacity > room_map[payload.room].capacity:
        raise HTTPException(
            status_code=409,
            detail=f'Kapasitas kelas ({payload.capacity}) melebihi kapasitas fisik ruang {payload.room} ({room_map[payload.room].capacity} kursi).',
        )
    linked_lecturer = None
    if payload.lecturer_id is not None:
        linked_lecturer = db.query(User).filter(
            User.id == payload.lecturer_id,
            User.role == 'dosen',
            User.is_active.is_(True),
        ).with_for_update().first()
        if not linked_lecturer:
            raise HTTPException(status_code=422, detail='Dosen pengampu tidak valid atau nonaktif.')
    item = db.query(CourseClass).filter(CourseClass.id == class_id).with_for_update().first()
    if not item:
        raise HTTPException(status_code=404, detail='Kelas tidak ditemukan.')

    course = db.query(Course).filter(
        Course.code == payload.course_code.upper(),
        Course.is_active.is_(True),
    ).first()
    if not course:
        raise HTTPException(status_code=422, detail='Mata kuliah tidak valid atau tidak aktif.')
    if db.query(CourseClass.id).filter(
        CourseClass.id != class_id,
        CourseClass.course_code == payload.course_code.upper(),
        CourseClass.class_name.ilike(payload.class_name.strip()),
        CourseClass.semester == payload.semester,
    ).first():
        raise HTTPException(status_code=409, detail='Nama kelas paralel sudah digunakan untuk mata kuliah dan semester ini.')

    occupied = class_occupancy(db, item.id)
    if payload.capacity < occupied:
        raise HTTPException(status_code=409, detail=f'Kapasitas kelas tidak dapat dikurangi di bawah {occupied} kursi yang sudah terpakai.')
    lecturer_display_name = (payload.lecturer_name or (linked_lecturer.full_name if linked_lecturer else '')).strip()
    old = {
        column: getattr(item, column)
        for column in (
            'course_code', 'class_name', 'lecturer_id', 'lecturer_name', 'room',
            'day', 'start_time', 'end_time', 'capacity', 'semester', 'is_open',
        )
    }
    try:
        end_time = validate_class_schedule(
            db,
            course_code=course.code,
            room_code=payload.room,
            day=payload.day,
            start_time=payload.start_time,
            lecturer_id=payload.lecturer_id,
            lecturer_name=lecturer_display_name or None,
            exclude_class_id=class_id,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if payload.end_time and payload.end_time != end_time:
        raise HTTPException(
            status_code=422,
            detail=f'Jam selesai dihitung otomatis berdasarkan {course.sks} SKS: {end_time} ({course.sks * 50} menit).',
        )

    new_values = payload.model_dump()
    new_values.update({
        'course_code': payload.course_code.strip().upper(),
        'class_name': payload.class_name.strip(),
        'lecturer_name': lecturer_display_name or None,
        'room': payload.room.strip().upper(),
        'day': payload.day.strip(),
        'start_time': payload.start_time,
        'end_time': end_time,
        'semester': str(payload.semester).strip(),
    })
    protected_fields = (
        'course_code', 'class_name', 'lecturer_id', 'lecturer_name', 'room', 'day',
        'start_time', 'end_time', 'semester', 'is_open',
    )
    changed_fields = [field for field in protected_fields if old[field] != new_values[field]]
    if occupied and changed_fields:
        raise HTTPException(
            status_code=409,
            detail=(
                f'Kelas memiliki {occupied} peserta atau reservasi aktif. '
                'Mata kuliah, kelas, dosen, ruang, jadwal, semester, dan status buka/tutup '
                'dikunci agar data KRS tidak berubah diam-diam. Hanya kapasitas yang boleh disesuaikan.'
            ),
        )
    for key, value in new_values.items():
        setattr(item, key, value)
    write_audit(
        db, current_user, 'class_updated', 'course_class', item.id, old,
        {**new_values, 'sks': course.sks, 'duration_minutes': course.sks * 50},
    )
    db.commit()
    db.refresh(item)
    return {
        'id': item.id, 'course_code': item.course_code, 'is_open': item.is_open,
        'occupied': occupied, 'capacity': item.capacity, 'room': item.room,
        'day': item.day, 'start_time': item.start_time, 'end_time': item.end_time,
        'lecturer_name': item.lecturer_name,
    }


@router.delete('/admin/classes/{class_id}', status_code=204)
def close_parallel_class(class_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles('admin'))):
    item = db.query(CourseClass).filter(CourseClass.id == class_id).first()
    if not item:
        raise HTTPException(status_code=404, detail='Kelas tidak ditemukan.')
    begin_capacity_transaction(db)
    lock_capacity_courses(db, [item.course_code], [class_id])
    item = db.query(CourseClass).filter(CourseClass.id == class_id).with_for_update().first()
    if not item:
        raise HTTPException(status_code=404, detail='Kelas tidak ditemukan.')
    if not item.is_open:
        return None
    occupied = class_occupancy(db, item.id)
    if occupied:
        raise HTTPException(status_code=409, detail=f'Kelas tidak dapat ditutup karena masih memiliki {occupied} peserta/ reservasi.')
    old = {'is_open': item.is_open}
    item.is_open = False
    write_audit(db, current_user, 'class_closed', 'course_class', item.id, old, {'is_open': False})
    db.commit()
    return None
