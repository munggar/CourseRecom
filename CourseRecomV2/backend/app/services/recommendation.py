import json
import math
import re
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AdvisorFeedback, Course, KhsDocument, RecommendationModelVersion, StudentRecord, StudyPlan, User
from app.services.time_utils import utc_now_naive
from app.services.khs_parser import GRADE_POINTS
from app.services.validation import get_sks_quota
from datetime import timezone



PASSING_GRADES = settings.get_passing_grades()

def is_mandatory_course(course: Course) -> bool:
    category = str(course.category or '')
    description = str(course.description or '')
    return bool(
        re.search(r'\bwajib\b', category, flags=re.IGNORECASE)
        or re.search(r'\bwajib(?:\s+semester\s+\d+)?\b', description, flags=re.IGNORECASE)
    )


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

INTEREST_TOPIC_MAP = {
    'manajemen sistem informasi': {
        'information_systems', 'application_development', 'database_management',
        'it_infrastructure', 'enterprise_systems', 'it_governance', 'business_process',
    },
    'kecerdasan bisnis': {
        'data_analytics', 'business_intelligence', 'artificial_intelligence',
        'statistical_analysis', 'decision_support', 'data_mining', 'database_management',
    },
}

COURSE_TOPIC_KEYWORDS = {
    'information_systems': (
        'sistem informasi', 'information system', 'information systems',
    ),
    'application_development': (
        'mobile application', 'mobile app', 'aplikasi mobile', 'web application',
        'pengembangan aplikasi', 'application development', 'software engineering',
        'rekayasa perangkat lunak', 'pemrograman', 'programming', 'algoritma', 'coding',
    ),
    'database_management': (
        'database', 'basis data', 'sql', 'data warehouse', 'sistem basis data',
        'database management',
    ),
    'it_infrastructure': (
        'infrastruktur teknologi informasi', 'infrastruktur ti', 'jaringan komputer',
        'jaringan', 'komunikasi data', 'telekomunikasi', 'computer network',
        'networking', 'cloud computing', 'arsitektur komputer',
        'computer architecture', 'server administration',
    ),
    'enterprise_systems': (
        'enterprise system', 'sistem enterprise', 'enterprise resource planning',
        'erp', 'perencanaan sumber daya perusahaan',
    ),
    'it_governance': (
        'tata kelola teknologi informasi', 'it governance', 'manajemen proyek ti',
        'manajemen proyek teknologi informasi', 'audit sistem informasi',
        'keamanan informasi', 'cybersecurity',
    ),
    'business_process': (
        'proses bisnis', 'business process', 'sistem informasi manajemen',
        'manajemen sistem informasi',
    ),
    'data_analytics': (
        'analisis data', 'data analytics', 'data analysis', 'data science',
        'analitika data', 'big data', 'visualisasi data', 'data visualization',
    ),
    'business_intelligence': (
        'business intelligence', 'kecerdasan bisnis', 'dashboard', 'power bi',
        'decision intelligence',
    ),
    'artificial_intelligence': (
        'artificial intelligence', 'kecerdasan buatan', 'machine learning',
        'deep learning', 'ai ml', 'neural network',
    ),
    'statistical_analysis': (
        'statistik', 'statistics', 'statistical analysis', 'probabilitas', 'probability',
    ),
    'decision_support': (
        'sistem pendukung keputusan', 'sistem penunjang keputusan',
        'decision support system', 'decision support', 'dss',
    ),
    'data_mining': (
        'data mining', 'text mining', 'sentiment analysis', 'analisis sentimen',
        'pattern recognition', 'pengenalan pola',
    ),
}


def _normalize_text(value: str) -> str:
    return re.sub(r'[\W_]+', ' ', str(value or '').casefold()).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = _normalize_text(text)
    normalized_phrase = _normalize_text(phrase)
    return bool(normalized_phrase and f' {normalized_phrase} ' in f' {normalized_text} ')


def _interest_groups(interests: str) -> set[str]:
    selected = set()
    for raw_interest in (interests or '').split(','):
        normalized = _normalize_text(raw_interest)
        if not normalized:
            continue
        for group, aliases in INTEREST_ALIASES.items():
            normalized_aliases = {_normalize_text(alias) for alias in aliases | {group}}
            if any(
                normalized == alias or f' {alias} ' in f' {normalized} '
                for alias in normalized_aliases if alias
            ):
                selected.add(group)
    return selected


def _interest_matches(category: str, interests: str) -> bool:
    """Legacy specialization matcher retained for callers and old tests."""
    return bool(_interest_groups(category) & _interest_groups(interests))


def _interest_topic_score(course: Course, interests: str) -> tuple[float | None, str]:
    selected_groups = _interest_groups(interests)
    if not selected_groups:
        return None, 'Peminatan mahasiswa belum dipilih atau belum dikenali.'

    category_groups = _interest_groups(course.category or '')
    if category_groups:
        if selected_groups.intersection(category_groups):
            return 1.0, 'Kategori katalog secara eksplisit sesuai dengan peminatan yang dipilih.'
        return 0.0, 'Kategori katalog mengarah ke peminatan yang berbeda dari pilihan mahasiswa.'

    selected_topics = set().union(
        *(INTEREST_TOPIC_MAP[group] for group in selected_groups)
    )
    course_text = ' '.join((
        course.name or '',
        course.category or '',
        course.description or '',
        course.prerequisite_text or '',
    ))
    course_topics = {
        topic for topic, phrases in COURSE_TOPIC_KEYWORDS.items()
        if any(_contains_phrase(course_text, phrase) for phrase in phrases)
    }
    if not course_topics:
        return None, 'Kata kunci mata kuliah belum cukup untuk menilai kecocokan peminatan.'

    matched_topics = course_topics & selected_topics
    score = len(matched_topics) / len(course_topics)
    if matched_topics:
        detail = (
            f'{len(matched_topics)} dari {len(course_topics)} topik mata kuliah '
            'sesuai dengan peminatan yang dipilih.'
        )
    else:
        detail = (
            f'Topik terdeteksi ({len(course_topics)}) belum beririsan dengan peminatan yang dipilih.'
        )
    return score, detail


def _similar_students_factor(
    similarities: dict[str, float],
    course_identity: str,
    peer_count: int,
) -> float | None:
    if peer_count <= 0:
        return None
    # A missing vote among an available peer cohort is a real 0%, not missing data.
    return similarities.get(course_identity, 0.0)


def _score_with_available_factors(
    factors: dict[str, float | None],
    weights: dict[str, float],
) -> tuple[float, float, dict[str, float]]:
    available = {
        key: value for key, value in factors.items()
        if value is not None and key in weights
    }
    available_weight = sum(weights[key] for key in available)
    if available_weight <= 0:
        return 0.0, 0.0, {key: 0.0 for key in weights}

    score = sum(weights[key] * float(value) for key, value in available.items())
    effective_weights = {
        key: round(weights[key] / available_weight * 100, 1) if key in available else 0.0
        for key in weights
    }
    return round(score / available_weight * 100, 1), round(available_weight * 100, 1), effective_weights



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
    normalized_name = _normalize_text(name or '')
    if normalized_name:
        return f'name:{normalized_name}'
    normalized_code = str(code or '').strip().upper()
    return f'code:{normalized_code}'


def _record_identity(
    record: StudentRecord,
    catalog_codes: set[str] | None = None,
    catalog_name_to_code: dict[str, str] | None = None,
) -> str:
    code = str(record.course_code or '').strip().upper()
    if catalog_codes is not None:
        normalized_code = _catalog_code_for_record(code, catalog_codes)
        if normalized_code in catalog_codes:
            return _course_identity(normalized_code)
        normalized_name = _normalize_text(record.course_name or '')
        if catalog_name_to_code and normalized_name in catalog_name_to_code:
            return _course_identity(catalog_name_to_code[normalized_name])
        if normalized_name:
            return _course_identity('', record.course_name)
        return _course_identity(code)
    return _course_identity(code, record.course_name)


def _record_grade_value(record: StudentRecord) -> float:
    if record.grade_point is not None:
        return float(record.grade_point)
    return float(GRADE_POINTS.get(str(record.grade or '').upper(), 0.0))


def _latest_course_grades(
    records: list[StudentRecord],
    catalog_codes: set[str] | None = None,
    catalog_name_to_code: dict[str, str] | None = None,
) -> dict[str, str]:
    latest: dict[str, StudentRecord] = {}
    for record in records:
        identity = _record_identity(record, catalog_codes, catalog_name_to_code)
        previous = latest.get(identity)
        if previous is None or (
            int(record.semester or 0), int(record.id or 0)
        ) > (
            int(previous.semester or 0), int(previous.id or 0)
        ):
            latest[identity] = record
    return {
        identity: str(record.grade or '').upper()
        for identity, record in latest.items()
        if record.grade
    }


def _similarity(
    student_records: list[StudentRecord],
    peer_records: list[StudentRecord],
    catalog_codes: set[str] | None = None,
    catalog_name_to_code: dict[str, str] | None = None,
) -> float:
    student_grades = _latest_course_grades(
        student_records, catalog_codes, catalog_name_to_code
    )
    peer_grades = _latest_course_grades(
        peer_records, catalog_codes, catalog_name_to_code
    )
    student_codes = set(student_grades)
    peer_codes = set(peer_grades)
    if not student_codes or not peer_codes:
        return 0.0

    union = student_codes | peer_codes
    jaccard = len(student_codes & peer_codes) / len(union)
    common = student_codes & peer_codes
    grade_similarity = (
        sum(student_grades[code] == peer_grades[code] for code in common) / len(common)
        if common else 0.0
    )
    return 0.8 * jaccard + 0.2 * grade_similarity


def _peer_course_scores(
    db: Session,
    student: User,
    target_semester: int,
    student_records: list[StudentRecord],
    catalog_courses: list[Course] | None = None,
) -> tuple[dict[str, float], dict[str, tuple[int, int]], int]:
    catalog_courses = catalog_courses or []
    catalog_codes = {course.code.strip().upper() for course in catalog_courses}
    name_to_codes: dict[str, set[str]] = defaultdict(set)
    for course in catalog_courses:
        normalized_name = _normalize_text(course.name)
        if normalized_name:
            name_to_codes[normalized_name].add(course.code.strip().upper())
    catalog_name_to_code = {
        name: next(iter(codes))
        for name, codes in name_to_codes.items()
        if len(codes) == 1
    }

    all_records = db.query(StudentRecord).filter(StudentRecord.semester.is_not(None)).all()
    peer_by_student: dict[int, list[StudentRecord]] = defaultdict(list)
    for record in all_records:
        if record.student_id != student.id:
            peer_by_student[record.student_id].append(record)

    student_history = [
        record for record in student_records
        if record.semester is None or record.semester < target_semester
    ]
    peers: list[tuple[float, list[StudentRecord]]] = []
    for peer_records in peer_by_student.values():
        history = [record for record in peer_records if record.semester < target_semester]
        next_semester = [record for record in peer_records if record.semester == target_semester]
        if not history or not next_semester:
            continue
        similarity = _similarity(
            student_history, history, catalog_codes, catalog_name_to_code
        )
        if similarity > 0:
            peers.append((similarity, next_semester))

    peers.sort(key=lambda item: item[0], reverse=True)
    peers = peers[:20]
    total_similarity = sum(peer[0] for peer in peers)
    weighted_scores: dict[str, float] = defaultdict(float)
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for similarity, next_semester_records in peers:
        unique_courses = {
            _record_identity(record, catalog_codes, catalog_name_to_code)
            for record in next_semester_records
        }
        for identity in unique_courses:
            weighted_scores[identity] += similarity
            counts[identity][0] += 1

    peer_total = len(peers)
    for count in counts.values():
        count[1] = peer_total

    normalized = {
        identity: score / total_similarity
        for identity, score in weighted_scores.items()
    } if total_similarity else {}
    return normalized, {
        identity: (count[0], count[1]) for identity, count in counts.items()
    }, peer_total


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


def _course_recommendation_explanation(peer_course_count: int, peer_total: int) -> str:
    if peer_total > 0:
        if peer_course_count > 0:
            return (
                f"Model membandingkan riwayat KHS dengan {peer_total} mahasiswa serupa; "
                f"{peer_course_count} di antaranya mengambil mata kuliah ini. "
                "Skor juga menggabungkan sinyal akademik, minat yang tersedia, prasyarat, dan kurikulum."
            )
        return (
            f"Model membandingkan riwayat KHS dengan {peer_total} mahasiswa serupa, "
            "tetapi belum ada yang tercatat mengambil mata kuliah ini. "
            "Skor tetap mempertimbangkan riwayat akademik, minat yang tersedia, prasyarat, dan kurikulum."
        )
    return (
        "Belum ada kelompok mahasiswa pembanding yang memadai. Untuk mata kuliah ini, "
        "sistem menggunakan content-based scoring dari riwayat akademik, minat yang tersedia, "
        "prasyarat, dan kesesuaian kurikulum."
    )


def _build_model_runtime_info(
    latest_model: RecommendationModelVersion | None,
    peer_count: int,
    weights: dict[str, float],
    available_history_records: int,
    available_history_students: int,
) -> dict:
    metrics = {}
    if latest_model and latest_model.metrics:
        try:
            metrics = json.loads(latest_model.metrics)
        except (TypeError, ValueError, json.JSONDecodeError):
            metrics = {}

    evaluation_status = (
        metrics.get('evaluation_status', 'not_evaluated')
        if latest_model else 'not_trained'
    )
    inference_mode = 'collaborative_plus_content' if peer_count else 'content_based_fallback'
    return {
        'name': 'CourseRecom Hybrid Course Recommender',
        'version': latest_model.version if latest_model else None,
        'method': (
            latest_model.method if latest_model
            else 'Weighted nearest-neighbor collaborative filtering + content-based fallback'
        ),
        'inference_mode': inference_mode,
        'inference_mode_label': (
            'Collaborative filtering + content-based'
            if peer_count else 'Content-based fallback (data pembanding belum cukup)'
        ),
        'training_status': evaluation_status,
        'training_dataset_size': latest_model.dataset_size if latest_model else None,
        'dataset_size': latest_model.dataset_size if latest_model else available_history_records,
        'available_history_records': available_history_records,
        'available_history_students': available_history_students,
        'trained_at': (
            latest_model.trained_at.replace(tzinfo=timezone.utc).isoformat()
            if latest_model and latest_model.trained_at else None
        ),
        'metrics': metrics or None,
        'peer_count': peer_count,
        'weights': weights,
        'scoring_method': 'Evidence-normalized weighted score; unavailable factors are excluded and remaining weights are renormalized.',
    }



def _active_advisor_feedback(
    db: Session,
    student_id: int,
    target_semester: int,
) -> tuple[list[AdvisorFeedback], dict[str, list[AdvisorFeedback]]]:
    latest_plan = (
        db.query(StudyPlan)
        .filter(
            StudyPlan.student_id == student_id,
            StudyPlan.semester == target_semester,
        )
        .order_by(StudyPlan.updated_at.desc(), StudyPlan.id.desc())
        .first()
    )
    if latest_plan and latest_plan.status == 'approved':
        return [], {}

    feedback_rows = (
        db.query(AdvisorFeedback)
        .filter(
            AdvisorFeedback.student_id == student_id,
            AdvisorFeedback.semester == target_semester,
            AdvisorFeedback.feedback_type == 'revision_requested',
        )
        .order_by(AdvisorFeedback.created_at.asc(), AdvisorFeedback.id.asc())
        .all()
    )
    by_course: dict[str, list[AdvisorFeedback]] = defaultdict(list)
    for feedback in feedback_rows:
        try:
            codes = json.loads(feedback.affected_course_codes_json or '[]')
        except (TypeError, ValueError, json.JSONDecodeError):
            codes = []
        for code in codes:
            normalized = str(code).strip().upper()
            if normalized:
                by_course[normalized].append(feedback)
    return feedback_rows, dict(by_course)


def _serialize_advisor_feedback(feedback: AdvisorFeedback) -> dict:
    try:
        codes = json.loads(feedback.affected_course_codes_json or '[]')
    except (TypeError, ValueError, json.JSONDecodeError):
        codes = []
    return {
        'id': feedback.id,
        'semester': feedback.semester,
        'affected_course_codes': codes,
        'reason_category': feedback.reason_category,
        'note': feedback.note,
        'feedback_type': feedback.feedback_type,
        'created_at': feedback.created_at.isoformat(),
    }


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
            'mandatory_courses': [],
            'rejected': [],
            'semester_antara': [],
            'advisor_feedback': [],
        }

    document_data = json.loads(latest_document.parsed_data)
    profile_data = document_data['metadata']
    records = db.query(StudentRecord).filter(StudentRecord.student_id == student.id).all()
    current_semester = int(profile_data['current_semester'])
    target_semester = current_semester + 1
    advisor_feedback_rows, advisor_feedback_by_course = _active_advisor_feedback(
        db, student.id, target_semester
    )
    advisor_feedback_payload = [
        _serialize_advisor_feedback(item) for item in advisor_feedback_rows
    ]
    profile_ipk = profile_data.get('ipk')
    if profile_ipk is None:
        profile_ipk = student.ipk
    try:
        profile_ipk = float(profile_ipk) if profile_ipk is not None else None
    except (TypeError, ValueError):
        profile_ipk = None
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
        db, student, target_semester, records, catalog_courses
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
    mandatory_courses = []
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
            grades_by_code[code] = _record_grade_value(latest_passing_attempt)

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
        course_feedback = advisor_feedback_by_course.get(course.code, [])
        if course_feedback:
            latest_feedback = course_feedback[-1]
            blocks.append(
                f'Ditandai dosen PA untuk revisi: {latest_feedback.note}'
            )
            reasons.append('Sinyal feedback negatif personal dari dosen PA dipakai untuk mencari alternatif')
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

        course_identity = _course_identity(course.code)
        similar_score = _similar_students_factor(similarities, course_identity, peer_count)
        peer_count_for_course, peer_total = cohort_counts.get(
            course_identity,
            (0, peer_count),
        )
        if peer_total:
            reasons.append(
                f'{peer_count_for_course} dari {peer_total} mahasiswa serupa mengambil mata kuliah ini'
            )
        else:
            reasons.append('Belum cukup data mahasiswa serupa untuk menghitung aspek kolaboratif')

        interest_score, interest_detail = _interest_topic_score(
            course, student.interests or ''
        )
        if interest_score is not None and interest_score > 0:
            reasons.append(interest_detail)

        relevant_points = [
            grades_by_code[code] for code in prereqs
            if code in grades_by_code and code in passed_codes
        ]
        if relevant_points:
            academic_score = sum(relevant_points) / (4 * len(relevant_points))
            academic_detail = (
                f'Rata-rata nilai {len(relevant_points)} mata kuliah prasyarat '
                f'{sum(relevant_points) / len(relevant_points):.2f} dari 4.00.'
            )
            reasons.append('Nilai mata kuliah prasyarat yang sudah lulus dipertimbangkan')
        elif profile_ipk is not None:
            academic_score = min(max(profile_ipk / 4, 0), 1)
            academic_detail = f'IPK pada KHS terbaru {profile_ipk:.2f} dari 4.00.'
        else:
            academic_score = None
            academic_detail = 'IPK KHS terbaru belum tersedia untuk menghitung aspek akademik.'

        frequency_score = (
            peer_count_for_course / peer_total if peer_total else None
        )
        if peer_total:
            course_pattern_detail = (
                f'{peer_count_for_course} dari {peer_total} mahasiswa serupa mengambil mata kuliah ini.'
            )
        else:
            course_pattern_detail = 'Belum ada kelompok mahasiswa pembanding yang cukup.'

        factor_values = {
            'similar_students': similar_score,
            'academic_history': academic_score,
            'interest': interest_score,
            'curriculum': 1.0,
            'course_pattern': frequency_score,
        }
        score, score_coverage, effective_weights = _score_with_available_factors(
            factor_values, weights
        )
        factors = {
            key: round(value * 100, 1) if value is not None else None
            for key, value in factor_values.items()
        }
        factor_details = {
            'similar_students': (
                f'Kemiripan riwayat akademik dipakai untuk memberi bobot suara; '
                f'{peer_total} mahasiswa pembanding tersedia.'
                if peer_total else
                'Belum cukup riwayat mahasiswa lain untuk membentuk kelompok pembanding.'
            ),
            'academic_history': academic_detail,
            'interest': interest_detail,
            'curriculum': f'Mata kuliah tersedia pada semester target {target_semester}.',
            'course_pattern': course_pattern_detail,
        }
        item = {
            'code': course.code,
            'name': course.name,
            'sks': course.sks,
            'mandatory': is_mandatory_course(course),
            'score': score,
            'valid': not blocks,
            'reasons': reasons,
            'reason_block': '; '.join(blocks) if blocks else None,
            'description': course.description,
            'category': course.category,
            'prerequisite_text': course.prerequisite_text,
            'semester': target_semester,
            'factors': factors,
            'factor_details': factor_details,
            'factor_weights': effective_weights,
            'score_coverage': score_coverage,
            'available_factor_count': sum(value is not None for value in factor_values.values()),
            'peer_count': peer_count_for_course,
            'peer_total': peer_total,
            'recommendation_mode': (
                'collaborative_plus_content' if peer_total
                else 'content_based_fallback'
            ),
            'recommendation_explanation': _course_recommendation_explanation(
                peer_count_for_course, peer_total
            ),
            'rejection_source': 'advisor_feedback' if course_feedback else None,
            'advisor_feedback': (
                {
                    'note': course_feedback[-1].note,
                    'reason_category': course_feedback[-1].reason_category,
                    'created_at': course_feedback[-1].created_at.isoformat(),
                }
                if course_feedback else None
            ),
        }
        if blocks:
            rejected.append(item)
        elif item['mandatory']:
            mandatory_courses.append(item)
        else:
            recommendations.append(item)

    recommendations.sort(key=lambda item: item['score'], reverse=True)
    mandatory_courses.sort(key=lambda item: item['code'])
    rejected.sort(key=lambda item: item['score'], reverse=True)
    latest_model = (
        db.query(RecommendationModelVersion)
        .order_by(RecommendationModelVersion.trained_at.desc())
        .first()
    )
    available_history_records = (
        db.query(StudentRecord)
        .filter(StudentRecord.semester.is_not(None))
        .count()
    )
    available_history_students = (
        db.query(StudentRecord.student_id)
        .filter(StudentRecord.semester.is_not(None))
        .distinct()
        .count()
    )
    model_info = _build_model_runtime_info(
        latest_model,
        peer_count,
        weights,
        available_history_records,
        available_history_students,
    )
    all_feedback_rows = db.query(AdvisorFeedback).filter(
        AdvisorFeedback.feedback_type == 'revision_requested'
    ).all()
    model_info['advisor_feedback_events'] = len(all_feedback_rows)
    model_info['advisor_negative_course_labels'] = sum(
        len(json.loads(item.affected_course_codes_json or '[]'))
        for item in all_feedback_rows
    )
    model_info['active_advisor_feedback_events'] = len(advisor_feedback_rows)
    model_info['feedback_learning_method'] = (
        'Student- and semester-specific weak negative labels from advisor-selected course codes; '
        'free-text notes are retained for explanation and audit.'
    )
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
        'mandatory_courses': mandatory_courses,
        'rejected': rejected,
        'semester_antara': semester_antara,
        'advisor_feedback': advisor_feedback_payload,
    }


def train_similarity_model(db: Session) -> RecommendationModelVersion:
    records = db.query(StudentRecord).filter(StudentRecord.semester.is_not(None)).all()
    feedback_rows = db.query(AdvisorFeedback).filter(
        AdvisorFeedback.feedback_type == 'revision_requested'
    ).all()
    negative_labels: dict[tuple[int, int], set[str]] = defaultdict(set)
    feedback_reason_counts: Counter[str] = Counter()
    feedback_note_terms: Counter[str] = Counter()
    feedback_label_count = 0
    for feedback in feedback_rows:
        try:
            codes = json.loads(feedback.affected_course_codes_json or '[]')
        except (TypeError, ValueError, json.JSONDecodeError):
            codes = []
        normalized_codes = {str(code).strip().upper() for code in codes if str(code).strip()}
        negative_labels[(feedback.student_id, feedback.semester)].update(normalized_codes)
        feedback_label_count += len(normalized_codes)
        feedback_reason_counts[feedback.reason_category or 'general'] += 1
        feedback_note_terms.update(
            token for token in re.findall(r'[a-z0-9]{3,}', (feedback.note or '').casefold())
            if token not in {'yang', 'untuk', 'dengan', 'pada', 'karena', 'agar', 'atau'}
        )
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
        excluded_by_advisor = negative_labels.get((student_id, semester), set())
        ranked = [
            code for code, _ in sorted(votes.items(), key=lambda item: item[1], reverse=True)
            if code not in excluded_by_advisor
        ][:5]
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
        'advisor_feedback_events': len(feedback_rows),
        'advisor_negative_course_labels': feedback_label_count,
        'feedback_adjusted_samples': sum(
            1 for student_id, semester, _history, _target in episodes
            if negative_labels.get((student_id, semester))
        ),
        'feedback_reason_categories': dict(feedback_reason_counts),
        'feedback_note_terms': dict(feedback_note_terms.most_common(20)),
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
