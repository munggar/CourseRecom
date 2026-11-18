from app.services.validation import (
    get_sks_quota,
    has_schedule_conflict,
    is_prereq_met,
    parse_iso_datetime,
    validate_sks,
)
from app.services.time_utils import utc_now, utc_now_naive


def test_prereq_met():
    assert is_prereq_met(['STAT', 'TI201'], ['STAT'])
    assert not is_prereq_met(['STAT'], ['TI201'])


def test_sks_limit():
    assert validate_sks(18, 22)
    assert not validate_sks(24, 22)


def test_sks_quota_uses_ipk_thresholds():
    assert get_sks_quota(3.35) == 24
    assert get_sks_quota(4.0) == 24
    assert get_sks_quota(3.34) == 22
    assert get_sks_quota(3.00) == 22
    assert get_sks_quota(2.99) == 20
    assert get_sks_quota(None) == 20


def test_schedule_conflict():
    assert has_schedule_conflict('Senin', '09:00-11:30', [('Senin', '09:00-11:30')])
    assert not has_schedule_conflict('Selasa', '09:00-11:30', [('Senin', '09:00-11:30')])
    assert has_schedule_conflict('Senin', '08:00-10:00', [('Senin', '09:00-11:00')])
    assert has_schedule_conflict('Senin', '08:30-09:30', [('Senin', '08:00-10:00')])
    assert not has_schedule_conflict('Senin', '08:00-10:00', [('Senin', '10:00-12:00')])
    assert not has_schedule_conflict('senin', '08:00 - 10:00', [('Senin', '10:00 - 12:00')])


def test_application_clock_has_utc_and_database_naive_forms():
    assert utc_now().tzinfo is not None
    assert utc_now_naive().tzinfo is None


def test_academic_period_iso_values_are_timezone_aware():
    open_time = parse_iso_datetime('2026-01-01T08:00:00')
    utc_time = parse_iso_datetime('2026-01-01T08:00:00Z')
    assert open_time.utcoffset().total_seconds() == 7 * 60 * 60
    assert utc_time.utcoffset().total_seconds() == 7 * 60 * 60
    assert utc_time.hour == 15


def test_ftii_program_interest_catalog_is_program_scoped():
    from app.services.program_interests import validate_program_interest

    assert validate_program_interest(
        'STI', 'Kecerdasan Bisnis'
    ) == ('Sistem dan Teknologi Informasi', 'Kecerdasan Bisnis')
    assert validate_program_interest('Teknik Mesin', 'Manufaktur') == ('Teknik Mesin', 'Manufaktur')
    try:
        validate_program_interest('Teknik Mesin', 'Kecerdasan Bisnis')
    except ValueError as exc:
        assert 'tidak sesuai' in str(exc)
    else:
        raise AssertionError('Interest dari prodi lain seharusnya ditolak.')


def test_program_name_normalization_accepts_official_labels_and_abbreviations():
    from app.services.program_interests import normalize_program_name, validate_program_interest

    assert normalize_program_name('Program Studi: Sistem dan Teknologi Informasi (STI)') == 'Sistem dan Teknologi Informasi'
    assert normalize_program_name('Prodi Teknik Informatika (TI)') == 'Teknik Informatika'
    assert validate_program_interest('STI', 'Manajemen Sistem Informasi') == (
        'Sistem dan Teknologi Informasi',
        'Manajemen Teknologi Informasi',
    )
