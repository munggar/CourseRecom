from io import BytesIO

import pytest
from PIL import Image

from app.services import khs_parser


def _png_bytes():
    image = Image.new('RGB', (100, 100), 'white')
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def test_parse_text_khs_extracts_metadata_and_each_semester(monkeypatch):
    text = """
    NIM: 2203001
    Nama Mahasiswa: Andi Pratama
    Program Studi: Teknik Informatika
    IPK: 3.45
    KHS Semester 1
    IP Semester: 3.50
    1 TI101 Algoritma Dasar 3 88 A
    KHS Semester 2
    IP Semester: 3.70
    TI201 Analisis Data 3 B 3.00
    """
    monkeypatch.setattr(khs_parser, '_extract_pdf_text', lambda _: text)

    parsed = khs_parser.parse_khs_pdf(b'%PDF-test')

    assert parsed['metadata'] == {
        'nim': '2203001',
        'full_name': 'Andi Pratama',
        'program_study': 'Teknik Informatika',
        'current_semester': 2,
        'ipk': 3.45,
    }
    assert [semester['semester'] for semester in parsed['semesters']] == [1, 2]
    assert parsed['semesters'][0]['ip_semester'] == 3.5
    assert parsed['semesters'][0]['courses'][0] == {
        'code': 'TI101',
        'name': 'Algoritma Dasar',
        'sks': 3,
        'grade': 'A',
        'numeric_grade': 88.0,
        'grade_point': 4.0,
        'semester': 1,
    }


def test_parse_rejects_non_pdf_and_pdf_without_semester_courses(monkeypatch):
    with pytest.raises(ValueError, match='bukan PDF'):
        khs_parser.parse_khs_pdf(b'not a pdf')

    monkeypatch.setattr(khs_parser, '_extract_pdf_text', lambda _: 'KHS semester 1\\nTidak ada tabel')
    with pytest.raises(ValueError, match='Data mata kuliah'):
        khs_parser.parse_khs_pdf(b'%PDF-empty')


def test_parse_uhamka_histori_nilai_uses_academic_terms_and_compact_columns(monkeypatch):
    text = """
    N I M : 2403045007
    Nama : MUNGGAR FAJAR MUHARRAM
    Fakultas
    Prog. Studi
    : Tekn. Industri & Informatika
    : Sistem dan Teknologi Informasi
    1 2 A2024/2025 Gasal 03045018 Algo. dan Dasar Pemrograman
    2 2 B03045022 Bahasa Indonesia
    11 2 B2024/2025 Genap 03045003 Akidah
    12 2 B03045013 Aljabar Linear
    21 2 D2025/2026 Gasal 03045006 Ibadah Akhlak
    31 3 A2025/2026 Genap 03045047 Analisis dan Perancangan Sistem Informasi
    """
    monkeypatch.setattr(khs_parser, '_extract_pdf_text', lambda _: text)

    parsed = khs_parser.parse_khs_pdf(b'%PDF-uhamka')

    assert parsed['metadata'] == {
        'nim': '2403045007',
        'full_name': 'MUNGGAR FAJAR MUHARRAM',
        'program_study': 'Sistem dan Teknologi Informasi',
        'current_semester': 4,
        'ipk': None,
    }
    assert [semester['semester'] for semester in parsed['semesters']] == [1, 2, 3, 4]
    assert [len(semester['courses']) for semester in parsed['semesters']] == [2, 2, 1, 1]
    assert parsed['semesters'][0]['courses'][0] == {
        'code': '03045018',
        'name': 'Algo. dan Dasar Pemrograman',
        'sks': 2,
        'grade': 'A',
        'numeric_grade': None,
        'grade_point': 4.0,
        'semester': 1,
    }
    assert parsed['semesters'][2]['courses'][0]['grade_point'] == 1.0


def test_parse_uhamka_photo_ocr_layout_groups_courses_by_academic_term():
    text = """
    UNIVERSITAS MUHAMMADIYAH PROF.DR.HAMKA
    HISTORI NILAI MAHASISWA
    NIM 1 2403045043
    Nama : ARYO DIMAS RUSDIANTORO
    Prog. Studi : Sistem dan Teknologi Informasi
    Th. Akademik -Semest NO MATAKULIAH SKS NILAI
    2024/2025 Gasal 1 03045018 Algo. dan Dasar Pemrograman 2 B
    2 03045022 Bahasa Indonesia 2 Cc
    2024/2025 Genap 11 03045003 Akidah 2 A
    12 03045013 Aljabar Linear 2 A
    2025/2026 Gasal 21 03045006 Ibadah Akhlak 2 B
    22 030450026 Jaringan Komp. & Kom.Data 3 A
    2025/2026 Genap 31 03045047 Analisis & Peranc. Sistem Info 3 B
    39 03045045 Sistem Terdistribusi 3 Cc
    """

    parsed = khs_parser._parse_khs_text(text, 'image')

    assert parsed['metadata']['nim'] == '2403045043'
    assert parsed['metadata']['current_semester'] == 4
    assert [semester['semester'] for semester in parsed['semesters']] == [1, 2, 3, 4]
    assert [len(semester['courses']) for semester in parsed['semesters']] == [2, 2, 2, 2]
    assert parsed['semesters'][0]['courses'][1]['grade'] == 'C'
    assert parsed['semesters'][2]['courses'][1]['code'] == '030450026'
    assert parsed['semesters'][3]['courses'][1]['grade'] == 'C'


def test_parse_khs_images_runs_ocr_and_combines_multiple_pages(monkeypatch):
    page_texts = [
        'NIM: 2203001\nNama Mahasiswa: Andi Pratama\nProgram Studi: Informatika\n'
        'KHS Semester 1\n1 03045018 Algo. dan Dasar Pemrograman 2 A',
        'KHS Semester 2\n2 03045022 Bahasa Indonesia 2 B',
    ]
    ocr_calls = []

    def fake_ocr(image, **options):
        ocr_calls.append((image.size, options))
        if options['config'] != '--oem 1 --psm 11':
            return 'Header Akademik tidak terbaca'
        page_index = (len(ocr_calls) - 1) // 4
        return page_texts[page_index]

    monkeypatch.setattr(khs_parser.pytesseract, 'image_to_string', fake_ocr)

    parsed = khs_parser.parse_khs_images([_png_bytes(), _png_bytes()])

    assert parsed['source_type'] == 'image'
    assert parsed['metadata']['current_semester'] == 2
    assert [semester['semester'] for semester in parsed['semesters']] == [1, 2]
    assert len(ocr_calls) == 8
    assert all(call[1]['lang'] == 'ind+eng' for call in ocr_calls)
    assert {call[1]['config'] for call in ocr_calls} == {
        '--oem 1 --psm 4',
        '--oem 1 --psm 6',
        '--oem 1 --psm 11',
    }
    assert parsed['semesters'][0]['courses'][0]['code'] == '03045018'
    assert parsed['semesters'][0]['courses'][0]['name'] == 'Algo. dan Dasar Pemrograman'


def test_generic_parser_accepts_numeric_course_code_layout():
    course = khs_parser._parse_course_line(
        '1 03045018 Algo. dan Dasar Pemrograman 2 A'
    )

    assert course == {
        'code': '03045018',
        'name': 'Algo. dan Dasar Pemrograman',
        'sks': 2,
        'grade': 'A',
        'numeric_grade': None,
        'grade_point': 4,
    }


def test_parser_keeps_different_course_codes_across_semesters():
    text = """
    KHS Semester 1
    1 TI101 Algoritma Dasar 3 C
    KHS Semester 2
    2 TI201 Algoritma-Dasar 3 A
    """

    parsed = khs_parser._parse_khs_text(text, 'pdf')

    assert parsed['metadata']['current_semester'] == 2
    assert [course['code'] for course in parsed['semesters'][0]['courses']] == ['TI101']
    assert [course['code'] for course in parsed['semesters'][1]['courses']] == ['TI201']
    assert parsed['semesters'][1]['courses'][0]['grade'] == 'A'
    assert parsed['warnings'] == []


def test_parser_keeps_same_course_code_in_different_semesters():
    text = """
    KHS Semester 1
    1 TI101 Algoritma Dasar 3 C
    KHS Semester 2
    2 TI101 Algoritma Dasar 3 B
    """

    parsed = khs_parser._parse_khs_text(text, 'pdf')

    assert parsed['metadata']['current_semester'] == 2
    assert [course['grade'] for course in parsed['semesters'][0]['courses']] == ['C']
    assert [course['grade'] for course in parsed['semesters'][1]['courses']] == ['B']
    assert parsed['warnings'] == []


def test_image_parser_returns_photo_specific_guidance_when_ocr_has_no_rows(monkeypatch):
    monkeypatch.setattr(
        khs_parser,
        '_extract_image_text',
        lambda _: 'KHS Semester 1\\nKode Mata Kuliah SKS Nilai',
    )

    with pytest.raises(ValueError, match='Foto harus tajam, tegak'):
        khs_parser.parse_khs_images([_png_bytes()])


def test_parse_khs_images_rejects_invalid_images():
    with pytest.raises(ValueError, match='Gambar tidak valid'):
        khs_parser.parse_khs_images([b'not an image'])
