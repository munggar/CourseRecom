import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Course, CourseClass, Room

ALLOWED_DAYS = ('Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu')
DAY_START_MINUTES = 7 * 60
DAY_END_MINUTES = 18 * 60
SLOT_STEP_MINUTES = 10


def parse_clock(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
        raise ValueError('Format jam harus HH:MM.')
    hour, minute = value.split(':')
    return int(hour) * 60 + int(minute)


def format_clock(value: int) -> str:
    return f'{value // 60:02d}:{value % 60:02d}'


def duration_for_sks(sks: int) -> int:
    if not isinstance(sks, int) or sks < 1:
        raise ValueError('Bobot SKS mata kuliah tidak valid.')
    return sks * 50


def validate_room_code(room_code: str) -> str:
    normalized = str(room_code or '').strip().upper()
    if not re.fullmatch(r'FT[234]\d{2}', normalized):
        raise ValueError('Kode ruang harus mengikuti format FT2xx, FT3xx, atau FT4xx (contoh: FT401).')
    return normalized


def room_is_available(db: Session, room_code: str) -> Room:
    normalized = validate_room_code(room_code)
    room = db.query(Room).filter(Room.code == normalized).first()
    if not room:
        raise ValueError(f'Ruang {normalized} belum terdaftar pada inventaris ruangan.')
    if not room.is_active:
        raise ValueError(f'Ruang {normalized} belum diaktifkan Admin setelah verifikasi fisik.')
    return room


def _find_conflict(
    db: Session,
    day: str,
    start_minutes: int,
    end_minutes: int,
    room_code: str,
    lecturer_id: int | None,
    exclude_class_id: int | None = None,
) -> dict | None:
    query = db.query(CourseClass).filter(
        CourseClass.day.ilike(day.strip()),
        CourseClass.is_open.is_(True),
    )
    if exclude_class_id is not None:
        query = query.filter(CourseClass.id != exclude_class_id)
    for other in query.all():
        other_start = parse_clock(other.start_time)
        other_end = parse_clock(other.end_time)
        if start_minutes >= other_end or end_minutes <= other_start:
            continue
        if other.room.strip().upper() == room_code.upper():
            return {'type': 'room', 'class_id': other.id, 'room': other.room, 'start_time': other.start_time, 'end_time': other.end_time}
        if lecturer_id is not None and other.lecturer_id == lecturer_id:
            return {'type': 'lecturer', 'class_id': other.id, 'start_time': other.start_time, 'end_time': other.end_time}
    return None


def validate_class_schedule(
    db: Session,
    *,
    course_code: str,
    room_code: str,
    day: str,
    start_time: str,
    lecturer_id: int | None,
    exclude_class_id: int | None = None,
) -> str:
    room_code = validate_room_code(room_code)
    room_is_available(db, room_code)
    if day not in ALLOWED_DAYS:
        raise ValueError('Hari perkuliahan hanya Senin sampai Sabtu.')
    course = db.query(Course).filter(Course.code == course_code.upper(), Course.is_active.is_(True)).first()
    if not course:
        raise ValueError('Mata kuliah tidak ditemukan atau tidak aktif.')
    start_minutes = parse_clock(start_time)
    duration = duration_for_sks(course.sks)
    end_minutes = start_minutes + duration
    if start_minutes < DAY_START_MINUTES or end_minutes > DAY_END_MINUTES:
        raise ValueError(
            f'Jadwal {course.sks} SKS berdurasi {duration} menit. '
            'Perkuliahan harus berada pada rentang 07:00–18:00.'
        )
    if start_minutes % SLOT_STEP_MINUTES != 0:
        raise ValueError('Jam mulai harus mengikuti kelipatan 10 menit.')
    conflict = _find_conflict(
        db, day, start_minutes, end_minutes, room_code, lecturer_id, exclude_class_id,
    )
    if conflict:
        if conflict['type'] == 'room':
            raise ValueError(
                f'Ruangan {room_code} sudah digunakan oleh kelas #{conflict["class_id"]} '
                f'pada {day} {conflict["start_time"]}-{conflict["end_time"]}.'
            )
        raise ValueError(
            f'Dosen pengampu sudah mengajar kelas #{conflict["class_id"]} '
            f'pada {day} {conflict["start_time"]}-{conflict["end_time"]}.'
        )
    return format_clock(end_minutes)


def build_available_start_times(
    db: Session,
    *,
    course_code: str,
    room_code: str,
    day: str,
    lecturer_id: int | None,
    exclude_class_id: int | None = None,
) -> list[dict]:
    normalized_room = validate_room_code(room_code)
    room_is_available(db, normalized_room)
    course = db.query(Course).filter(Course.code == course_code.upper(), Course.is_active.is_(True)).first()
    if not course:
        raise ValueError('Pilih mata kuliah aktif terlebih dahulu.')
    if day not in ALLOWED_DAYS:
        raise ValueError('Pilih hari perkuliahan Senin sampai Sabtu.')
    duration = duration_for_sks(course.sks)
    last_start = DAY_END_MINUTES - duration
    slots = []
    for start_minutes in range(DAY_START_MINUTES, last_start + 1, SLOT_STEP_MINUTES):
        end_minutes = start_minutes + duration
        conflict = _find_conflict(
            db, day, start_minutes, end_minutes, normalized_room, lecturer_id, exclude_class_id,
        )
        if conflict is None:
            slots.append({
                'start_time': format_clock(start_minutes),
                'end_time': format_clock(end_minutes),
                'duration_minutes': duration,
            })
    return slots
