import json
from datetime import timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.deps import get_db, require_roles
from app.models import (
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
)
from app.schemas import CourseMutation, AdvisorMapping, SystemSettingUpdate, StudyPlanOverride, CourseClassMutation, LecturerRegistration, LecturerUpdate
from app.services.academic import validate_course_selection
from app.services.course_catalog import parse_course_catalog
from app.services.capacity import (
    CapacityError,
    assert_course_capacity,
    begin_capacity_transaction,
    course_occupancy,
    lock_capacity_courses,
)
from app.services.recommendation import train_similarity_model
from app.services.audit import write_audit
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
        }
        for lecturer in lecturers
    ]


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
        if replace_catalog:
            db.query(Course).update({'is_active': False}, synchronize_session=False)

        for item in courses:
            course = db.query(Course).filter(Course.code == item['code']).first()
            if not course:
                course = Course(code=item['code'])
                db.add(course)
            for field, value in item.items():
                if field == 'available_semesters':
                    value = value
                setattr(course, field, value)
            course.is_active = True
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
        courses = validate_course_selection(db, student, codes, plan.semester)
        lock_capacity_courses(db, [course['code'] for course in courses])
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


@router.get('/admin/classes')
def list_classes(db: Session = Depends(get_db), current_user: User = Depends(require_roles('admin'))):
    return [{
        'id': item.id,
        'course_code': item.course_code,
        'class_name': item.class_name,
        'lecturer_id': item.lecturer_id,
        'room': item.room,
        'day': item.day,
        'start_time': item.start_time,
        'end_time': item.end_time,
        'capacity': item.capacity,
        'semester': item.semester,
        'is_open': item.is_open,
    } for item in db.query(CourseClass).order_by(CourseClass.semester, CourseClass.course_code).all()]


@router.post('/admin/classes', status_code=201)
def create_class(payload: CourseClassMutation, db: Session = Depends(get_db), current_user: User = Depends(require_roles('admin'))):
    course = db.query(Course).filter(Course.code == payload.course_code.upper(), Course.is_active.is_(True)).first()
    if not course:
        raise HTTPException(status_code=422, detail='Mata kuliah tidak ditemukan atau tidak aktif.')
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=422, detail='Jam selesai harus setelah jam mulai.')
    if payload.lecturer_id is not None and not db.query(User).filter(User.id == payload.lecturer_id, User.role == 'dosen').first():
        raise HTTPException(status_code=422, detail='Dosen pengampu tidak valid.')
    for other in db.query(CourseClass).filter(CourseClass.day == payload.day, CourseClass.is_open.is_(True)).all():
        if other.semester != payload.semester:
            continue
        overlaps = payload.start_time < other.end_time and payload.end_time > other.start_time
        if overlaps and payload.room == other.room:
            raise HTTPException(status_code=409, detail='Ruangan berbenturan pada jadwal tersebut.')
        if overlaps and payload.lecturer_id is not None and payload.lecturer_id == other.lecturer_id:
            raise HTTPException(status_code=409, detail='Dosen pengampu berbenturan pada jadwal tersebut.')
    item = CourseClass(**payload.model_dump(), course_code=payload.course_code.upper())
    db.add(item)
    write_audit(db, current_user, 'class_created', 'course_class', payload.course_code.upper(), None, payload.model_dump())
    db.commit()
    db.refresh(item)
    return {'id': item.id, 'course_code': item.course_code, 'class_name': item.class_name, 'is_open': item.is_open}


@router.put('/admin/classes/{class_id}')
def update_class(class_id: int, payload: CourseClassMutation, db: Session = Depends(get_db), current_user: User = Depends(require_roles('admin'))):
    item = db.query(CourseClass).filter(CourseClass.id == class_id).first()
    if not item:
        raise HTTPException(status_code=404, detail='Kelas tidak ditemukan.')
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=422, detail='Jam selesai harus setelah jam mulai.')
    course = db.query(Course).filter(Course.code == payload.course_code.upper(), Course.is_active.is_(True)).first()
    if not course:
        raise HTTPException(status_code=422, detail='Mata kuliah tidak valid atau tidak aktif.')
    if payload.lecturer_id is not None and not db.query(User).filter(User.id == payload.lecturer_id, User.role == 'dosen').first():
        raise HTTPException(status_code=422, detail='Dosen pengampu tidak valid.')
    for other in db.query(CourseClass).filter(CourseClass.id != class_id, CourseClass.day == payload.day, CourseClass.is_open.is_(True)).all():
        if other.semester != payload.semester:
            continue
        overlaps = payload.start_time < other.end_time and payload.end_time > other.start_time
        if overlaps and payload.room == other.room:
            raise HTTPException(status_code=409, detail='Ruangan berbenturan pada jadwal tersebut.')
        if overlaps and payload.lecturer_id is not None and payload.lecturer_id == other.lecturer_id:
            raise HTTPException(status_code=409, detail='Dosen pengampu berbenturan pada jadwal tersebut.')
    old = {column: getattr(item, column) for column in ('course_code', 'class_name', 'lecturer_id', 'room', 'day', 'start_time', 'end_time', 'capacity', 'semester', 'is_open')}
    for key, value in payload.model_dump().items():
        setattr(item, key, value.upper() if key == 'course_code' else value)
    write_audit(db, current_user, 'class_updated', 'course_class', item.id, old, payload.model_dump())
    db.commit()
    db.refresh(item)
    return {'id': item.id, 'course_code': item.course_code, 'is_open': item.is_open}
