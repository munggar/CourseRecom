from collections.abc import Mapping, Sequence

from sqlalchemy.orm import Session

from app.models import Course, User
from app.services.recommendation import build_recommendation_result
from app.services.validation import has_schedule_conflict


def validate_course_selection(
    db: Session,
    student: User,
    course_codes: Sequence[str],
    semester: int,
) -> list[dict]:
    codes = [code.strip().upper() for code in course_codes]
    if not codes:
        raise ValueError('Pilih minimal satu mata kuliah.')
    if len(codes) != len(set(codes)):
        raise ValueError('Mata kuliah duplikat tidak diperbolehkan.')

    result = build_recommendation_result(db, student)
    if result['status'] != 'ready':
        raise ValueError(result.get('message') or 'KHS terkonfirmasi diperlukan.')
    if result['target_semester'] != semester:
        raise ValueError('Semester rencana studi tidak sesuai dengan semester rekomendasi.')

    recommendations = {item['code']: item for item in result['recommendations']}
    rejected = {item['code']: item for item in result['rejected']}
    unavailable = [code for code in codes if code not in recommendations]
    if unavailable:
        explanations = [
            f"{code}: {rejected[code]['reason_block']}"
            for code in unavailable
            if code in rejected
        ]
        if explanations:
            raise ValueError('Mata kuliah tidak memenuhi aturan akademik: ' + '; '.join(explanations))
        raise ValueError(
            'Mata kuliah tidak aktif, tidak ditawarkan, atau bukan bagian semester ini: '
            + ', '.join(unavailable)
        )

    selected = [recommendations[code] for code in codes]
    quota = result['profile']['kuota_sks']
    total_sks = sum(course['sks'] for course in selected)
    if total_sks > quota:
        raise ValueError(f'Total SKS melebihi batas maksimum ({quota} SKS).')

    catalog = {
        course.code: course
        for course in db.query(Course).filter(
            Course.code.in_(codes),
            Course.is_active.is_(True),
        ).all()
    }
    schedules: list[tuple[str, str]] = []
    for code in codes:
        course = catalog.get(code)
        if course is None:
            raise ValueError(f'Mata kuliah {code} tidak aktif.')
        if course.day and course.time:
            if has_schedule_conflict(course.day, course.time, schedules):
                raise ValueError(f'Jadwal mata kuliah {code} berbenturan.')
            schedules.append((course.day, course.time))
    return selected


def latest_attempt_gpa(attempts: Sequence[Mapping[str, object]]) -> float | None:
    latest_by_course: dict[str, tuple[int, int, float, int]] = {}
    for index, attempt in enumerate(attempts):
        code = str(attempt['code']).strip().upper()
        semester = int(attempt['semester'])
        grade_point = float(attempt['grade_point'])
        credits = int(attempt['sks'])
        previous = latest_by_course.get(code)
        if previous is None or (semester, index) > (previous[0], previous[1]):
            latest_by_course[code] = (semester, index, grade_point, credits)

    total_credits = sum(item[3] for item in latest_by_course.values())
    if total_credits == 0:
        return None
    weighted_points = sum(item[2] * item[3] for item in latest_by_course.values())
    return round(weighted_points / total_credits, 2)


def earned_credits(attempts: Sequence[Mapping[str, object]], passing_grades: set[str]) -> int:
    credits_by_course: dict[str, int] = {}
    for attempt in attempts:
        if str(attempt['grade']).upper() not in passing_grades:
            continue
        code = str(attempt['code']).strip().upper()
        credits_by_course[code] = max(credits_by_course.get(code, 0), int(attempt['sks']))
    return sum(credits_by_course.values())
