import json

from sqlalchemy.orm import Session

from app.models import Course, CourseClass, KprsRequest, StudyPlan


class CapacityError(ValueError):
    pass


def _entry_code(entry) -> str | None:
    if isinstance(entry, str):
        return entry.strip().upper()
    if isinstance(entry, dict):
        code = entry.get('code')
        return str(code).strip().upper() if code else None
    return None


def begin_capacity_transaction(db: Session) -> None:
    db.commit()
    if db.get_bind().dialect.name == 'sqlite':
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')


def lock_capacity_courses(
    db: Session,
    course_codes: list[str],
    class_ids: list[int] | None = None,
) -> None:
    if db.get_bind().dialect.name == 'sqlite':
        return
    (
        db.query(Course)
        .filter(Course.code.in_(course_codes))
        .order_by(Course.code)
        .with_for_update()
        .all()
    )
    if class_ids:
        (
            db.query(CourseClass)
            .filter(CourseClass.id.in_(class_ids))
            .order_by(CourseClass.id)
            .with_for_update()
            .all()
        )


def course_occupancy(
    db: Session,
    code: str,
    *,
    exclude_plan_id: int | None = None,
    exclude_kprs_request_id: int | None = None,
) -> int:
    used = 0
    plans_query = db.query(StudyPlan.courses_json).filter(
        StudyPlan.status.in_(('pending', 'approved')),
    )
    if exclude_plan_id is not None:
        plans_query = plans_query.filter(StudyPlan.id != exclude_plan_id)
    for (courses_json,) in plans_query.all():
        try:
            plan_courses = json.loads(courses_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError('Data mata kuliah pada KRS tersimpan tidak valid.') from exc
        if not isinstance(plan_courses, list):
            raise ValueError('Data mata kuliah pada KRS tersimpan tidak valid.')
        if any(_entry_code(item) == code.strip().upper() for item in plan_courses):
            used += 1

    requests_query = db.query(KprsRequest).filter(KprsRequest.status == 'pending')
    if exclude_kprs_request_id is not None:
        requests_query = requests_query.filter(KprsRequest.id != exclude_kprs_request_id)
    for request in requests_query.all():
        try:
            before = json.loads(request.before_json)
            after = json.loads(request.after_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError('Data mata kuliah pada pengajuan KPRS tersimpan tidak valid.') from exc
        if not isinstance(before, list) or not isinstance(after, list):
            raise ValueError('Data mata kuliah pada pengajuan KPRS tersimpan tidak valid.')
        before_codes = {_entry_code(item) for item in before}
        after_codes = {_entry_code(item) for item in after}
        if code.strip().upper() in after_codes - before_codes:
            used += 1
    return used


def class_occupancy(
    db: Session,
    class_id: int,
    *,
    exclude_plan_id: int | None = None,
    exclude_kprs_request_id: int | None = None,
) -> int:
    section = db.query(CourseClass).filter(CourseClass.id == class_id).first()
    if not section:
        raise ValueError('Kelas paralel tidak ditemukan.')
    used = 0
    plans_query = db.query(StudyPlan.courses_json).filter(StudyPlan.status.in_(('pending', 'approved')))
    if exclude_plan_id is not None:
        plans_query = plans_query.filter(StudyPlan.id != exclude_plan_id)
    for (courses_json,) in plans_query.all():
        try:
            entries = json.loads(courses_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError('Data mata kuliah pada KRS tersimpan tidak valid.') from exc
        if not isinstance(entries, list):
            raise ValueError('Data mata kuliah pada KRS tersimpan tidak valid.')
        for entry in entries:
            if _entry_code(entry) != section.course_code.strip().upper():
                continue
            assigned_class = entry.get('class_id') if isinstance(entry, dict) else None
            # Legacy KRS without a class assignment reserves a seat conservatively
            # in every parallel section until it is reconciled.
            if assigned_class is None or str(assigned_class) == str(class_id):
                used += 1

    requests_query = db.query(KprsRequest).filter(KprsRequest.status == 'pending')
    if exclude_kprs_request_id is not None:
        requests_query = requests_query.filter(KprsRequest.id != exclude_kprs_request_id)
    for request in requests_query.all():
        try:
            before = json.loads(request.before_json)
            after = json.loads(request.after_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError('Data mata kuliah pada pengajuan KPRS tersimpan tidak valid.') from exc
        before_by_code = {_entry_code(entry): entry for entry in before if _entry_code(entry)}
        for entry in after:
            if _entry_code(entry) != section.course_code.strip().upper():
                continue
            assigned_class = entry.get('class_id') if isinstance(entry, dict) else None
            if str(assigned_class or '') != str(class_id):
                continue
            previous = before_by_code.get(section.course_code.strip().upper())
            previous_class_id = previous.get('class_id') if isinstance(previous, dict) else None
            if previous is None or str(previous_class_id or '') != str(class_id):
                used += 1
    return used


def assert_course_capacity(
    db: Session,
    courses: list[dict],
    *,
    exclude_plan_id: int | None = None,
    exclude_kprs_request_id: int | None = None,
) -> None:
    for selected in courses:
        code = selected['code']
        course = db.query(Course).filter(
            Course.code == code,
            Course.is_active.is_(True),
        ).first()
        if not course:
            raise ValueError(f'Mata kuliah {code} tidak aktif.')

        course_used = course_occupancy(
            db,
            code,
            exclude_plan_id=exclude_plan_id,
            exclude_kprs_request_id=exclude_kprs_request_id,
        )
        course_capacity = course.capacity if course.capacity is not None else 40
        if course_used >= course_capacity:
            raise CapacityError(f'Kuota keseluruhan mata kuliah {code} sudah penuh.')
        class_id = selected.get('class_id')
        if class_id is not None:
            section = db.query(CourseClass).filter(
                CourseClass.id == int(class_id),
                CourseClass.course_code == code,
                CourseClass.is_open.is_(True),
            ).first()
            if not section:
                raise ValueError(f'Kelas paralel untuk {code} tidak tersedia.')
            used = class_occupancy(
                db,
                section.id,
                exclude_plan_id=exclude_plan_id,
                exclude_kprs_request_id=exclude_kprs_request_id,
            )
            if used >= section.capacity:
                raise CapacityError(f'Kuota kelas {section.class_name} untuk {code} sudah penuh.')
            continue

        if course_used >= course_capacity:
            raise CapacityError(f'Kuota mata kuliah {code} sudah penuh.')
