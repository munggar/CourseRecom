import json
import math
import re
from collections import defaultdict

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Course, KhsDocument, RecommendationModelVersion, StudentRecord, User
from app.services.time_utils import utc_now_naive
from app.services.khs_parser import GRADE_POINTS
from app.services.validation import get_sks_quota


PASSING_GRADES = settings.get_passing_grades()
INTEREST_ALIASES = {
    'manajemen sistem informasi': {
        'manajemen sistem informasi',
        'manajemen & sistem informasi',
        'peminatan manajemen si',
        'peminatan msi',
        'sistem informasi',
        'information systems',
        'msi',
    },
    'kecerdasan bisnis': {
        'kecerdasan bisnis',
        'peminatan kecerdasan bisnis',
        'kb',
        'data',
        'data science',
        'ai/ml',
        'ai',
        'artificial intelligence',
        'machine learning',
        'business intelligence',
        'data analytics',
    },
}


def _passed(record: StudentRecord) -> bool:
    return record.grade.upper() in PASSING_GRADES


def _catalog_code_for_record(code: str, catalog_codes: set[str]) -> str:
    if code in catalog_codes:
        return code
    if code.isdigit():
        normalized_code = re.sub(r'0{2,}', '0', code)
        if normalized_code in catalog_codes:
            return normalized_code
    return code


def _course_identity(code: str, name: str | None = None) -> str:
    normalized_name = re.sub(r'[\W_]+', ' ', (name or '').casefold()).strip()
    if normalized_name:
        return f'name:{normalized_name}'
    return f'code:{code.strip().upper()}'


def _record_grade_value(record: StudentRecord) -> float:
    if record.grade_point is not None:
        return record.grade_point
    return GRADE_POINTS.get(record.grade.upper(), 0.0)


def _similarity(student_records: list[StudentRecord], peer_records: list[StudentRecord]) -> float:
    student_grades: dict[str, str] = {}
    peer_grades: dict[str, str] = {}
    for records, grades in (
        (student_records, student_grades),
        (peer_records, peer_grades),
    ):
        for record in records:
            identity = _course_identity(record.course_code, record.course_name)
            previous_grade = grades.get(identity)
            if (
                previous_grade is None
                or _record_grade_value(record) > GRADE_POINTS.get(previous_grade, 0.0)
            ):
                grades[identity] = record.grade.upper()

    student_codes = set(student_grades)
    peer_codes = set(peer_grades)
    if not student_codes or not peer_codes:
        return 0.0
    union = student_codes | peer_codes
    jaccard = len(student_codes & peer_codes) / len(union)

    common = {
        code for code in student_grades.keys() & peer_grades.keys()
        if student_grades[code] and peer_grades[code]
    }
    grade_similarity = (
        sum(student_grades[code] == peer_grades[code] for code in common) / len(common)
        if common
        else 0.0
    )
    return 0.8 * jaccard + 0.2 * grade_similarity


def _interest_matches(category: str, interests: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r'[\W_]+', ' ', value.casefold()).strip()

    def groups_for(values: list[str]) -> set[str]:
        groups = set()
        for value in values:
            normalized_value = normalize(value)
            for group, aliases in INTEREST_ALIASES.items():
                normalized_aliases = {normalize(alias) for alias in aliases | {group}}
                if any(
                    normalized_value == alias
                    or (
                        len(alias) > 3
                        and f' {alias} ' in f' {normalized_value} '
                    )
                    for alias in normalized_aliases
                ):
                    groups.add(group)
        return groups

    selected_interests = groups_for([tag.strip() for tag in interests.split(',') if tag.strip()])
    matching_interests = groups_for([category.strip()])
    return bool(selected_interests.intersection(matching_interests))


def _peer_course_scores(
    db: Session,
    student: User,
    target_semester: int,
    student_records: list[StudentRecord],
) -> tuple[dict[str, float], dict[str, tuple[int, int]], int]:
    all_records = db.query(StudentRecord).filter(StudentRecord.semester.is_not(None)).all()
    peer_by_student: dict[int, list[StudentRecord]] = defaultdict(list)
    for record in all_records:
        if record.student_id != student.id:
            peer_by_student[record.student_id].append(record)

    peers: list[tuple[float, list[StudentRecord], list[StudentRecord]]] = []
    for records in peer_by_student.values():
        history = [record for record in records if record.semester < target_semester]
        next_semester = [record for record in records if record.semester == target_semester]
        if not history or not next_semester:
            continue
        score = _similarity(student_records, history)
        if score > 0:
            peers.append((score, history, next_semester))

    peers.sort(key=lambda item: item[0], reverse=True)
    peers = peers[:20]
    total_similarity = sum(peer[0] for peer in peers)
    weighted_scores: dict[str, float] = defaultdict(float)
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for similarity, _, courses in peers:
        unique_courses = {
            _course_identity(record.course_code, record.course_name): record
            for record in courses
        }
        for identity in unique_courses:
            weighted_scores[identity] += similarity
            counts[identity][0] += 1
        for code in counts:
            counts[code][1] = len(peers)

    normalized = {
        code: score / total_similarity
        for code, score in weighted_scores.items()
    } if total_similarity else {}
    return normalized, {code: (count[0], count[1]) for code, count in counts.items()}, len(peers)


def _additional_prerequisite_blocks(
    prerequisite_text: str,
    student: User,
    records: list[StudentRecord],
    passed_sks: int,
) -> list[str]:
    text = prerequisite_text.casefold()
    blocks = []

    credit_threshold = re.search(r'>\s*(\d+)\s*sks', text)
    if credit_threshold and passed_sks <= int(credit_threshold.group(1)):
        blocks.append(f'Syarat SKS lulus harus lebih dari {credit_threshold.group(1)} SKS')

    minimum_credits = re.search(r'minimum\s+(\d+)\s*%\s*sks\s+total', text)
    if minimum_credits:
        required_sks = math.ceil(settings.total_curriculum_sks * int(minimum_credits.group(1)) / 100)
        if passed_sks < required_sks:
            blocks.append(f'Syarat minimal {minimum_credits.group(1)}% SKS ({required_sks} SKS)')

    minimum_ipk = re.search(r'ipk\s+minimal\s+(\d+(?:[.,]\d+)?)', text)
    if minimum_ipk:
        threshold = float(minimum_ipk.group(1).replace(',', '.'))
        if (student.ipk or 0) < threshold:
            blocks.append(f'Syarat IPK minimal {threshold:.2f}')

    if re.search(r'nilai\s+d\s+maksimal\s+(\d+)\s*mk', text):
        max_d_grades = int(re.search(r'nilai\s+d\s+maksimal\s+(\d+)\s*mk', text).group(1))
        latest_attempts: dict[str, StudentRecord] = {}
        for record in records:
            current = latest_attempts.get(record.course_code)
            if current is None or (record.semester or 0) > (current.semester or 0):
                latest_attempts[record.course_code] = record
        d_count = sum(record.grade.upper() == 'D' for record in latest_attempts.values())
        if d_count > max_d_grades:
            blocks.append(f'Jumlah nilai D melebihi batas maksimal {max_d_grades} mata kuliah')

    if 'ujian proposal' in text:
        blocks.append('Kelulusan ujian proposal perlu diverifikasi sebelum mengambil mata kuliah ini')

    return blocks


def build_recommendation_result(db: Session, student: User) -> dict:
    latest_document = (
        db.query(KhsDocument)
        .filter(KhsDocument.student_id == student.id, KhsDocument.status == 'confirmed')
        .order_by(KhsDocument.created_at.desc(), KhsDocument.id.desc())
        .first()
    )
    if not latest_document:
        return {
            'status': 'khs_required',
            'message': 'Unggah dan konfirmasi KHS lengkap sebelum meminta rekomendasi.',
            'profile': None,
            'target_semester': None,
            'model': None,
            'recommendations': [],
            'rejected': [],
            'semester_antara': [],
        }

    document_data = json.loads(latest_document.parsed_data)
    profile_data = document_data['metadata']
    records = db.query(StudentRecord).filter(StudentRecord.student_id == student.id).all()
    current_semester = int(profile_data['current_semester'])
    target_semester = current_semester + 1
    profile_ipk = profile_data.get('ipk')
    if profile_ipk is None:
        profile_ipk = student.ipk
    kuota_sks = get_sks_quota(profile_ipk, db)
    catalog_courses = (
        db.query(Course)
        .filter(Course.is_active.is_(True))
        .order_by(Course.code)
        .all()
    )
    catalog_by_code = {course.code: course for course in catalog_courses}
    catalog_codes = set(catalog_by_code)
    attempted: dict[str, list[StudentRecord]] = defaultdict(list)
    for record in records:
        course_code = _catalog_code_for_record(record.course_code, catalog_codes)
        attempted[course_code].append(record)
    passed_codes = {
        code for code, course_attempts in attempted.items()
        if any(_passed(record) for record in course_attempts)
    }
    passed_sks_by_code: dict[str, int] = {}
    for code, course_attempts in attempted.items():
        for record in course_attempts:
            if _passed(record):
                passed_sks_by_code[code] = max(
                    passed_sks_by_code.get(code, 0),
                    record.sks or 0,
                )
    passed_sks = sum(passed_sks_by_code.values())

    weights = settings.get_recommendation_weights()
    similarities, cohort_counts, peer_count = _peer_course_scores(
        db, student, target_semester, records
    )
    target_courses = [
        course for course in catalog_courses
        if target_semester in {
            int(item.strip())
            for item in (course.available_semesters or str(course.semester)).split(',')
            if item.strip().isdigit()
        }
    ]

    recommendations = []
    rejected = []
    grades_by_code = {}
    latest_attempts = {}
    for code, course_attempts in attempted.items():
        latest_attempts[code] = max(
            course_attempts,
            key=lambda record: (record.semester or 0, record.id or 0),
        )
        passing_attempts = [record for record in course_attempts if _passed(record)]
        if passing_attempts:
            latest_passing_attempt = max(
                passing_attempts,
                key=lambda record: (record.semester or 0, record.id or 0),
            )
            if latest_passing_attempt.grade_point is not None:
                grades_by_code[code] = latest_passing_attempt.grade_point

    semester_antara = [
        {
            'code': code,
            'name': catalog_by_code[code].name if code in catalog_by_code else latest.course_name or code,
            'sks': catalog_by_code[code].sks if code in catalog_by_code else latest.sks or 0,
            'grade': latest.grade,
            'last_attempt_semester': latest.semester,
            'mandatory': True,
        }
        for code, latest in latest_attempts.items()
        if not _passed(latest)
        and not any(_passed(record) for record in attempted[code])
    ]
    semester_antara.sort(key=lambda item: item['code'])

    for course in target_courses:
        prereqs = [item.strip() for item in (course.prerequisite_codes or '').split(',') if item.strip()]
        missing_prereqs = [code for code in prereqs if code not in passed_codes]
        course_attempts = attempted.get(course.code, [])
        already_passed = any(_passed(record) for record in course_attempts)
        reasons = []
        blocks = []
        if missing_prereqs:
            blocks.append(f"Prasyarat belum lulus: {', '.join(missing_prereqs)}")
        if already_passed:
            blocks.append('Mata kuliah sudah pernah dinyatakan lulus')
        elif course_attempts:
            blocks.append('Mata kuliah belum lulus; wajib diulang di Semester Antara setelah semester genap')
        if course.sks > kuota_sks:
            blocks.append(f'Melebihi kuota SKS ({course.sks} > {kuota_sks})')
        blocks.extend(
            _additional_prerequisite_blocks(
                course.prerequisite_text or '',
                student,
                records,
                passed_sks,
            )
        )
        if not course_attempts:
            reasons.append('Belum pernah diambil')
        if not missing_prereqs:
            reasons.append('Prasyarat terpenuhi')
        reasons.append(f'Sesuai kurikulum semester {target_semester}')

        course_identity = _course_identity(course.code, course.name)
        similar_score = similarities.get(course_identity, 0.0)
        peer_count_for_course, peer_total = cohort_counts.get(
            course_identity,
            (0, peer_count),
        )
        if peer_total:
            reasons.append(
                f'{peer_count_for_course} dari {peer_total} mahasiswa serupa mengambil mata kuliah ini'
            )
        else:
            reasons.append('Data mahasiswa serupa belum tersedia; skor kolaboratif dinetralkan')

        if _interest_matches(course.category, student.interests or ''):
            interest_score = 1.0
            reasons.append(f'Sesuai minat {course.category}')
        else:
            interest_score = 0.0

        relevant_points = [
            grades_by_code[code] for code in prereqs if code in grades_by_code and code in passed_codes
        ]
        academic_score = (
            sum(relevant_points) / (4 * len(relevant_points))
            if relevant_points
            else min(max((student.ipk or 0) / 4, 0), 1)
        )
        if relevant_points:
            reasons.append('Performa mata kuliah prasyarat dipertimbangkan')

        frequency_score = min(peer_count_for_course / peer_total, 1.0) if peer_total else 0.0
        factors = {
            'similar_students': similar_score,
            'academic_history': academic_score,
            'interest': interest_score,
            'curriculum': 1.0,
            'course_pattern': frequency_score,
        }
        score = round(100 * sum(weights[key] * factors[key] for key in weights), 1)
        item = {
            'code': course.code,
            'name': course.name,
            'sks': course.sks,
            'score': score,
            'valid': not blocks,
            'reasons': reasons,
            'reason_block': '; '.join(blocks) if blocks else None,
            'description': course.description,
            'category': course.category,
            'prerequisite_text': course.prerequisite_text,
            'semester': target_semester,
            'factors': {key: round(value * 100, 1) for key, value in factors.items()},
            'peer_count': peer_count_for_course,
            'peer_total': peer_total,
        }
        if blocks:
            rejected.append(item)
        else:
            recommendations.append(item)

    recommendations.sort(key=lambda item: item['score'], reverse=True)
    rejected.sort(key=lambda item: item['score'], reverse=True)
    latest_model = (
        db.query(RecommendationModelVersion)
        .order_by(RecommendationModelVersion.trained_at.desc())
        .first()
    )
    model_info = {
        'version': latest_model.version if latest_model else 'similarity-cold-start',
        'method': latest_model.method if latest_model else 'Content-based + similarity-based collaborative filtering',
        'dataset_size': latest_model.dataset_size if latest_model else len(records),
        'peer_count': peer_count,
        'weights': weights,
    }
    all_codes = set(attempted)
    passed_count = len(passed_codes)
    failed_count = sum(
        not any(_passed(record) for record in course_attempts)
        for course_attempts in attempted.values()
    )
    passed_sks = {}
    for code, course_attempts in attempted.items():
        for record in course_attempts:
            if _passed(record):
                passed_sks[code] = max(passed_sks.get(code, 0), record.sks or 0)
    profile = {
        'nim': student.nim,
        'full_name': profile_data.get('full_name') or student.full_name,
        'program_study': profile_data.get('program_study') or '',
        'current_semester': current_semester,
        'target_semester': target_semester,
        'ipk': profile_data.get('ipk') if profile_data.get('ipk') is not None else student.ipk,
        'kuota_sks': kuota_sks,
        'total_sks': sum(passed_sks.values()),
        'passed_courses': passed_count,
        'failed_courses': failed_count,
        'taken_course_codes': sorted(all_codes),
        'not_taken_course_codes': sorted(catalog_codes - all_codes),
        'interests': student.interests or '',
    }
    return {
        'status': 'ready',
        'message': None,
        'profile': profile,
        'target_semester': target_semester,
        'model': model_info,
        'recommendations': recommendations,
        'rejected': rejected,
        'semester_antara': semester_antara,
    }


def train_similarity_model(db: Session) -> RecommendationModelVersion:
    records = db.query(StudentRecord).filter(StudentRecord.semester.is_not(None)).all()
    students_with_history = {
        record.student_id for record in records
    }
    by_student_semester: dict[tuple[int, int], set[str]] = defaultdict(set)
    for record in records:
        if _passed(record):
            by_student_semester[(record.student_id, record.semester)].add(record.course_code)

    episodes = []
    for student_id in students_with_history:
        semesters = sorted(
            semester for owner, semester in by_student_semester if owner == student_id
        )
        for semester in semesters:
            history = set().union(*(
                by_student_semester[(student_id, previous)]
                for previous in semesters if previous < semester
            )) if any(previous < semester for previous in semesters) else set()
            target = by_student_semester[(student_id, semester)]
            if history and target:
                episodes.append((student_id, semester, history, target))

    precisions = []
    recalls = []
    for student_id, semester, history, target in episodes:
        votes: dict[str, float] = defaultdict(float)
        for peer_id, peer_semester, peer_history, peer_courses in episodes:
            if peer_id == student_id or peer_semester != semester:
                continue
            similarity = _similarity(
                [StudentRecord(course_code=code, grade='') for code in history],
                [StudentRecord(course_code=code, grade='') for code in peer_history],
            )
            if similarity:
                for code in peer_courses:
                    votes[code] += similarity
        ranked = [code for code, _ in sorted(votes.items(), key=lambda item: item[1], reverse=True)[:5]]
        if not ranked:
            continue
        hits = len(set(ranked) & target)
        precisions.append(hits / 5)
        recalls.append(hits / len(target))

    course_coverage = len({record.course_code for record in records})
    metrics = {
        'students_with_history': len(students_with_history),
        'semester_transitions': len(episodes),
        'course_coverage': course_coverage,
        'precision_at_5': round(sum(precisions) / len(precisions), 4) if precisions else None,
        'recall_at_5': round(sum(recalls) / len(recalls), 4) if recalls else None,
        'evaluation_samples': len(precisions),
        'evaluation_status': 'evaluated' if precisions else 'insufficient_history',
    }
    version_number = db.query(RecommendationModelVersion).count() + 1
    version = RecommendationModelVersion(
        version=f'similarity-{version_number:03d}',
        method='Weighted nearest-neighbor collaborative filtering + content-based fallback',
        dataset_size=len(records),
        metrics=json.dumps(metrics),
        trained_at=utc_now_naive(),
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version
