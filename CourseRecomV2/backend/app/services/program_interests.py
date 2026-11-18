"""FTII UHAMKA program-specific academic interest catalog.

Only STI labels are retained as the user's requested legacy choices. Other
programs are explicitly described as academic-interest areas unless a formal
specialization is confirmed by the program's published curriculum.
"""
PROGRAM_INTERESTS = {
    "Sistem dan Teknologi Informasi": {
        "kind": "Peminatan program studi",
        "options": ["Manajemen Sistem Informasi", "Kecerdasan Bisnis"],
        "note": "Pilihan mengikuti struktur peminatan yang telah digunakan pada data STI CourseRecom.",
    },
    "Teknik Informatika": {
        "kind": "Bidang minat akademik",
        "options": ["Software Engineering", "Data Science", "Jaringan Komputer", "UI/UX"],
        "note": "Bidang minat akademik berdasarkan profil kompetensi lulusan; bukan klaim peminatan formal.",
    },
    "Teknik Mesin": {
        "kind": "Peminatan program studi",
        "options": ["Manufaktur", "Konversi Energi"],
        "note": "Bidang peminatan yang tercantum pada informasi program studi.",
    },
    "Teknik Elektro": {
        "kind": "Bidang minat akademik",
        "options": [
            "Telekomunikasi - Satelit",
            "Telekomunikasi - Optik",
            "Telekomunikasi - Nirkabel dan Antena",
            "Industri Cerdas",
        ],
        "note": "Bidang akademik/spesialisasi; konfirmasi ke prodi untuk penamaan kurikulum resmi.",
    },
    "Teknologi Rekayasa Mekatronika": {
        "kind": "Bidang minat akademik",
        "options": [
            "Robotika",
            "Otomasi Industri",
            "Pemeliharaan Industri",
            "Manajemen Proyek Mekatronika",
        ],
        "note": "Bidang minat berdasarkan profil kompetensi lulusan; bukan klaim peminatan formal.",
    },
}


def get_program_interest_catalog():
    return PROGRAM_INTERESTS


def normalize_program_name(value: str) -> str:
    normalized = " ".join((value or "").strip().lower().split())
    aliases = {
        "sti": "Sistem dan Teknologi Informasi",
        "sistem informasi": "Sistem dan Teknologi Informasi",
        "sistem dan teknologi informasi": "Sistem dan Teknologi Informasi",
        "ti": "Teknik Informatika",
        "teknik informatika": "Teknik Informatika",
        "teknik mesin": "Teknik Mesin",
        "teknik elektro": "Teknik Elektro",
        "trm": "Teknologi Rekayasa Mekatronika",
        "teknologi rekayasa mekatronika": "Teknologi Rekayasa Mekatronika",
    }
    return aliases.get(normalized, "")


def validate_program_interest(program_study: str, interest: str) -> tuple[str, str]:
    program = normalize_program_name(program_study)
    if not program:
        raise ValueError("Pilih salah satu program studi FTII UHAMKA.")
    option = (interest or "").strip()
    if option not in PROGRAM_INTERESTS[program]["options"]:
        raise ValueError("Bidang minat tidak sesuai dengan program studi yang dipilih.")
    return program, option
