import json
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models import SystemSetting

WIB = timezone(timedelta(hours=7))


def parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=WIB)
    return parsed.astimezone(WIB)


def _setting(db: Session | None, key: str) -> str | None:
    if db is None:
        return None
    value = db.query(SystemSetting.value).filter(SystemSetting.key == key).scalar()
    return value


def get_sks_quota(ipk: float | None, db: Session | None = None) -> int:
    raw = _setting(db, 'max_sks_by_ips')
    if raw:
        try:
            rules = json.loads(raw)
            for threshold in sorted(((float(k), int(v)) for k, v in rules.items() if k != 'default'), reverse=True):
                if ipk is not None and ipk >= threshold[0]:
                    return threshold[1]
            return int(rules.get('default', 20))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    if ipk is not None and ipk >= 3.35:
        return 24
    if ipk is not None and ipk >= 3.00:
        return 22
    return 20


def assert_krs_period_open(db: Session) -> None:
    start = _setting(db, 'krs_period_start')
    end = _setting(db, 'krs_period_end')
    deadline = _setting(db, 'krs_fill_deadline')
    if start or end:
        now = datetime.now(WIB)
        if start:
            try:
                if now < parse_iso_datetime(start):
                    raise ValueError('Periode pengajuan KRS belum dimulai.')
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
        if end:
            try:
                if now > parse_iso_datetime(end):
                    raise ValueError('Periode pengajuan KRS sudah berakhir.')
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
    if deadline:
        try:
            if datetime.now(WIB) > parse_iso_datetime(deadline):
                raise ValueError('Batas waktu pengisian KRS telah berakhir.')
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


def assert_kprs_period_open(db: Session) -> None:
    start = _setting(db, 'kprs_period_start')
    end = _setting(db, 'kprs_period_end')
    if not start or not end:
        raise ValueError('Periode KPRS belum dikonfigurasi.')
    try:
        start_time = parse_iso_datetime(start)
        end_time = parse_iso_datetime(end)
    except (TypeError, ValueError) as exc:
        raise ValueError('Format periode KPRS tidak valid.') from exc
    if end_time < start_time:
        raise ValueError('Periode akhir KPRS tidak boleh mendahului periode mulai.')
    now = datetime.now(WIB)
    if now < start_time or now > end_time:
        raise ValueError('Periode KPRS ditutup.')


def is_prereq_met(student_records: List[str], course_prereq: List[str]) -> bool:
    if not course_prereq:
        return True
    return all(item in student_records for item in course_prereq)


def validate_sks(selected_sks: int, kuota_sks: int) -> bool:
    return selected_sks <= kuota_sks


def has_schedule_conflict(new_day: str, new_time: str, existing: List[Tuple[str, str]]) -> bool:
    if not new_day or not new_time:
        return False
    def parse_interval(value: str) -> tuple[datetime, datetime] | None:
        parts = [part.strip() for part in value.replace('–', '-').split('-', 1)]
        if len(parts) != 2:
            return None
        try:
            return datetime.strptime(parts[0], '%H:%M'), datetime.strptime(parts[1], '%H:%M')
        except ValueError:
            return None

    new_interval = parse_interval(new_time)
    if not new_interval:
        return False
    for day, time in existing:
        existing_interval = parse_interval(time)
        if (
            day.strip().casefold() == new_day.strip().casefold()
            and existing_interval
            and new_interval[0] < existing_interval[1]
            and existing_interval[0] < new_interval[1]
        ):
            return True
    return False
