import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import pytest

from app.database import Base
from app.models import Course, CourseClass, KprsRequest, StudyPlan, User
from app.services.academic import earned_credits, latest_attempt_gpa
from app.services.capacity import (
    assert_course_capacity,
    class_occupancy,
    begin_capacity_transaction,
    lock_capacity_courses,
)


def test_latest_attempt_gpa_includes_failed_latest_grade():
    assert latest_attempt_gpa([
        {'code': 'IF101', 'semester': 1, 'grade_point': 4.0, 'sks': 3},
        {'code': 'IF101', 'semester': 2, 'grade_point': 0.0, 'sks': 3},
        {'code': 'IF102', 'semester': 1, 'grade_point': 3.0, 'sks': 2},
    ]) == 1.2


def test_latest_attempt_gpa_uses_latest_repeat_and_handles_empty_history():
    assert latest_attempt_gpa([
        {'code': 'IF101', 'semester': 1, 'grade_point': 0.0, 'sks': 3},
        {'code': 'IF101', 'semester': 2, 'grade_point': 4.0, 'sks': 3},
    ]) == 4.0
    assert latest_attempt_gpa([]) is None


def test_earned_credits_count_passed_course_once_even_after_failed_repeat():
    assert earned_credits([
        {'code': 'IF101', 'grade': 'A', 'sks': 3},
        {'code': 'IF101', 'grade': 'E', 'sks': 3},
        {'code': 'IF102', 'grade': 'E', 'sks': 2},
        {'code': 'IF103', 'grade': 'C', 'sks': 2},
    ], {'A', 'C'}) == 5


def test_course_selection_requires_every_recommended_mandatory_course(monkeypatch):
    from app.services import academic

    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    recommendations = [
        {
            'code': 'REQ101',
            'name': 'Mata Kuliah Wajib',
            'sks': 3,
            'category': 'Wajib',
            'mandatory': True,
        },
        {
            'code': 'ELC101',
            'name': 'Mata Kuliah Pilihan',
            'sks': 3,
            'category': 'Pilihan',
            'mandatory': False,
        },
    ]
    monkeypatch.setattr(
        academic,
        'build_recommendation_result',
        lambda *_: {
            'status': 'ready',
            'target_semester': 2,
            'recommendations': recommendations,
            'rejected': [],
            'profile': {'kuota_sks': 20},
        },
    )

    try:
        with Session(engine) as db:
            student = User(
                nim='MANDATORY-TEST',
                full_name='Mahasiswa Wajib',
                role='mahasiswa',
                password_hash='test',
            )
            db.add_all([
                student,
                Course(
                    code='REQ101',
                    name='Mata Kuliah Wajib',
                    sks=3,
                    semester=2,
                    category='Wajib',
                    is_active=True,
                ),
                Course(
                    code='ELC101',
                    name='Mata Kuliah Pilihan',
                    sks=3,
                    semester=2,
                    category='Pilihan',
                    is_active=True,
                ),
            ])
            db.commit()

            with pytest.raises(ValueError, match='REQ101'):
                academic.validate_course_selection(db, student, ['ELC101'], 2)

            selected = academic.validate_course_selection(
                db,
                student,
                ['REQ101', 'ELC101'],
                2,
            )
            assert [course['code'] for course in selected] == ['REQ101', 'ELC101']
    finally:
        engine.dispose()


def _create_capacity_database(path):
    engine = create_engine(f'sqlite:///{path}', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            User(nim='CAP-STUDENT-1', full_name='Student 1', role='mahasiswa', password_hash='test'),
            User(nim='CAP-STUDENT-2', full_name='Student 2', role='mahasiswa', password_hash='test'),
            Course(
                code='CAP101',
                name='Capacity',
                sks=3,
                semester=1,
                available_semesters='1',
                category='Wajib',
                capacity=1,
                is_active=True,
            ),
            Course(
                code='CAP102',
                name='Replacement',
                sks=3,
                semester=1,
                available_semesters='1',
                category='Wajib',
                capacity=1,
                is_active=True,
            ),
        ])
        db.commit()
    return engine


def test_concurrent_reservations_cannot_oversell_last_seat(tmp_path):
    engine = _create_capacity_database(tmp_path / 'capacity.sqlite')
    barrier = Barrier(2)
    now = datetime.now()

    def reserve(nim):
        with Session(engine) as db:
            student = db.query(User).filter(User.nim == nim).one()
            barrier.wait()
            begin_capacity_transaction(db)
            course = {'code': 'CAP101', 'name': 'Capacity', 'sks': 3}
            try:
                lock_capacity_courses(db, ['CAP101'])
                assert_course_capacity(db, [course])
            except ValueError:
                db.rollback()
                return False
            db.add(StudyPlan(
                student_id=student.id,
                semester=1,
                courses_json=json.dumps([course]),
                status='pending',
                advisor_note='',
                created_at=now,
                updated_at=now,
            ))
            db.commit()
            return True

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, ['CAP-STUDENT-1', 'CAP-STUDENT-2']))
        assert sorted(results) == [False, True]
    finally:
        engine.dispose()


def test_pending_kprs_reserves_added_seat_and_cancellation_releases_it(tmp_path):
    engine = _create_capacity_database(tmp_path / 'kprs-capacity.sqlite')
    now = datetime.now()
    try:
        with Session(engine) as db:
            student = db.query(User).filter(User.nim == 'CAP-STUDENT-1').one()
            plan = StudyPlan(
                student_id=student.id,
                semester=1,
                courses_json='[{"code":"CAP101","name":"Capacity","sks":3}]',
                status='approved',
                advisor_note='',
                created_at=now,
                updated_at=now,
            )
            db.add(plan)
            db.flush()
            request = KprsRequest(
                student_id=student.id,
                study_plan_id=plan.id,
                before_json='[{"code":"CAP101","name":"Capacity","sks":3}]',
                after_json='[{"code":"CAP102","name":"Replacement","sks":3}]',
                reason='Penggantian jadwal mata kuliah',
                status='pending',
                reviewer_note='',
                created_at=now,
                updated_at=now,
            )
            db.add(request)
            db.commit()

            with pytest.raises(ValueError, match='CAP102 sudah penuh'):
                assert_course_capacity(
                    db,
                    [{'code': 'CAP102', 'name': 'Replacement', 'sks': 3}],
                )

            request.status = 'cancelled'
            db.commit()
            assert_course_capacity(
                db,
                [{'code': 'CAP102', 'name': 'Replacement', 'sks': 3}],
            )
    finally:
        engine.dispose()



def test_parallel_sections_validate_schedule_selection_and_capacity(monkeypatch):
    from app.services import academic

    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    recommendations = [
        {'code': 'PAR101', 'name': 'Pemrograman Paralel', 'sks': 3, 'category': 'Pilihan', 'mandatory': False},
        {'code': 'PAR102', 'name': 'Jaringan Lanjut', 'sks': 3, 'category': 'Pilihan', 'mandatory': False},
    ]
    monkeypatch.setattr(
        academic,
        'build_recommendation_result',
        lambda *_: {
            'status': 'ready',
            'target_semester': 3,
            'recommendations': recommendations,
            'rejected': [],
            'profile': {'kuota_sks': 20},
        },
    )

    try:
        with Session(engine) as db:
            student = User(
                nim='PARALLEL-TEST',
                full_name='Mahasiswa Paralel',
                role='mahasiswa',
                password_hash='test',
            )
            first_course = Course(
                code='PAR101', name='Pemrograman Paralel', sks=3,
                semester=3, category='Pilihan', capacity=40, is_active=True,
            )
            second_course = Course(
                code='PAR102', name='Jaringan Lanjut', sks=3,
                semester=3, category='Pilihan', capacity=40, is_active=True,
            )
            db.add_all([student, first_course, second_course])
            db.flush()
            section_a = CourseClass(
                course_code='PAR101', class_name='A', room='Lab 1',
                day='Selasa', start_time='08:00', end_time='10:00',
                capacity=1, semester='3', is_open=True,
            )
            section_b = CourseClass(
                course_code='PAR101', class_name='B', room='Lab 2',
                day='Rabu', start_time='08:00', end_time='10:00',
                capacity=1, semester='3', is_open=True,
            )
            second_section = CourseClass(
                course_code='PAR102', class_name='A', room='Ruang 1',
                day='Selasa', start_time='09:00', end_time='11:00',
                capacity=5, semester='3', is_open=True,
            )
            db.add_all([section_a, section_b, second_section])
            db.flush()

            with pytest.raises(ValueError, match='Pilih kelas paralel'):
                academic.validate_course_selection(db, student, ['PAR101'], 3)

            with pytest.raises(ValueError, match='berbenturan'):
                academic.validate_course_selection(
                    db, student, ['PAR101', 'PAR102'], 3,
                    {'PAR101': section_a.id, 'PAR102': second_section.id},
                )

            selected = academic.validate_course_selection(
                db, student, ['PAR101', 'PAR102'], 3,
                {'PAR101': section_b.id, 'PAR102': second_section.id},
            )
            assert selected[0]['class_id'] == section_b.id
            assert selected[0]['schedule'] == 'Rabu, 08:00-10:00'
            assert selected[1]['class_id'] == second_section.id

            with pytest.raises(ValueError, match='tidak tersedia'):
                academic.validate_course_selection(
                    db, student, ['PAR101'], 3,
                    {'PAR101': second_section.id},
                )

            now = datetime.now()
            db.add(StudyPlan(
                student_id=student.id,
                semester=3,
                courses_json=json.dumps([selected[0]]),
                status='pending',
                advisor_note='',
                created_at=now,
                updated_at=now,
            ))
            db.commit()

            assert class_occupancy(db, section_b.id) == 1
            assert class_occupancy(db, section_a.id) == 0
            assert_course_capacity(db, [{'code': 'PAR101', 'class_id': section_a.id}])
            with pytest.raises(ValueError, match='Kuota kelas B'):
                assert_course_capacity(db, [{'code': 'PAR101', 'class_id': section_b.id}])
    finally:
        engine.dispose()
