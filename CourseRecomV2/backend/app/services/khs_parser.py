import re
from io import BytesIO

import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
from pypdf import PdfReader


MAX_PDF_PAGES = 40
MAX_IMAGE_PIXELS = 12_000_000
SUPPORTED_IMAGE_FORMATS = {'BMP', 'JPEG', 'PNG', 'TIFF', 'WEBP'}
GRADE_POINTS = {
    'A': 4.0, 'A-': 3.7, 'B+': 3.3, 'B': 3.0, 'B-': 2.7,
    'C+': 2.3, 'C': 2.0, 'C-': 1.7, 'D': 1.0, 'E': 0.0, 'F': 0.0,
}
COURSE_ROW = re.compile(
    r'^\s*(?:\d{1,3}[.)]?\s+)?'
    r'(?P<code>[A-Z][A-Z0-9./-]{1,}|[0-9]{6,})\s+'
    r'(?P<name>.+?)\s+(?P<sks>\d{1,2})\s+'
    r'(?:(?P<score>\d{1,3}(?:[.,]\d+)?)\s+)?'
    r'(?P<grade>A-|A|B\+|B-|B|C\+|C-|C|D|E|F)'
    r'(?:\s+(?P<point>\d(?:\.\d+)?))?\s*$',
    re.IGNORECASE,
)
UHAMKA_HISTORI_ROW = re.compile(
    r'^\s*(?P<row>\d{1,3})\s+(?P<code>\d{6,})\s+'
    r'(?P<name>.+?)\s+(?P<sks>\d{1,2})\s+(?P<grade>[A-F](?:[+-]|[A-F])?)\s*$',
    re.IGNORECASE,
)
SEMESTER_MARKER = re.compile(r'\bsemester(?:\s+ke)?\s*[:\-]?\s*(\d{1,2})\b', re.IGNORECASE)
ACADEMIC_TERM_MARKER = re.compile(
    r'(?<!\d)(?P<year>\d{4})/(?P<next_year>\d{4})\s+(?P<term>Gasal|Genap)\b',
    re.IGNORECASE,
)
UHAMKA_COURSE_ROW = re.compile(
    r'^\s*\d{1,3}\s+(?P<sks>\d{1,2})\s*'
    r'(?P<grade>A-|A|B\+|B-|B|C\+|C-|C|D|E|F)'
    r'\s*(?:(?P<year>\d{4})/(?P<next_year>\d{4})\s+(?P<term>Gasal|Genap)\s+)?'
    r'(?P<code>[A-Z][A-Z0-9./-]{1,}|\d{6,})\s+(?P<name>.+?)\s*$',
    re.IGNORECASE,
)


def _parse_uhamka_course_line(line: str) -> dict | None:
    match = UHAMKA_COURSE_ROW.match(line)
    if not match:
        return None

    values = match.groupdict()
    grade = values['grade'].upper()
    try:
        sks = int(values['sks'])
        year = int(values['year']) if values['year'] else None
        next_year = int(values['next_year']) if values['next_year'] else None
    except ValueError:
        return None

    if (
        not 1 <= sks <= 10
        or not values['name'].strip()
        or (year is not None and next_year != year + 1)
        or (year is None) != (values['term'] is None)
    ):
        return None

    return {
        'code': values['code'].upper(),
        'name': values['name'].strip(),
        'sks': sks,
        'grade': grade,
        'numeric_grade': None,
        'grade_point': GRADE_POINTS[grade],
        'academic_year': year,
        'academic_term': values['term'].title() if values['term'] else None,
    }


def _parse_uhamka_histori_line(line: str) -> dict | None:
    match = UHAMKA_HISTORI_ROW.match(line)
    if not match:
        return None

    values = match.groupdict()
    grade = values['grade'].upper()
    if len(grade) == 2 and grade[0] == grade[1]:
        grade = grade[0]
    try:
        sks = int(values['sks'])
    except ValueError:
        return None
    name = values['name'].strip(' :-_')
    if not name or not 1 <= sks <= 10 or grade not in GRADE_POINTS:
        return None
    return {
        'code': values['code'],
        'name': name,
        'sks': sks,
        'grade': grade,
        'numeric_grade': None,
        'grade_point': GRADE_POINTS[grade],
    }


def _parse_course_line(line: str) -> dict | None:
    fields = [field.strip() for field in line.split('|')]
    if len(fields) >= 4 and fields[0].strip().isdigit():
        fields = fields[1:]
    if len(fields) >= 4 and re.fullmatch(
        r'(?:[A-Z][A-Z0-9./-]{1,}|[0-9]{6,})',
        fields[0],
        re.IGNORECASE,
    ):
        try:
            sks = int(fields[2])
        except ValueError:
            sks = 0
        grade_index = 3 if fields[3].upper() in GRADE_POINTS else 4
        grade = fields[grade_index].upper() if grade_index < len(fields) else ''
        if sks > 0 and grade in GRADE_POINTS:
            point = GRADE_POINTS[grade]
            numeric_grade = None
            if grade_index == 4:
                try:
                    numeric_grade = float(fields[3].replace(',', '.'))
                except ValueError:
                    pass
            if len(fields) > grade_index + 1:
                try:
                    point = float(fields[grade_index + 1].replace(',', '.'))
                except ValueError:
                    pass
            return {
                'code': fields[0].upper(),
                'name': fields[1],
                'sks': sks,
                'grade': grade,
                'numeric_grade': numeric_grade,
                'grade_point': point,
            }

    match = COURSE_ROW.match(line)
    if not match:
        return None
    values = match.groupdict()
    code = values['code'].upper()
    name = values['name'].strip(' :-')
    grade = values['grade'].upper()
    try:
        sks = int(values['sks'])
        point = float(values['point'].replace(',', '.')) if values['point'] else GRADE_POINTS[grade]
        numeric_grade = float(values['score'].replace(',', '.')) if values['score'] else None
    except (ValueError, KeyError):
        return None
    if (
        not name
        or not 1 <= sks <= 10
        or not 0 <= point <= 4
        or (numeric_grade is not None and not 0 <= numeric_grade <= 100)
    ):
        return None
    return {
        'code': code,
        'name': name,
        'sks': sks,
        'grade': grade,
        'numeric_grade': numeric_grade,
        'grade_point': point,
    }


def deduplicate_course_entries(courses: list[dict]) -> tuple[list[dict], int]:
    best_by_identity: dict[tuple[str, int], tuple[int, dict]] = {}
    for index, course in enumerate(courses):
        code = str(course.get('code', '')).strip().upper()
        semester = int(course.get('semester', 0) or 0)
        if not code or semester <= 0:
            continue
        identity = (code, semester)
        grade = course['grade'].upper()
        grade_point = GRADE_POINTS.get(grade, 0.0)
        numeric_grade = course.get('numeric_grade')
        rank = (
            grade_point,
            numeric_grade if numeric_grade is not None else -1.0,
            course.get('semester', 0),
        )
        current = best_by_identity.get(identity)
        if current is None:
            best_by_identity[identity] = (index, course)
            continue

        current_course = current[1]
        current_grade = current_course['grade'].upper()
        current_rank = (
            GRADE_POINTS.get(current_grade, 0.0),
            current_course.get('numeric_grade')
            if current_course.get('numeric_grade') is not None
            else -1.0,
            current_course.get('semester', 0),
        )
        if rank > current_rank:
            best_by_identity[identity] = (index, course)

    retained = sorted(best_by_identity.values(), key=lambda item: item[0])
    return [course for _, course in retained], len(courses) - len(retained)


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    if reader.is_encrypted:
        raise ValueError('PDF KHS terenkripsi; unggah PDF yang tidak dikunci.')
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError(f'PDF melebihi batas {MAX_PDF_PAGES} halaman.')

    layout_text = '\n'.join(page.extract_text(extraction_mode='layout') or '' for page in reader.pages)
    plain_text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    text = layout_text
    if any(_parse_uhamka_course_line(line) for line in plain_text.splitlines()):
        text = plain_text

    has_semester = SEMESTER_MARKER.search(text) is not None or ACADEMIC_TERM_MARKER.search(text) is not None
    has_courses = any(
        _parse_course_line(line) or _parse_uhamka_course_line(line)
        for line in text.splitlines()
    )
    if len(re.sub(r'\s', '', text)) >= 40 and has_semester and has_courses:
        return text

    images = convert_from_bytes(content, dpi=220, fmt='png')
    return '\n'.join(pytesseract.image_to_string(image, lang='ind+eng') for image in images)


def _extract_image_text(content: bytes) -> str:
    try:
        with Image.open(BytesIO(content)) as source:
            if source.format not in SUPPORTED_IMAGE_FORMATS:
                raise ValueError('Format gambar tidak didukung. Gunakan JPG, PNG, WEBP, TIFF, atau BMP.')
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError('Resolusi gambar terlalu besar. Maksimal 12 megapiksel per gambar.')
            image = ImageOps.exif_transpose(source).convert('L')
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Gambar tidak valid atau tidak dapat dibuka.') from exc

    if image.width < 2400:
        max_scale_without_exceeding_limit = int(
            (MAX_IMAGE_PIXELS / (image.width * image.height)) ** 0.5
        )
        scale = min(3, 2400 // image.width, max_scale_without_exceeding_limit)
        if scale > 1:
            image = image.resize((image.width * scale, image.height * scale))
    image = ImageOps.autocontrast(image).filter(ImageFilter.UnsharpMask(radius=1.5, percent=150, threshold=3))
    thresholded = image.point(lambda value: 255 if value >= 175 else 0)
    candidates = []
    try:
        for candidate_image, psm in (
            (image, 6),
            (image, 11),
            (image, 4),
            (thresholded, 6),
        ):
            text = pytesseract.image_to_string(
                candidate_image,
                lang='ind+eng',
                config=f'--oem 1 --psm {psm}',
            )
            candidates.append(text)
    except Exception as exc:
        raise ValueError(
            'OCR gambar gagal. Pastikan Tesseract dengan bahasa Indonesia dan Inggris aktif.'
        ) from exc
    return max(candidates, key=_ocr_text_quality)


def _ocr_text_quality(text: str) -> tuple[int, int, int]:
    course_rows = sum(
        _parse_course_line(line) is not None
        or _parse_uhamka_course_line(line) is not None
        or _parse_uhamka_histori_line(line) is not None
        for line in text.splitlines()
    )
    semester_markers = len(SEMESTER_MARKER.findall(text)) + len(ACADEMIC_TERM_MARKER.findall(text))
    readable_text = len(re.sub(r'[\W_]', '', text))
    return course_rows, semester_markers, readable_text


def parse_khs_images(contents: list[bytes]) -> dict:
    if not contents:
        raise ValueError('Unggah minimal satu gambar KHS.')
    text = '\n'.join(_extract_image_text(content) for content in contents)
    return _parse_khs_text(text, 'image')


def parse_khs_pdf(content: bytes) -> dict:
    if not content.startswith(b'%PDF-'):
        raise ValueError('File yang diunggah bukan PDF yang valid.')

    try:
        text = _extract_pdf_text(content)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            'PDF tidak dapat dibaca. Untuk PDF hasil scan, pastikan layanan OCR aktif atau unggah PDF yang teksnya dapat dipilih.'
        ) from exc

    return _parse_khs_text(text, 'pdf')


def _parse_khs_text(text: str, source_type: str) -> dict:
    metadata: dict[str, str | int | float | None] = {
        'nim': '',
        'full_name': '',
        'program_study': '',
        'current_semester': 0,
        'ipk': None,
    }
    semesters: dict[int, dict] = {}
    current_semester: int | None = None
    academic_years = [
        int(match.group('year'))
        for line in text.splitlines()
        if (match := ACADEMIC_TERM_MARKER.search(line))
    ]
    first_academic_year = min(academic_years) if academic_years else None
    program_value_lines_remaining = 0
    faculty_label_seen = False

    for raw_line in text.splitlines():
        line = ' '.join(raw_line.split()).strip()
        if not line:
            continue

        if program_value_lines_remaining:
            if line.startswith(':'):
                program_value_lines_remaining -= 1
                if program_value_lines_remaining == 0:
                    metadata['program_study'] = line[1:].strip()
                continue

        academic_term_match = ACADEMIC_TERM_MARKER.search(line)
        if academic_term_match and first_academic_year is not None:
            year = int(academic_term_match.group('year'))
            term_number = 1 if academic_term_match.group('term').casefold() == 'gasal' else 2
            current_semester = 2 * (year - first_academic_year) + term_number
            semesters.setdefault(
                current_semester,
                {'semester': current_semester, 'ip_semester': None, 'courses': []},
            )

        course_line = line[academic_term_match.end():].strip() if academic_term_match else line
        histori_course = _parse_uhamka_histori_line(course_line)
        if histori_course and current_semester is not None:
            histori_course['semester'] = current_semester
            semesters[current_semester]['courses'].append(histori_course)
            continue

        uhamka_course = _parse_uhamka_course_line(line)
        if uhamka_course:
            academic_year = uhamka_course.pop('academic_year')
            academic_term = uhamka_course.pop('academic_term')
            if academic_year is not None and first_academic_year is not None:
                term_number = 1 if academic_term == 'Gasal' else 2
                current_semester = 2 * (academic_year - first_academic_year) + term_number
            if current_semester is not None:
                uhamka_course['semester'] = current_semester
                semesters.setdefault(
                    current_semester,
                    {'semester': current_semester, 'ip_semester': None, 'courses': []},
                )
                semesters[current_semester]['courses'].append(uhamka_course)
            continue

        semester_match = SEMESTER_MARKER.search(line)
        if re.search(r'\bIP\s*Semester\b', line, re.IGNORECASE):
            semester_match = None
        if semester_match:
            current_semester = int(semester_match.group(1))
            if current_semester not in semesters:
                semesters[current_semester] = {'semester': current_semester, 'ip_semester': None, 'courses': []}

        nim_match = re.search(r'\bN\s*I\s*M\b\s*[:\-]?\s*(.+)$', line, re.IGNORECASE)
        if nim_match:
            nim_candidates = re.findall(r'[A-Z0-9./-]+', nim_match.group(1), re.IGNORECASE)
            if nim_candidates:
                metadata['nim'] = max(
                    nim_candidates,
                    key=lambda candidate: sum(character.isdigit() for character in candidate),
                ).strip()

        name_match = re.search(r'\bNama(?:\s+Mahasiswa)?\b\s*[:\-]\s*(.+?)(?=\s+(?:NIM|Program Studi)\b|$)', line, re.IGNORECASE)
        if name_match:
            metadata['full_name'] = name_match.group(1).strip()

        study_match = re.search(
            r'\b(?:Program Studi|Prog\.\s*Studi)\b\s*[:\-]\s*(.+)$',
            line,
            re.IGNORECASE,
        )
        if study_match:
            metadata['program_study'] = study_match.group(1).strip()
        elif re.fullmatch(r'Prog\.\s*Studi', line, re.IGNORECASE):
            program_value_lines_remaining = 2 if faculty_label_seen else 1
        elif line.casefold() == 'fakultas':
            faculty_label_seen = True

        ipk_match = re.search(r'\bIPK\b\s*[:\-]?\s*(\d(?:[.,]\d{1,2})?)', line, re.IGNORECASE)
        if ipk_match:
            metadata['ipk'] = float(ipk_match.group(1).replace(',', '.'))

        ip_semester_match = re.search(
            r'\bIP\s*(?:Semester|S)\b\s*[:\-]?\s*(\d(?:[.,]\d{1,2})?)',
            line,
            re.IGNORECASE,
        )
        if ip_semester_match and current_semester is not None:
            semesters[current_semester]['ip_semester'] = float(ip_semester_match.group(1).replace(',', '.'))

        course = _parse_course_line(line)
        if course and current_semester is not None:
            course['semester'] = current_semester
            semesters[current_semester]['courses'].append(course)

    semesters = {number: item for number, item in semesters.items() if item['courses']}
    if not semesters:
        if source_type == 'image':
            raise ValueError(
                'OCR belum menemukan baris mata kuliah. Foto harus tajam, tegak, menampilkan seluruh tabel, '
                'dan memuat kode, nama mata kuliah, SKS, serta nilai. Coba foto ulang dengan pencahayaan rata '
                'atau unggah setiap halaman KHS secara terpisah.'
            )
        raise ValueError(
            'Data mata kuliah per semester tidak ditemukan. Pastikan dokumen berisi judul semester serta baris Kode, Nama Mata Kuliah, SKS, dan Nilai yang terbaca jelas.'
        )

    metadata['current_semester'] = max(semesters)
    all_courses = [
        course for semester in semesters.values() for course in semester['courses']
    ]
    unique_courses, removed_count = deduplicate_course_entries(all_courses)
    courses_by_semester: dict[int, list[dict]] = {}
    for course in unique_courses:
        courses_by_semester.setdefault(course['semester'], []).append(course)
    for number, semester in semesters.items():
        semester['courses'] = courses_by_semester.get(number, [])

    warnings = []
    if removed_count:
        warnings.append(
            f'{removed_count} baris mata kuliah duplikat dihilangkan; '
            'nilai tertinggi untuk setiap kode dan semester dipertahankan.'
        )

    return {
        'metadata': metadata,
        'semesters': [semesters[number] for number in sorted(semesters)],
        'warnings': warnings,
        'source_type': source_type,
    }
