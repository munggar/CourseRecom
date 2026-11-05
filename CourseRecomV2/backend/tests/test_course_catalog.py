from io import BytesIO

from openpyxl import Workbook

from app.services.course_catalog import parse_course_catalog


def test_xlsx_catalog_maps_indonesian_columns_prerequisites_and_repeated_semesters():
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(['semester', 'kode_mk', 'nama_mk', 'kategori', 'sks', 'Mata Kuliah Prasyarat', 'Keterangan / Catatan'])
    worksheet.append(['Semester 1', 'TI001', 'Algoritma Dasar', 'Komputasi', 3, 'Tidak Ada', 'Wajib Semester 1'])
    worksheet.append(['Semester 3', 'TI002', 'Struktur Data', 'Komputasi', 2, 'Algoritma Dasar', 'Wajib Semester 3'])
    worksheet.append(['Semester 5', 'TI003', 'Komunikasi', 'Umum', 2, 'Tidak Ada', 'Dapat diambil'])
    worksheet.append(['Semester 3', 'TI003', 'Komunikasi', 'Pilihan', 2, 'Tidak Ada', 'Dapat diambil'])
    content = BytesIO()
    workbook.save(content)

    courses, replaces_catalog = parse_course_catalog(content.getvalue(), 'kurikulum.xlsx')

    assert replaces_catalog is True
    assert len(courses) == 3
    data_structures = next(course for course in courses if course['code'] == 'TI002')
    assert data_structures['prerequisite_text'] == 'Algoritma Dasar'
    assert data_structures['prerequisite_codes'] == 'TI001'
    communication = next(course for course in courses if course['code'] == 'TI003')
    assert communication['semester'] == 3
    assert communication['available_semesters'] == '3,5'
    assert communication['category'] == 'Pilihan'
    assert communication['description'] == 'Dapat diambil'


def test_csv_catalog_import_keeps_merge_behavior():
    content = (
        'code,name,sks,semester,category,description,prerequisite_codes\n'
        'TI001,Algoritma Dasar,3,1,Komputasi,Wajib,\n'
    ).encode()

    courses, replaces_catalog = parse_course_catalog(content, 'kurikulum.csv')

    assert replaces_catalog is False
    assert courses[0]['code'] == 'TI001'
    assert courses[0]['available_semesters'] == '1'
