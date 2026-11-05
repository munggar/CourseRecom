import re
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class UserLogin(BaseModel):
    username: str
    password: str
    role: Optional[Literal['mahasiswa', 'dosen', 'admin']] = None


class StudentRegistration(BaseModel):
    nim: str = Field(min_length=2, max_length=20)
    full_name: str = Field(min_length=2, max_length=120)
    username: str | None = Field(default=None, min_length=2, max_length=120)
    program_study: str = Field(default='', max_length=120)
    angkatan: str = Field(default='', max_length=20)
    password: str = Field(min_length=8, max_length=72)

    @field_validator('nim', 'full_name')
    @classmethod
    def strip_registration_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Nilai minimal harus berisi 2 karakter.')
        return value

    @field_validator('password')
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode('utf-8')) > 72:
            raise ValueError('Password tidak boleh melebihi 72 byte.')
        return value


class LecturerRegistration(BaseModel):
    nip: str = Field(min_length=2, max_length=20)
    full_name: str = Field(min_length=2, max_length=120)
    username: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, max_length=120)
    password: str = Field(min_length=8, max_length=72)

    @field_validator('nip', 'full_name')
    @classmethod
    def strip_registration_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Nilai minimal harus berisi 2 karakter.')
        return value

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator('password')
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode('utf-8')) > 72:
            raise ValueError('Password tidak boleh melebihi 72 byte.')
        return value


class LecturerUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    username: str = Field(min_length=2, max_length=120)
    email: str | None = Field(default=None, max_length=120)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nim: str
    full_name: str
    role: str
    email: Optional[str] = None
    semester: Optional[int] = None
    ipk: Optional[float] = None
    sks_lulus: Optional[int] = None
    sks_sisa: Optional[int] = None
    kuota_sks: Optional[int] = None
    interests: Optional[str] = None
    username: Optional[str] = None
    program_study: Optional[str] = None
    angkatan: Optional[str] = None
    phone_number: Optional[str] = None


class AccountProfileResponse(UserOut):
    access_token: Optional[str] = None


class AccountProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: Optional[str] = Field(default=None, max_length=120)
    username: str = Field(min_length=2, max_length=120)
    program_study: Optional[str] = Field(default=None, max_length=120)
    angkatan: Optional[str] = Field(default=None, max_length=20)
    phone_number: Optional[str] = Field(default=None, max_length=20)
    current_password: Optional[str] = Field(default=None, max_length=72)
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=72)

    @field_validator('phone_number')
    @classmethod
    def normalize_phone_number(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = re.sub(r'(?:[\s().-]+)', '', value.strip())
        if normalized.startswith('00'):
            normalized = '+' + normalized[2:]
        elif normalized.startswith('0'):
            normalized = '+62' + normalized[1:]
        if not re.fullmatch(r'\+?[1-9][0-9]{7,14}', normalized):
            raise ValueError('Nomor telepon harus berisi 8-15 digit dan format internasional yang valid.')
        return normalized

    @model_validator(mode='after')
    def validate_password_change(self):
        if bool(self.new_password) != bool(self.current_password):
            raise ValueError('Password saat ini dan password baru wajib diisi bersamaan.')
        return self


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    sks: int
    semester: int
    available_semesters: Optional[str] = None
    category: str
    description: Optional[str]
    prerequisite_text: Optional[str] = None
    prerequisite_codes: Optional[str]
    day: Optional[str]
    time: Optional[str]


class CourseMutation(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=120)
    sks: int = Field(ge=1, le=10)
    semester: int = Field(ge=1, le=14)
    available_semesters: str = Field(min_length=1, max_length=40)
    category: str = Field(min_length=1, max_length=60)
    description: str = Field(default='', max_length=2000)
    prerequisite_text: str = Field(default='', max_length=1000)
    prerequisite_codes: str = Field(default='', max_length=255)
    day: str = Field(default='', max_length=40)
    time: str = Field(default='', max_length=60)
    capacity: int = Field(default=40, ge=0, le=10000)

    @field_validator('code', 'name', 'category')
    @classmethod
    def strip_required_course_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('Kolom wajib tidak boleh kosong.')
        return value

    @field_validator('code')
    @classmethod
    def normalize_course_code(cls, value: str) -> str:
        return value.upper()

    @field_validator('available_semesters')
    @classmethod
    def validate_available_semesters(cls, value: str) -> str:
        semesters = [item.strip() for item in value.split(',') if item.strip()]
        if not semesters or any(not item.isdigit() or not 1 <= int(item) <= 14 for item in semesters):
            raise ValueError('Semester tersedia harus berupa daftar angka 1 sampai 14.')
        return ','.join(dict.fromkeys(semesters))


class RecommendationItem(BaseModel):
    code: str
    name: str
    sks: int
    score: float
    reasons: List[str]
    valid: bool
    reason_block: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    prerequisite_text: Optional[str] = None
    semester: Optional[int] = None


class ProfileUpdate(BaseModel):
    interests: str = Field(min_length=1, max_length=255)

    @field_validator('interests')
    @classmethod
    def validate_interests(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('Pilih minimal satu peminatan.')
        if len([interest for interest in value.split(',') if interest.strip()]) > 1:
            raise ValueError('Pilih satu peminatan saja.')
        return value


class AdvisorMapping(BaseModel):
    advisor_nim: str = Field(min_length=2, max_length=20)
    reason: str = Field(default='', max_length=1000)


class KhsCourseEntry(BaseModel):
    semester: int = Field(ge=1, le=14)
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    sks: int = Field(ge=1, le=10)
    grade: str = Field(min_length=1, max_length=2)
    numeric_grade: Optional[float] = Field(default=None, ge=0, le=100)
    grade_point: Optional[float] = Field(default=None, ge=0, le=4)


class KhsConfirm(BaseModel):
    nim: str
    full_name: str
    program_study: str = ''
    current_semester: int = Field(ge=1, le=14)
    ipk: Optional[float] = Field(default=None, ge=0, le=4)
    ip_semesters: dict[int, Optional[float]] = Field(default_factory=dict)
    courses: List[KhsCourseEntry]


class StudyPlanSubmit(BaseModel):
    course_codes: List[str] = Field(min_length=1, max_length=30)

    @field_validator('course_codes')
    @classmethod
    def validate_course_codes(cls, value: List[str]) -> List[str]:
        codes = [code.strip().upper() for code in value]
        if any(not code for code in codes):
            raise ValueError('Kode mata kuliah tidak boleh kosong.')
        if len(set(codes)) != len(codes):
            raise ValueError('Mata kuliah yang sama tidak boleh diajukan lebih dari sekali.')
        return codes


class StudyPlanReview(BaseModel):
    status: str
    advisor_note: str = Field(default='', max_length=2000)

    @field_validator('status')
    @classmethod
    def validate_review_status(cls, value: str) -> str:
        if value not in {'approved', 'revision_requested'}:
            raise ValueError('Status review harus approved atau revision_requested.')
        return value

    @model_validator(mode='after')
    def require_note_for_revision(self):
        if self.status == 'revision_requested' and not self.advisor_note.strip():
            raise ValueError('Catatan dosen wajib diisi saat meminta revisi.')
        self.advisor_note = self.advisor_note.strip()
        return self


class StudyPlanUpdate(BaseModel):
    course_codes: List[str] = Field(min_length=1, max_length=30)

    @field_validator('course_codes')
    @classmethod
    def validate_course_codes(cls, value: List[str]) -> List[str]:
        codes = [code.strip().upper() for code in value]
        if any(not code for code in codes):
            raise ValueError('Kode mata kuliah wajib diisi.')
        if len(set(codes)) != len(codes):
            raise ValueError('Mata kuliah yang sama tidak boleh dipilih lebih dari sekali.')
        return codes


class SystemSettingUpdate(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    value: str = Field(max_length=2000)


class StudyPlanOverride(BaseModel):
    status: Literal['draft', 'revision_requested', 'pending', 'approved']
    reason: str = Field(min_length=10, max_length=2000)
    course_codes: List[str] | None = Field(default=None, max_length=30)


class CourseClassMutation(BaseModel):
    course_code: str = Field(min_length=2, max_length=20)
    class_name: str = Field(min_length=1, max_length=40)
    lecturer_id: int | None = None
    room: str = Field(min_length=1, max_length=40)
    day: str = Field(min_length=1, max_length=20)
    start_time: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    end_time: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    capacity: int = Field(ge=0, le=10000)
    semester: str = Field(min_length=1, max_length=20)
    is_open: bool = True

class KprsMutation(BaseModel):
    study_plan_id: int = Field(gt=0)
    course_codes: List[str] = Field(min_length=1, max_length=30)
    reason: str = Field(min_length=10, max_length=2000)


class KprsReview(BaseModel):
    status: Literal['approved', 'revision_requested', 'rejected']
    note: str = Field(min_length=3, max_length=2000)
