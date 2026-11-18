"""FTII UHAMKA program-specific academic interest catalog.

Only STI labels are retained as the user's requested legacy choices. Other
programs are explicitly described as academic-interest areas unless a formal
specialization is confirmed by the program's published curriculum.
"""
PROGRAM_INTERESTS = {
    "Sistem dan Teknologi Informasi": {
        "kind": "Peminatan resmi program studi",
        "options": ["Manajemen Teknologi Informasi", "Kecerdasan Bisnis"],
        "note": "Mengikuti dua peminatan yang ditampilkan pada laman resmi Prodi STI UHAMKA. Label lama Manajemen Sistem Informasi diperlakukan sebagai data legacy.",
    },
    "Teknik Informatika": {
        "kind": "Arah minat berdasarkan profil lulusan",
        "options": [
            "Software Engineer",
            "Manajer Proyek TI",
            "Data Scientist",
            "Analisis dan Rekayasa Jaringan",
            "Perancangan UI/UX",
        ],
        "note": "Pilihan dirangkum dari profil lulusan dan capaian pembelajaran di laman resmi Prodi Teknik Informatika; bukan peminatan formal.",
    },
    "Teknik Mesin": {
        "kind": "Arah minat berdasarkan bidang keilmuan",
        "options": ["Manufaktur", "Energi dan Konversi Energi", "Material", "Sistem Mekanikal"],
        "note": "Dirangkum dari visi dan misi Prodi Teknik Mesin UHAMKA yang menyebut bidang manufaktur, energi, material, dan mekanikal; bukan klaim jalur peminatan formal.",
    },
    "Teknik Elektro": {
        "kind": "Spesialisasi bidang program studi",
        "options": ["Teknik Telekomunikasi"],
        "note": "Laman resmi Prodi Teknik Elektro menyebut spesialisasi bidang Teknik Telekomunikasi; tidak memecahnya menjadi subpeminatan yang belum terverifikasi.",
    },
    "Teknologi Rekayasa Mekatronika": {
        "kind": "Arah minat berdasarkan profil lulusan",
        "options": [
            "Pengembangan Robotika",
            "Pemeliharaan Industri",
            "Manajemen Proyek Mekatronika",
        ],
        "note": "Mengikuti tiga profil lulusan resmi TRM: Robotics Development Engineer, Industrial Maintenance Engineer, dan Mechatronics Project Manager; bukan peminatan formal.",
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
