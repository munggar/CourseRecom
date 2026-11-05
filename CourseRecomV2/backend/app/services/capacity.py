import json

from sqlalchemy.orm import Session

from app.models import Course, KprsRequest, StudyPlan


class CapacityError(ValueError):
    pass


def begin_capacity_transaction(db: Session) -> None:
    db.commit()
    if db.get_bind().dialect.name == 'sqlite':
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')


def lock_capacity_courses(db: Session, course_codes: list[str]) -> None:
    if db.get_bind().dialect.name == 'sqlite':
        return
    (
        db.query(Course)
        .filter(Course.code.in_(course_codes))
        .order_by(Course.code)
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
        if any(item.get('code') == code for item in plan_courses if isinstance(item, dict)):
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
        before_codes = {item.get('code') for item in before if isinstance(item, dict)}
        after_codes = {item.get('code') for item in after if isinstance(item, dict)}
        if code in after_codes - before_codes:
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

        used = course_occupancy(
            db,
            code,
            exclude_plan_id=exclude_plan_id,
            exclude_kprs_request_id=exclude_kprs_request_id,
        )

        capacity = course.capacity if course.capacity is not None else 40
        if used >= capacity:
            raise CapacityError(f'Kuota mata kuliah {code} sudah penuh.')
