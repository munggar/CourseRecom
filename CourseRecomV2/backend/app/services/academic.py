from collections.abc import Mapping, Sequence

from sqlalchemy.orm import Session

from app.models import Course, CourseClass, User, Room
from app.services.recommendation import build_recommendation_result
from app.services.validation import has_schedule_conflict


def class_selection_map(entries: Sequence[Mapping[str, object]]) -> dict[str, int]:
    """Extract saved class choices from modern KRS course objects."""
    selections: dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        code = str(entry.get('code') or '').strip().upper()
        class_id = entry.get('class_id')
        if code and class_id is not None:
            try:
                selections[code] = int(class_id)
            except (TypeError, ValueError) as exc:
                raise ValueError(f'Pilihan kelas tersimpan untuk {code} tidak valid.') from exc
    return selections


def validate_course_selection(
    db: Session,
    student: User,
    course_codes: Sequence[str],
    semester: int,
    class_selections: Mapping[str, int] | None = None,
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

    # KRS validation must know both elective recommendations and mandatory
    # courses, even though only electives are exposed in the recommendation list.
    selectable_courses = [
        *(result.get('recommendations') or []),
        *(result.get('mandatory_courses') or []),
    ]
    recommendations = {item['code']: item for item in selectable_courses}
    rejected = {item['code']: item for item in result['rejected']}
    mandatory_codes = {
        code for code, item in recommendations.items()
        if item.get('mandatory') is True
        or 'wajib' in str(item.get('category') or '').casefold()
    }
    missing_mandatory = sorted(mandatory_codes - set(codes))
    if missing_mandatory:
        raise ValueError(
            'Mata kuliah wajib harus tetap ada di KRS: '
            + ', '.join(missing_mandatory)
        )
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

    selected = [dict(recommendations[code]) for code in codes]
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
    selections = {str(code).strip().upper(): int(class_id) for code, class_id in (class_selections or {}).items()}
    unknown_selections = sorted(set(selections) - set(codes))
    if unknown_selections:
        raise ValueError('Pilihan kelas mengacu pada mata kuliah yang tidak dipilih: ' + ', '.join(unknown_selections))

    schedules: list[tuple[str, str]] = []
    for item in selected:
        code = item['code']
        course = catalog.get(code)
        if course is None:
            raise ValueError(f'Mata kuliah {code} tidak aktif.')

        sections = db.query(CourseClass).filter(
            CourseClass.course_code == code,
            CourseClass.semester == str(semester),
        ).order_by(CourseClass.class_name, CourseClass.id).all()
        if sections:
            class_id = selections.get(code)
            if class_id is None:
                raise ValueError(f'Pilih kelas paralel untuk mata kuliah {code}.')
            section = next((candidate for candidate in sections if candidate.id == class_id), None)
            if section is None or not section.is_open:
                raise ValueError(f'Kelas paralel yang dipilih untuk {code} tidak tersedia atau sudah ditutup.')
            room = db.query(Room).filter(
                Room.code == section.room.strip().upper(),
                Room.is_active.is_(True),
            ).first()
            if room is None:
                raise ValueError(
                    f'Ruang {section.room} untuk mata kuliah {code} belum diverifikasi/diaktifkan Admin.'
                )
            if room.capacity is not None and section.capacity > room.capacity:
                raise ValueError(
                    f'Kapasitas kelas {code} melebihi kapasitas fisik ruang {section.room}.'
                )
            lecturer = db.query(User).filter(User.id == section.lecturer_id, User.role == 'dosen').first() if section.lecturer_id else None
            item.update({
                'class_id': section.id,
                'class_name': section.class_name,
                'lecturer_id': section.lecturer_id,
                'lecturer_name': section.lecturer_name or (lecturer.full_name if lecturer else ''),
                'campus': 'Ps-Rebo FT',
                'room': section.room,
                'day': section.day,
                'start_time': section.start_time,
                'end_time': section.end_time,
                'schedule': f'{section.day}, {section.start_time}-{section.end_time}',
            })
            effective_day = section.day
            effective_time = f'{section.start_time}-{section.end_time}'
        else:
            if code in selections:
                raise ValueError(f'Kelas paralel untuk {code} tidak terdaftar pada semester {semester}.')
            item.update({
                'class_id': None,
                'class_name': course.default_class_name or None,
                'lecturer_id': None,
                'lecturer_name': course.default_lecturer_name or '',
                'room': '',
                'campus': '',
                'schedule': f'{course.day} {course.time}'.strip(),
            })
            effective_day = course.day or ''
            effective_time = course.time or ''

        if effective_day and effective_time:
            if has_schedule_conflict(effective_day, effective_time, schedules):
                raise ValueError(f'Jadwal mata kuliah {code} berbenturan dengan mata kuliah lain pada KRS.')
            schedules.append((effective_day, effective_time))
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
