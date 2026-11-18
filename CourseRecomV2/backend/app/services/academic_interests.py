"""Program study and interest catalog for FTII UHAMKA.

Official concentration names are distinguished from broader academic-interest areas.
The latter are recommendation preferences, not claims of an officially approved track.
"""

import re


PROGRAMS = [
    {
        'value': 'Sistem dan Teknologi Informasi',
        'aliases': ['STI', 'Sistem Teknologi Informasi', 'Sistem Informasi'],
        'interest_type': 'peminatan_prodi',
        'interest_note': (
            'Halaman resmi STI menyebut Kecerdasan Bisnis (KB) dan '
            'Manajemen Teknologi Informasi (MTI). Pilihan Manajemen Sistem Informasi '
            'dipertahankan sebagai label aplikasi yang sudah digunakan mahasiswa.'
        ),
        'interests': [
            {
                'value': 'Manajemen Sistem Informasi',
                'label': 'Manajemen Sistem Informasi',
                'official_label': 'Manajemen Teknologi Informasi (MTI)',
                'description': 'Tata kelola SI/TI, layanan TI organisasi, proses bisnis, analisis sistem, dan manajemen proyek TI.',
                'aliases': ['Manajemen Teknologi Informasi', 'MTI', 'MSI'],
            },
            {
                'value': 'Kecerdasan Bisnis',
                'label': 'Kecerdasan Bisnis',
                'official_label': 'Kecerdasan Bisnis (KB)',
                'description': 'Business intelligence, analitik data, dashboard, data mining, dan dukungan keputusan.',
                'aliases': ['KB', 'Business Intelligence'],
            },
        ],
    },
    {
        'value': 'Teknik Informatika',
        'aliases': ['TI', 'Informatika', 'Teknik Informatika S1', 'S1 Teknik Informatika'],
        'interest_type': 'bidang_minat_akademik',
        'interest_note': (
            'Situs prodi menampilkan profil lulusan Software Engineer, Manajer Proyek, '
            'Data Saintis, Analis/Perekayasa Jaringan, dan Perancang UI/UX. '
            'Pilihan di bawah adalah bidang minat rekomendasi, bukan klaim jalur peminatan resmi.'
        ),
        'interests': [
            {
                'value': 'Rekayasa Perangkat Lunak',
                'label': 'Rekayasa Perangkat Lunak',
                'description': 'Analisis kebutuhan, desain, pengembangan, pengujian, dan pemeliharaan aplikasi.',
                'aliases': ['Software Engineering', 'Software Engineer'],
            },
            {
                'value': 'Data Science dan Kecerdasan Buatan',
                'label': 'Data Science dan Kecerdasan Buatan',
                'description': 'Pengolahan data, algoritma, machine learning, dan penerapan kecerdasan buatan.',
                'aliases': ['Data Science', 'Data Scientist', 'Artificial Intelligence', 'AI/ML'],
            },
            {
                'value': 'Jaringan Komputer',
                'label': 'Jaringan Komputer',
                'description': 'Perancangan, administrasi, analisis, dan pemeliharaan jaringan komputer.',
                'aliases': ['Networking', 'Network Engineer'],
            },
            {
                'value': 'UI/UX dan Komputasi Visual',
                'label': 'UI/UX dan Komputasi Visual',
                'description': 'Perancangan pengalaman pengguna, antarmuka, interaksi, dan visual computing.',
                'aliases': ['UI/UX', 'User Interface', 'Visual Computing', 'Grafik dan Visual'],
            },
            {
                'value': 'Manajemen Proyek Teknologi Informasi',
                'label': 'Manajemen Proyek Teknologi Informasi',
                'description': 'Perencanaan, koordinasi tim, pengendalian, dan evaluasi proyek teknologi informasi.',
                'aliases': ['Manajemen Proyek TI', 'IT Project Management'],
            },
        ],
    },
    {
        'value': 'Teknik Mesin',
        'aliases': ['TM', 'Mesin', 'Teknik Mesin S1', 'S1 Teknik Mesin'],
        'interest_type': 'peminatan_prodi',
        'interest_note': 'Panduan kurikulum Teknik Mesin menyebut peminatan Manufaktur dan Konversi Energi.',
        'interests': [
            {
                'value': 'Manufaktur',
                'label': 'Manufaktur',
                'description': 'Desain produk, proses produksi, material, pengecoran, pengelasan, otomasi, dan sistem produksi.',
                'aliases': ['Manufacturing'],
            },
            {
                'value': 'Konversi Energi',
                'label': 'Konversi Energi',
                'description': 'Mesin konversi energi, termal, fluida, performa mesin, dan sistem energi.',
                'aliases': ['Energy Conversion'],
            },
        ],
    },
    {
        'value': 'Teknik Elektro',
        'aliases': ['TE', 'Elektro', 'Teknik Elektro S1', 'S1 Teknik Elektro'],
        'interest_type': 'bidang_spesialisasi_prodi',
        'interest_note': (
            'Situs Teknik Elektro menyebut spesialisasi telekomunikasi dan kelompok '
            'kepakaran riset: satelit, optik, nirkabel/antena, serta industri cerdas. '
            'Pilihan mengikuti bidang spesialisasi/kelompok kepakaran tersebut.'
        ),
        'interests': [
            {
                'value': 'Telekomunikasi Satelit',
                'label': 'Telekomunikasi Satelit',
                'description': 'Sistem komunikasi satelit, antena, link budget, dan aplikasi komunikasi satelit.',
                'aliases': ['Satellite Telecommunications'],
            },
            {
                'value': 'Telekomunikasi Optik',
                'label': 'Telekomunikasi Optik',
                'description': 'Serat optik, sistem komunikasi optik, transmisi, dan jaringan optik.',
                'aliases': ['Optical Telecommunications', 'Fiber Optic'],
            },
            {
                'value': 'Telekomunikasi Nirkabel dan Antena',
                'label': 'Telekomunikasi Nirkabel dan Antena',
                'description': 'Komunikasi nirkabel, antena, propagasi gelombang, dan sistem RF.',
                'aliases': ['Wireless Telecommunications', 'Antena', 'Nirkabel'],
            },
            {
                'value': 'Industri Cerdas',
                'label': 'Industri Cerdas',
                'description': 'Sistem industri cerdas, otomasi, sensor, instrumentasi, dan integrasi sistem.',
                'aliases': ['Smart Industry', 'Industrial Intelligence'],
            },
        ],
    },
    {
        'value': 'Teknologi Rekayasa Mekatronika',
        'aliases': ['TRM', 'Mekatronika', 'Teknologi Rekayasa Mekatronika D4', 'D4 Mekatronika'],
        'interest_type': 'bidang_minat_akademik',
        'interest_note': (
            'Profil lulusan prodi menampilkan Robotics Development Engineer, '
            'Industrial Maintenance Engineer, dan Mechatronics Project Manager. '
            'Pilihan di bawah adalah bidang minat berdasarkan profil lulusan, bukan klaim jalur peminatan resmi.'
        ),
        'interests': [
            {
                'value': 'Pengembangan Robotika',
                'label': 'Pengembangan Robotika',
                'description': 'Robotika, sistem kendali, aktuator, sensor, dan integrasi perangkat keras-perangkat lunak.',
                'aliases': ['Robotics', 'Robot Development'],
            },
            {
                'value': 'Pemeliharaan Sistem Industri',
                'label': 'Pemeliharaan Sistem Industri',
                'description': 'Perawatan, diagnosis gangguan, instrumentasi, dan keandalan sistem mekatronika industri.',
                'aliases': ['Industrial Maintenance', 'Maintenance Engineering'],
            },
            {
                'value': 'Manajemen Proyek Mekatronika',
                'label': 'Manajemen Proyek Mekatronika',
                'description': 'Perencanaan, pelaksanaan, pengujian, dan evaluasi proyek sistem mekatronika.',
                'aliases': ['Mechatronics Project Management'],
            },
        ],
    },
]


def _normalize(value: str | None) -> str:
    return re.sub(r'[\W_]+', ' ', str(value or '').casefold()).strip()


def program_by_value(program_study: str | None) -> dict | None:
    normalized = _normalize(program_study)
    if not normalized:
        return None
    for program in PROGRAMS:
        if normalized == _normalize(program['value']) or normalized in {
            _normalize(alias) for alias in program['aliases']
        }:
            return program
    return None


def canonical_program_study(program_study: str | None) -> str | None:
    program = program_by_value(program_study)
    return program['value'] if program else None


def interests_for_program(program_study: str | None) -> list[dict]:
    program = program_by_value(program_study)
    return list(program['interests']) if program else []


def canonical_interest(program_study: str | None, interest: str | None) -> str | None:
    program = program_by_value(program_study)
    normalized = _normalize(interest)
    if not program or not normalized:
        return None
    for option in program['interests']:
        accepted = {option['value'], option['label'], *option.get('aliases', [])}
        if normalized in {_normalize(item) for item in accepted}:
            return option['value']
    return None


def validate_student_program_and_interest(program_study: str, interest: str) -> tuple[str, str]:
    program = canonical_program_study(program_study)
    if not program:
        raise ValueError('Pilih salah satu Program Studi FTII UHAMKA yang tersedia.')
    selected_interest = canonical_interest(program, interest)
    if not selected_interest:
        raise ValueError('Pilih bidang minat yang sesuai dengan Program Studi.')
    return program, selected_interest


def public_catalog() -> dict:
    return {
        'faculty': 'Fakultas Teknologi Industri dan Informatika UHAMKA',
        'programs': [
            {
                'value': program['value'],
                'aliases': program['aliases'],
                'interest_type': program['interest_type'],
                'interest_note': program['interest_note'],
                'interests': [
                    {
                        key: value for key, value in option.items()
                        if key != 'aliases'
                    }
                    for option in program['interests']
                ],
            }
            for program in PROGRAMS
        ],
    }
