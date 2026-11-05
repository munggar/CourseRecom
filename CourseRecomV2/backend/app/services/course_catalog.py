import csv
import io
import re
import unicodedata
from zipfile import BadZipFile
from xml.etree.ElementTree import ParseError

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException


FIELD_ALIASES = {
    'semester': {'semester'},
    'code': {'code', 'kodemk'},
    'name': {'name', 'namamk'},
    'category': {'category', 'kategori'},
    'sks': {'sks'},
    'prerequisite_text': {'prerequisite', 'prasyarat', 'matakuliahprasyarat', 'prerequisitecodes'},
    'description': {'description', 'keterangan', 'keterangancatatan', 'catatan'},
    'day': {'day', 'hari'},
    'time': {'time', 'waktu'},
}
REQUIRED_FIELDS = {'semester', 'code', 'name', 'category', 'sks'}


def _normalized_header(value: object) -> str:
    return re.sub(r'[^a-z0-9]', '', str(value or '').casefold())


def _normalized_name(value: str) -> str:
    value = unicodedata.normalize('NFKD', value).casefold()
    value = ''.join(character for character in value if not unicodedata.combining(character))
    return ' '.join(re.findall(r'[a-z0-9]+', value))


def _normalize_headers(headers: list[object]) -> dict[int, str]:
    normalized: dict[int, str] = {}
    for index, value in enumerate(headers):
        header = _normalized_header(value)
        for field, aliases in FIELD_ALIASES.items():
            if header in aliases:
                normalized[index] = field
                break
    return normalized


def _semester_number(value: object, row_number: int) -> int:
    match = re.search(r'\d{1,2}', str(value or ''))
    if not match or not 1 <= int(match.group()) <= 14:
        raise ValueError(f'Baris {row_number}: semester harus bernilai 1 sampai 14.')
    return int(match.group())


def _credits(value: object, row_number: int) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Baris {row_number}: SKS harus berupa angka bulat.') from exc
    if not number.is_integer() or not 1 <= number <= 10:
        raise ValueError(f'Baris {row_number}: SKS harus bernilai 1 sampai 10.')
    return int(number)


def _read_rows(headers: list[object], data_rows: list[tuple[object, ...]], first_data_row: int) -> list[dict]:
    header_map = _normalize_headers(headers)
    missing = REQUIRED_FIELDS - set(header_map.values())
    if missing:
        raise ValueError(f'Kolom wajib belum lengkap: {", ".join(sorted(missing))}.')

    courses_by_code: dict[str, dict] = {}
    for row_number, values in enumerate(data_rows, start=first_data_row):
        row = {
            field: str(values[index] or '').strip()
            for index, field in header_map.items()
            if index < len(values)
        }
        if not any(row.get(field) for field in ('code', 'name', 'sks', 'category')):
            continue

        code = row.get('code', '').upper()
        name = row.get('name', '')
        category = row.get('category', '')
        if not code or not name or not category:
            raise ValueError(f'Baris {row_number}: kode, nama, dan kategori wajib diisi.')
        if len(code) > 20 or len(name) > 120 or len(category) > 60:
            raise ValueError(f'Baris {row_number}: kode, nama, atau kategori melebihi batas panjang.')

        semester = _semester_number(row.get('semester'), row_number)
        sks = _credits(row.get('sks'), row_number)
        course = courses_by_code.get(code)
        if course and course['sks'] != sks:
            raise ValueError(f'Baris {row_number}: data SKS untuk kode {code} tidak konsisten.')

        if not course:
            course = {
                'code': code,
                'name': name,
                'sks': sks,
                'semester': semester,
                'available_semesters': {semester},
                'category': category,
                'description': row.get('description', ''),
                'prerequisite_text': row.get('prerequisite_text', ''),
                'prerequisite_codes': '',
                'day': row.get('day', ''),
                'time': row.get('time', ''),
            }
            courses_by_code[code] = course
        else:
            course['available_semesters'].add(semester)
            course['semester'] = min(course['semester'], semester)
            course['category'] = category
            if len(name) > len(course['name']):
                course['name'] = name
            for field in ('description', 'prerequisite_text', 'day', 'time'):
                value = row.get(field, '')
                if value and value not in course[field].split('\n'):
                    course[field] = '\n'.join(filter(None, [course[field], value]))

    courses = list(courses_by_code.values())
    name_to_codes: dict[str, set[str]] = {}
    for course in courses:
        name_to_codes.setdefault(_normalized_name(course['name']), set()).add(course['code'])

    for course in courses:
        prerequisites = course['prerequisite_text']
        if _normalized_name(prerequisites) in {'', 'tidak ada', 'none', 'n a'}:
            resolved_codes: set[str] = set()
        else:
            normalized_prerequisites = _normalized_name(prerequisites)
            resolved_codes = set()
            for name, codes in name_to_codes.items():
                if name and f' {name} ' in f' {normalized_prerequisites} ':
                    resolved_codes.update(codes)
            for code in courses_by_code:
                if re.search(rf'(?<![A-Z0-9]){re.escape(code)}(?![A-Z0-9])', prerequisites, re.IGNORECASE):
                    resolved_codes.add(code)
        course['prerequisite_codes'] = ','.join(sorted(resolved_codes))
        course['available_semesters'] = ','.join(
            str(number) for number in sorted(course['available_semesters'])
        )

    return courses


def parse_course_catalog(content: bytes, filename: str) -> tuple[list[dict], bool]:
    if filename.lower().endswith('.xlsx'):
        try:
            workbook = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
            worksheet = next(
                (
                    sheet for sheet in workbook.worksheets
                    if any(
                        REQUIRED_FIELDS.issubset(set(_normalize_headers(row).values()))
                        for row in sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 30), values_only=True)
                    )
                ),
                None,
            )
            if worksheet is None:
                raise ValueError('Header katalog tidak ditemukan pada 30 baris pertama Excel.')

            header_row_number = next(
                row_number
                for row_number, row in enumerate(
                    worksheet.iter_rows(min_row=1, max_row=min(worksheet.max_row, 30), values_only=True),
                    start=1,
                )
                if REQUIRED_FIELDS.issubset(set(_normalize_headers(row).values()))
            )
            rows = list(
                worksheet.iter_rows(
                    min_row=header_row_number + 1,
                    max_row=worksheet.max_row,
                    values_only=True,
                )
            )
            headers = next(
                worksheet.iter_rows(
                    min_row=header_row_number,
                    max_row=header_row_number,
                    values_only=True,
                )
            )
            courses = _read_rows(list(headers), rows, header_row_number + 1)
            if not courses:
                raise ValueError('File Excel tidak berisi data mata kuliah.')
            return courses, True
        except (OSError, ValueError, KeyError, BadZipFile, InvalidFileException, ParseError) as exc:
            raise ValueError(f'Excel tidak dapat dibaca: {exc}') from exc
        finally:
            if 'workbook' in locals():
                workbook.close()

    if filename.lower().endswith('.csv'):
        try:
            reader = csv.reader(io.StringIO(content.decode('utf-8-sig')))
            rows = list(reader)
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ValueError(f'CSV tidak dapat dibaca: {exc}') from exc
        if not rows:
            raise ValueError('CSV tidak memiliki baris header.')
        courses = _read_rows(rows[0], [tuple(row) for row in rows[1:]], 2)
        if not courses:
            raise ValueError('File CSV tidak berisi data mata kuliah.')
        return courses, False

    raise ValueError('Impor katalog hanya mendukung file Excel (.xlsx) atau CSV.')
