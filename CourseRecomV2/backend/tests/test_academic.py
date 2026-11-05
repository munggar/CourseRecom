import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import pytest

from app.database import Base
from app.models import Course, KprsRequest, StudyPlan, User
from app.services.academic import earned_credits, latest_attempt_gpa
from app.services.capacity import (
    assert_course_capacity,
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
