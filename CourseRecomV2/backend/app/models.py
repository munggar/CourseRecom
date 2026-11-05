from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    nim = Column(String(20), unique=True, nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    role = Column(String(20), nullable=False, default='mahasiswa')
    email = Column(String(120), nullable=True)
    username = Column(String(120), nullable=True, unique=True, index=True)
    program_study = Column(String(120), nullable=True)
    angkatan = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)
    token_version = Column(Integer, nullable=False, default=0)
    phone_number = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    semester = Column(Integer, nullable=True)
    ipk = Column(Float, nullable=True)
    sks_lulus = Column(Integer, nullable=True)
    sks_sisa = Column(Integer, nullable=True)
    kuota_sks = Column(Integer, nullable=True)
    interests = Column(String(255), nullable=True)
    advisor_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    records = relationship('StudentRecord', back_populates='student')


class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    sks = Column(Integer, nullable=False)
    semester = Column(Integer, nullable=False)
    available_semesters = Column(String(40), nullable=True)
    category = Column(String(60), nullable=False)
    description = Column(Text, nullable=True)
    prerequisite_text = Column(Text, nullable=True)
    day = Column(String(20), nullable=True)
    time = Column(String(60), nullable=True)
    capacity = Column(Integer, nullable=False, default=40)
    prerequisite_codes = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)


class StudentRecord(Base):
    __tablename__ = 'student_records'
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    course_code = Column(String(20), nullable=False)
    grade = Column(String(2), nullable=False)
    semester = Column(Integer, nullable=True)
    course_name = Column(String(120), nullable=True)
    sks = Column(Integer, nullable=True)
    numeric_grade = Column(Float, nullable=True)
    grade_point = Column(Float, nullable=True)
    is_passed = Column(Boolean, nullable=True)
    student = relationship('User', back_populates='records')


class RecommendationCache(Base):
    __tablename__ = 'recommendation_cache'
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    course_code = Column(String(20), nullable=False)
    score = Column(Float, nullable=False)
    reasons = Column(Text, nullable=False)


class KhsDocument(Base):
    __tablename__ = 'khs_documents'
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    parsed_data = Column(Text, nullable=False)
    content = Column(LargeBinary, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)


class StudyPlan(Base):
    __tablename__ = 'study_plans'
    __table_args__ = (
        Index(
            'uq_study_plans_one_pending_per_student',
            'student_id',
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
    )
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    semester = Column(Integer, nullable=False)
    courses_json = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default='pending')
    advisor_note = Column(Text, nullable=False, default='')
    reviewer_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class RecommendationModelVersion(Base):
    __tablename__ = 'recommendation_model_versions'
    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(40), nullable=False, unique=True)
    method = Column(String(80), nullable=False)
    dataset_size = Column(Integer, nullable=False)
    metrics = Column(Text, nullable=False)
    trained_at = Column(DateTime, nullable=False)


class KrsDocument(Base):
    __tablename__ = 'krs_documents'
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    study_plan_id = Column(Integer, ForeignKey('study_plans.id'), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    size = Column(Integer, nullable=False)
    content = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, nullable=False)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    actor_name = Column(String(120), nullable=True)
    action = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(50), nullable=False, index=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)


class SystemSetting(Base):
    __tablename__ = 'system_settings'
    key = Column(String(80), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class OfficialKrsDocument(Base):
    __tablename__ = 'official_krs_documents'
    id = Column(Integer, primary_key=True, index=True)
    study_plan_id = Column(Integer, ForeignKey('study_plans.id'), nullable=False, unique=True, index=True)
    student_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    sha256 = Column(String(64), nullable=False)
    verification_token = Column(String(255), nullable=False, unique=True)
    content = Column(LargeBinary, nullable=False)
    issued_at = Column(DateTime, nullable=False)


class CourseClass(Base):
    __tablename__ = 'course_classes'
    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String(20), nullable=False, index=True)
    class_name = Column(String(40), nullable=False)
    lecturer_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    room = Column(String(40), nullable=False)
    day = Column(String(20), nullable=False)
    start_time = Column(String(5), nullable=False)
    end_time = Column(String(5), nullable=False)
    capacity = Column(Integer, nullable=False, default=40)
    semester = Column(String(20), nullable=False)
    is_open = Column(Boolean, nullable=False, default=True)


class KprsRequest(Base):
    __tablename__ = 'kprs_requests'
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    study_plan_id = Column(Integer, ForeignKey('study_plans.id'), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    before_json = Column(Text, nullable=False)
    after_json = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default='pending')
    reviewer_note = Column(Text, nullable=False, default='')
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
