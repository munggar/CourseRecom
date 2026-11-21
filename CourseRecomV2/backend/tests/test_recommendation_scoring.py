from types import SimpleNamespace
from uuid import uuid4

from app.database import SessionLocal
from app.models import AdvisorCourseFeedback, StudentRecord, User
from app.services.recommendation import (
    _build_model_runtime_info,
    _course_recommendation_explanation,
    _interest_topic_score,
    _interest_groups,
    _peer_course_scores,
    _score_with_available_factors,
    _similar_students_factor,
    _similarity,
)


BASE_WEIGHTS = {
    'similar_students': 0.30,
    'academic_history': 0.25,
    'interest': 0.20,
    'curriculum': 0.15,
    'course_pattern': 0.10,
}


def _record(student_id, code, name, grade, semester, record_id):
    return SimpleNamespace(
        student_id=student_id,
        course_code=code,
        course_name=name,
        grade=grade,
        grade_point=None,
        semester=semester,
        id=record_id,
    )


def test_interest_uses_course_name_category_description_and_selected_specialization():
    course = SimpleNamespace(
        name='Mobile Application',
        category='Inti Teknologi & Pemrograman',
        description='Wajib Semester 5',
        prerequisite_text='Pemrograman Web',
    )

    msi_score, msi_detail = _interest_topic_score(course, 'Manajemen Sistem Informasi')
    business_score, business_detail = _interest_topic_score(course, 'Kecerdasan Bisnis')

    assert msi_score == 1.0
    assert 'topik mata kuliah' in msi_detail
    assert business_score == 0.0
    assert 'belum beririsan' in business_detail


def test_interest_is_unavailable_when_profile_or_course_has_no_classifiable_topics():
    course = SimpleNamespace(
        name='Kemuhammadiyahan',
        category='Mata Kuliah Umum',
        description='Pendidikan karakter dan nilai keislaman',
        prerequisite_text='',
    )

    assert _interest_topic_score(course, '')[0] is None
    assert _interest_topic_score(course, 'Manajemen Sistem Informasi')[0] is None


def test_similarity_uses_canonical_course_code_even_when_imported_names_differ():
    student_records = [
        _record(1, '03045018', 'Algoritma', 'A', 1, 1),
    ]
    peer_records = [
        _record(2, '03045018', 'Algoritma dan Dasar Pemrograman', 'A', 1, 2),
    ]

    similarity = _similarity(student_records, peer_records, {'03045018'})

    assert similarity == 1.0


def test_similarity_uses_latest_attempt_instead_of_best_historical_grade():
    student_records = [
        _record(1, '03045018', 'Algoritma', 'A', 1, 1),
        _record(1, '03045018', 'Algoritma', 'C', 2, 2),
    ]
    peer_records = [
        _record(2, '03045018', 'Algoritma', 'C', 1, 3),
    ]

    assert _similarity(student_records, peer_records, {'03045018'}) == 1.0


def test_peer_course_scores_match_catalog_codes_and_count_only_similar_peers():
    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *_args, **_kwargs):
            return self

        def join(self, *_args, **_kwargs):
            return self

        def options(self, *_args, **_kwargs):
            return self

        def all(self):
            return self.rows

    class FakeDB:
        def __init__(self, rows, feedback_rows=None):
            self.rows = rows
            self.feedback_rows = feedback_rows or []

        def query(self, model):
            if model is AdvisorCourseFeedback:
                return FakeQuery(self.feedback_rows)
            return FakeQuery(self.rows)

    student = SimpleNamespace(id=1)
    student_history = [
        _record(1, 'A101', 'Algoritma', 'A', 1, 1),
        _record(1, 'A102', 'Basis Data', 'B', 1, 2),
    ]
    peer_rows = [
        _record(2, 'A101', 'Algoritma dan Dasar Pemrograman', 'A', 1, 3),
        _record(2, 'A102', 'Pengantar Basis Data', 'B', 1, 4),
        _record(2, 'X501', 'Mobile Application', 'A', 2, 5),
        _record(3, 'A101', 'Algoritma', 'A', 1, 6),
        _record(3, 'A102', 'Basis Data', 'B', 1, 7),
        _record(3, 'X502', 'Praktikum Mobile Application', 'B', 2, 8),
    ]
    catalog = [
        SimpleNamespace(code='A101', name='Algoritma'),
        SimpleNamespace(code='A102', name='Basis Data'),
        SimpleNamespace(code='X501', name='Mobile Application'),
        SimpleNamespace(code='X502', name='Praktikum Mobile Application'),
    ]

    similarities, counts, peer_count = _peer_course_scores(
        FakeDB(peer_rows), student, 2, student_history, catalog
    )

    assert peer_count == 2
    assert similarities['code:X501'] == 0.5
    assert similarities['code:X502'] == 0.5
    assert counts['code:X501'] == (1, 2)
    assert counts['code:X502'] == (1, 2)




def test_peer_course_scores_scope_to_active_students_in_the_same_program():
    suffix = uuid4().hex[:10]
    db = SessionLocal()
    users = [
        User(
            nim=f'PEER-STU-{suffix}',
            username=f'peer-stu-{suffix}',
            full_name='Peer Test Student',
            role='mahasiswa',
            program_study='Sistem dan Teknologi Informasi',
            password_hash='not-used',
            is_active=True,
        ),
        User(
            nim=f'PEER-SAME-{suffix}',
            username=f'peer-same-{suffix}',
            full_name='Peer Same Program',
            role='mahasiswa',
            program_study='Sistem dan Teknologi Informasi',
            password_hash='not-used',
            is_active=True,
        ),
        User(
            nim=f'PEER-OTHER-{suffix}',
            username=f'peer-other-{suffix}',
            full_name='Peer Other Program',
            role='mahasiswa',
            program_study='Teknik Informatika',
            password_hash='not-used',
            is_active=True,
        ),
        User(
            nim=f'PEER-INACTIVE-{suffix}',
            username=f'peer-inactive-{suffix}',
            full_name='Peer Inactive',
            role='mahasiswa',
            program_study='Sistem dan Teknologi Informasi',
            password_hash='not-used',
            is_active=False,
        ),
    ]
    try:
        db.add_all(users)
        db.flush()
        student, same_program, other_program, inactive = users
        records = [
            StudentRecord(student_id=student.id, course_code='C101', course_name='Algoritma', grade='A', semester=1),
            StudentRecord(student_id=same_program.id, course_code='C101', course_name='Algoritma', grade='A', semester=1),
            StudentRecord(student_id=same_program.id, course_code='X501', course_name='Mobile Application', grade='A', semester=2),
            StudentRecord(student_id=other_program.id, course_code='C101', course_name='Algoritma', grade='A', semester=1),
            StudentRecord(student_id=other_program.id, course_code='X502', course_name='Praktikum Mobile Application', grade='A', semester=2),
            StudentRecord(student_id=inactive.id, course_code='C101', course_name='Algoritma', grade='A', semester=1),
            StudentRecord(student_id=inactive.id, course_code='X503', course_name='Kursus Inactive', grade='A', semester=2),
        ]
        db.add_all(records)
        db.commit()
        db.refresh(student)
        student_history = db.query(StudentRecord).filter(
            StudentRecord.student_id == student.id,
            StudentRecord.semester < 2,
        ).all()
        catalog = [
            SimpleNamespace(code='C101', name='Algoritma'),
            SimpleNamespace(code='X501', name='Mobile Application'),
            SimpleNamespace(code='X502', name='Praktikum Mobile Application'),
            SimpleNamespace(code='X503', name='Kursus Inactive'),
        ]

        similarities, counts, peer_count = _peer_course_scores(
            db, student, 2, student_history, catalog
        )

        assert peer_count == 1
        assert similarities['code:X501'] == 1.0
        assert counts['code:X501'] == (1, 1)
        assert 'code:X502' not in similarities
        assert 'code:X503' not in similarities
    finally:
        if users and all(user.id is not None for user in users):
            user_ids = [user.id for user in users]
            db.query(StudentRecord).filter(StudentRecord.student_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
            db.commit()
        db.close()

def test_weighted_score_renormalizes_only_factors_with_real_evidence():
    score, coverage, effective_weights = _score_with_available_factors(
        {
            'similar_students': None,
            'academic_history': 0.8,
            'interest': None,
            'curriculum': 1.0,
            'course_pattern': None,
        },
        BASE_WEIGHTS,
    )

    assert score == 87.5
    assert coverage == 40.0
    assert effective_weights['academic_history'] == 62.5
    assert effective_weights['curriculum'] == 37.5
    assert effective_weights['similar_students'] == 0.0


def test_zero_is_a_real_score_and_is_not_treated_as_missing():
    score, coverage, effective_weights = _score_with_available_factors(
        {
            'similar_students': 0.0,
            'academic_history': None,
            'interest': None,
            'curriculum': 1.0,
            'course_pattern': None,
        },
        BASE_WEIGHTS,
    )

    assert score == 33.3
    assert coverage == 45.0
    assert effective_weights['similar_students'] == 66.7
    assert effective_weights['curriculum'] == 33.3



def test_similar_students_zero_vote_is_distinct_from_missing_peer_data():
    assert _similar_students_factor({}, 'code:MK001', peer_count=5) == 0.0
    assert _similar_students_factor({}, 'code:MK001', peer_count=0) is None



def test_interest_respects_explicit_course_catalog_specialization_tags():
    data_course = SimpleNamespace(
        name='Analisis Data dan Dashboard',
        category='Data Analytics',
        description='',
        prerequisite_text='',
    )
    msi_course = SimpleNamespace(
        name='Sistem Informasi Manajemen',
        category='Manajemen & Sistem Informasi',
        description='',
        prerequisite_text='',
    )

    assert _interest_topic_score(data_course, 'Kecerdasan Bisnis')[0] == 1.0
    assert _interest_topic_score(data_course, 'Manajemen Sistem Informasi')[0] == 0.0
    assert _interest_topic_score(msi_course, 'Manajemen Sistem Informasi')[0] == 1.0
    assert _interest_topic_score(msi_course, 'Kecerdasan Bisnis')[0] == 0.0



def test_runtime_model_metadata_reports_live_content_fallback_without_claiming_training():
    info = _build_model_runtime_info(
        latest_model=None,
        peer_count=0,
        weights=BASE_WEIGHTS,
        available_history_records=12,
        available_history_students=3,
    )

    assert info['name'] == 'CourseRecom Hybrid Course Recommender'
    assert info['version'] is None
    assert info['training_status'] == 'not_trained'
    assert info['inference_mode'] == 'content_based_fallback'
    assert info['available_history_records'] == 12
    assert info['available_history_students'] == 3
    assert info['metrics'] is None
    assert 'content-based fallback' in info['method'].lower()


def test_runtime_model_metadata_exposes_only_real_saved_evaluation_metrics():
    from datetime import datetime
    import json

    saved_model = SimpleNamespace(
        version='similarity-007',
        method='Weighted nearest-neighbor collaborative filtering + content-based fallback',
        dataset_size=36,
        metrics=json.dumps({
            'evaluation_status': 'evaluated',
            'evaluation_samples': 8,
            'precision_at_5': 0.625,
            'recall_at_5': 0.75,
        }),
        trained_at=datetime(2026, 11, 18, 9, 0, 0),
    )

    info = _build_model_runtime_info(
        latest_model=saved_model,
        peer_count=4,
        weights=BASE_WEIGHTS,
        available_history_records=40,
        available_history_students=5,
    )

    assert info['version'] == 'similarity-007'
    assert info['training_status'] == 'evaluated'
    assert info['inference_mode'] == 'collaborative_plus_content'
    assert info['training_dataset_size'] == 36
    assert info['metrics']['precision_at_5'] == 0.625
    assert info['metrics']['recall_at_5'] == 0.75
    assert info['trained_at'].startswith('2026-11-18T09:00:00')


def test_per_course_explanation_distinguishes_collaborative_and_content_fallback_modes():
    collaborative = _course_recommendation_explanation(peer_course_count=2, peer_total=5)
    content_fallback = _course_recommendation_explanation(peer_course_count=0, peer_total=0)

    assert '5 mahasiswa serupa' in collaborative
    assert '2 di antaranya' in collaborative
    assert 'content-based scoring' in content_fallback
    assert 'belum ada kelompok mahasiswa pembanding' in content_fallback.lower()


def test_ftii_program_interest_labels_map_to_distinct_ml_topic_groups():
    assert _interest_groups('Data Scientist') == {'data scientist'}
    assert 'kecerdasan bisnis' not in _interest_groups('Data Scientist')
    assert _interest_groups('Data Science') == {'data scientist'}
    assert _interest_groups('Manufaktur') == {'manufaktur'}
    assert _interest_groups('Energi dan Konversi Energi') == {'energi dan konversi energi'}
    assert _interest_groups('Pengembangan Robotika') == {'pengembangan robotika'}
    assert _interest_groups('Teknik Telekomunikasi') == {'teknik telekomunikasi'}
    assert _interest_groups('Pengembangan Robotika') == {'pengembangan robotika'}

    software_course = SimpleNamespace(
        name='Rekayasa Perangkat Lunak',
        category='Pilihan',
        description='Software engineering dan pengembangan aplikasi',
        prerequisite_text='',
    )
    score, _ = _interest_topic_score(software_course, 'Software Engineering')
    assert score is not None and score > 0

    manufacturing_course = SimpleNamespace(
        name='Proses Manufaktur',
        category='Pilihan',
        description='Sistem produksi dan mesin produksi',
        prerequisite_text='',
    )
    score, _ = _interest_topic_score(manufacturing_course, 'Manufaktur')
    assert score is not None and score > 0


def test_peer_course_scores_downweight_courses_rejected_by_similar_peers():
    student = SimpleNamespace(id=1)
    student_history = [
        _record(1, 'A101', 'Algoritma', 'A', 1, 1),
        _record(1, 'A102', 'Basis Data', 'B', 1, 2),
    ]
    peer_rows = [
        _record(2, 'A101', 'Algoritma', 'A', 1, 3),
        _record(2, 'A102', 'Basis Data', 'B', 1, 4),
        _record(2, 'X501', 'Mobile Application', 'A', 2, 5),
        _record(3, 'A101', 'Algoritma', 'A', 1, 6),
        _record(3, 'A102', 'Basis Data', 'B', 1, 7),
        _record(3, 'X502', 'Praktikum Mobile Application', 'B', 2, 8),
    ]
    catalog = [
        SimpleNamespace(code='A101', name='Algoritma'),
        SimpleNamespace(code='A102', name='Basis Data'),
        SimpleNamespace(code='X501', name='Mobile Application'),
        SimpleNamespace(code='X502', name='Praktikum Mobile Application'),
    ]
    feedback = [SimpleNamespace(student_id=2, semester=2, course_code='X501')]

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *_args, **_kwargs):
            return self

        def join(self, *_args, **_kwargs):
            return self

        def options(self, *_args, **_kwargs):
            return self

        def all(self):
            return self.rows

    class FakeDB:
        def query(self, model):
            return FakeQuery(feedback if model is AdvisorCourseFeedback else peer_rows)

    similarities, counts, peer_count = _peer_course_scores(
        FakeDB(), student, 2, student_history, catalog
    )

    assert peer_count == 2
    assert similarities['code:X501'] == 0.125
    assert similarities['code:X502'] == 0.5
    assert counts['code:X501'] == (1, 2)
    assert counts['code:X502'] == (1, 2)


def test_collaborative_votes_use_only_successfully_completed_peer_courses():
    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows
        def filter(self, *_args, **_kwargs):
            return self
        def all(self):
            return self.rows

    student = SimpleNamespace(id=1)
    student_history = [
        _record(1, 'A101', 'Algoritma', 'A', 1, 1),
        _record(1, 'A102', 'Basis Data', 'B', 1, 2),
    ]
    peer_rows = [
        _record(2, 'A101', 'Algoritma', 'A', 1, 3),
        _record(2, 'A102', 'Basis Data', 'B', 1, 4),
        _record(2, 'X501', 'Mobile Application', 'A', 2, 5),
        _record(3, 'A101', 'Algoritma', 'A', 1, 6),
        _record(3, 'A102', 'Basis Data', 'B', 1, 7),
        _record(3, 'X502', 'Praktikum Mobile Application', 'E', 2, 8),
    ]
    catalog = [
        SimpleNamespace(code='A101', name='Algoritma'),
        SimpleNamespace(code='A102', name='Basis Data'),
        SimpleNamespace(code='X501', name='Mobile Application'),
        SimpleNamespace(code='X502', name='Praktikum Mobile Application'),
    ]

    class FakeDB:
        def query(self, model):
            return FakeQuery([] if model is AdvisorCourseFeedback else peer_rows)

    similarities, counts, peer_count = _peer_course_scores(
        FakeDB(), student, 2, student_history, catalog,
    )
    assert peer_count == 1
    assert similarities == {'code:X501': 1.0}
    assert 'code:X502' not in similarities
    assert 'code:X502' not in counts
