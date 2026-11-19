"""Seed verified Gasal 2026/2027 KRS room, course and lecturer schedule data.

Revision ID: 20261118_05
Revises: 20261118_04
Create Date: 2026-11-19
"""
from datetime import datetime
import sqlalchemy as sa
from alembic import op

revision = '20261118_05'
down_revision = '20261118_04'
branch_labels = None
depends_on = None

KRS_SOURCE = 'https://akademik.uhamka.ac.id/student/course-plan'
ROOM_ARCHIVE = 'https://ft.uhamka.ac.id/wp-content/uploads/2023/10/Jadwal-Blended-Learning-FTII-UHAMKA-Gasal-2023-2024-Rev2.pdf'
PROFILE_STI = 'https://ft.uhamka.ac.id/dosen-sti/'
PROFILE_TI = 'https://ft.uhamka.ac.id/dosen-ti/'
PROFILE_TM = 'https://ft.uhamka.ac.id/dosen-teknik-mesin/'
PROFILE_TRM = 'https://ft.uhamka.ac.id/dosen-rekayasa-teknologi-mekatronika/'
PROFILE_ELECTRO = 'https://ft.uhamka.ac.id/prodi/elektro/'

# Names not in the first FTII directory seed are included only where the
# student KRS samples or an institutional/public profile provide evidence.
EXTRA_LECTURERS = [
    {
        'nidn': '0318087001',
        'name': 'Rita Agustina Karnawati, S.Pd., M.Pd., Dr.',
        'program': 'Pendidikan Bahasa Jepang (FKIP UHAMKA)',
        'education': 'S1 Pendidikan Bahasa Jepang, IKIP Surabaya; S2 Pendidikan Bahasa Jepang, UPI Bandung; biodata 2021 mencatat pendidikan doktoral sedang ditempuh',
        'expertise': 'Pendidikan Bahasa Jepang; pembelajaran bahasa Jepang; tracer study lulusan',
        'email': 'rita.agustina.karnawati@uhamka.ac.id',
        'url': 'https://journal.uhamka.ac.id/index.php/taiyou/article/download/10453/3309/30082',
        'notes': 'NIDN tercantum pada biodata tim pengabdian UHAMKA tahun 2021. KRS contoh 19 November 2026 menampilkan dosen ini pada Keterampilan Berbahasa Jepang. Jabatan/gelar perlu dicocokkan ke data kepegawaian terbaru.',
        'type': 'official_uhamka_publication',
    },
    {
        'nidn': None,
        'name': 'Yuni Masrokhah, S.Pd., M.Hum.',
        'program': 'Pendidikan Bahasa Jepang (FKIP UHAMKA)',
        'education': 'Pendidikan Bahasa Jepang; gelar S.Pd., M.Hum. tercantum pada dokumen KRS',
        'expertise': 'Pendidikan dan pembelajaran Bahasa Jepang',
        'email': 'yuni_masrokhah@uhamka.ac.id',
        'url': 'https://journal.uhamka.ac.id/index.php/taiyou/article/download/10453/3309/30082',
        'notes': 'Dikonfirmasi sebagai penulis/afiliasi UHAMKA pada Jurnal Taiyou dan muncul pada KRS contoh 19 November 2026. NIDN tidak dimasukkan karena belum ditemukan pada sumber resmi yang dapat dipastikan.',
        'type': 'official_uhamka_publication',
    },
    {
        'nidn': '0330097402',
        'name': 'Emilia Roza, S.T., M.Pd., M.T.',
        'program': 'Teknik Elektro (FTII UHAMKA)',
        'education': 'S1 Teknik Elektro, Universitas Mercu Buana (1993–1998); gelar S.T., M.Pd., M.T. tercantum pada sumber UHAMKA',
        'expertise': 'Telekomunikasi nirkabel; antena; teknik elektro',
        'email': 'emilia_roza@uhamka.ac.id',
        'url': 'https://ft.uhamka.ac.id/telekomunikasi-nirkabel-dan-antena/',
        'notes': 'NIDN 0330097402 tercantum pada dokumen skripsi repositori UHAMKA; profil KK FTII mencantumkan Emilia Roza sebagai anggota kelompok Telekomunikasi Nirkabel dan Antena. KRS contoh 19 November 2026 mencantumkan dosen ini untuk Pengembangan Talenta.',
        'type': 'official_ftii_profile',
    },
    {
        'nidn': '0325117707',
        'name': 'Adityo Ari Wibowo, S.E., M.M.',
        'program': 'Manajemen (FEB UHAMKA) / pengampu lintas fakultas',
        'education': 'S2; dokumen daftar mengajar UHAMKA 2022/2023 mencantumkan pendidikan terakhir S2',
        'expertise': 'Manajemen; kewirausahaan; pengajaran mata kuliah manajemen',
        'email': None,
        'url': 'https://conferences.uhamka.ac.id/uhamka/paper/view/240',
        'notes': 'NIDN 0325117707 dan NIRD D150942 tercantum pada salinan daftar mengajar UHAMKA semester Genap 2022/2023. KRS contoh 19 November 2026 mencantumkan nama ini untuk Kewirausahaan kelas 7B. Profil homebase harus diverifikasi oleh Admin.',
        'type': 'official_uhamka_record',
    },
    {
        'nidn': None,
        'name': 'Margiono, Drs.',
        'program': 'Pengampu MKWU / lintas program studi',
        'education': 'Gelar Drs. tercantum pada KRS contoh',
        'expertise': None,
        'email': None,
        'url': KRS_SOURCE,
        'notes': 'Nama dan gelar hanya ditemukan pada KRS contoh mahasiswa bertanggal 19 November 2026 untuk Kemuhammadiyahan kelas 5B. NIDN, homebase, dan profil publik belum ditemukan; jangan dipadankan dengan orang lain tanpa verifikasi.',
        'type': 'student_krs_sample',
    },
    {
        'nidn': None,
        'name': 'Ridwan Abd.Salam, Drs., M.M.',
        'program': 'Pengampu MKWU / lintas program studi',
        'education': 'Gelar Drs., M.M. tercantum pada KRS contoh',
        'expertise': None,
        'email': None,
        'url': KRS_SOURCE,
        'notes': 'Nama dan gelar tercantum pada KRS contoh 19 November 2026 untuk Kemuhammadiyahan kelas 5A. NIDN dan homebase belum ditemukan pada sumber publik yang dapat dipastikan.',
        'type': 'student_krs_sample',
    },
]

# Enrichment courses are catalog entries with a default class/teacher but
# no timetable on the supplied KRS examples. They must not be given a fake
# date, time or room; those fields stay empty until an official timetable exists.
COURSES = [
    ('03045008', 'Kemuhammadiyahan', 2, 5, 'MKWU / AIK', '5', None, None, 'Contoh KRS 19 November 2026: kelas 5A dan 5B.'),
    ('03045104', 'Keterampilan Berbicara Bahasa Jepang', 2, 5, 'Pengayaan / Bahasa', '5', None, None, 'Contoh KRS 19 November 2026: kelas 5A.'),
    ('03045097', 'Keterampilan Berbahasa Jepang', 2, 5, 'Pengayaan / Bahasa', '5', None, None, 'Contoh KRS 19 November 2026: kelas 5A.'),
    ('03045016', 'Manajemen Proyek dan Perubahan', 3, 5, 'Manajemen & Sistem Informasi', '5', None, None, 'Contoh KRS 19 November 2026: kelas 5A.'),
    ('03045051', 'Mobile Application', 2, 5, 'Inti Teknologi & Pemrograman', '5', None, None, 'Contoh KRS 19 November 2026: kelas 5A.'),
    ('03045050', 'Pengembangan Sistem Informasi Manajemen', 3, 5, 'Manajemen & Sistem Informasi', '5', None, None, 'Contoh KRS 19 November 2026: kelas 5A dan 5B.'),
    ('03045053', 'Perancangan Infrastruktur Teknologi Informasi', 2, 5, 'Inti Teknologi & Pemrograman', '5', None, None, 'Contoh KRS 19 November 2026: kelas 5A.'),
    ('03045052', 'Praktikum Mobile Application', 1, 5, 'Inti Teknologi & Pemrograman', '5', None, None, 'KRS 19 November 2026 mencatat FTTI2; KRS 15 September 2026 sebelumnya menggunakan FTTI1.'),
    ('03035975', 'Keterampilan Retorika dan Presentasi Publik', 2, 7, 'Pengayaan', '7', '7P', None, 'KRS Arifan Fadli 19 November 2026 lists Firman Noor Hasan; an earlier KRS for Adil Muslim Saputra lists Faldy Irwiensyah for the same course code. Teacher assignment remains unverified; no schedule, room or time supplied.'),
    ('03035989', 'Kewirausahaan Terstruktur', 3, 7, 'Pengayaan / Kewirausahaan', '7', '7P', 'Faldy Irwiensyah, S.Kom., M.TI.', 'KRS examples list 7P and Faldy Irwiensyah; no day, time or room is supplied.'),
    ('03035984', 'Pengembangan Profesi', 2, 7, 'Pengayaan', '7', '7P', 'Yos Nofendri, S.Pd., M.Sc. Eng.', 'KRS examples list 7P and Yos Nofendri; no day, time or room is supplied.'),
    ('03035983', 'Pengembangan Talenta', 3, 7, 'Pengayaan', '7', '7P', 'Emilia Roza, S.T., M.Pd., M.T.', 'Latest KRS screenshot 19 November 2026 lists 7P and Emilia Roza; no day, time or room is supplied.'),
    ('03045037', 'Kewirausahaan', 3, 7, 'Kewirausahaan', '7', None, None, 'KRS example 19 November 2026 lists class 7B, Tuesday 13:00–15:30, room FT403, lecturer Adityo Ari Wibowo.'),
]

# Time windows and room/lecturer assignments are transcribed from the
# 19 November 2026 screenshot and the 19 November 2026 two-page SIAKAD PDF.
# KRS times match SKS x 50 minutes. The 15 September 2026 PDF used FTTI1 for
# Praktikum Mobile Application; the newer 19 November sources use FTTI2.
SCHEDULES = [
    ('03045008', '5A', 5, 'Ridwan Abd.Salam, Drs., M.M.', None, 'FT403', 'Kamis', '10:20', '12:00'),
    ('03045008', '5B', 5, 'Margiono, Drs.', None, 'FT302', 'Jumat', '07:50', '09:30'),
    ('03045104', '5A', 5, 'Yuni Masrokhah, S.Pd., M.Hum.', None, 'FT302', 'Kamis', '14:40', '16:20'),
    ('03045097', '5A', 5, 'Rita Agustina Karnawati, Dr., M.Pd.', None, 'FT401', 'Kamis', '07:50', '09:30'),
    ('03045037', '7B', 7, 'Adityo Ari Wibowo, Dr., S.E., M.M.', None, 'FT403', 'Selasa', '13:00', '15:30'),
    ('03045016', '5A', 5, 'Muhammad Givi Efgivia, Dr., Ir., M.Kom.', '0305046403', 'FT401', 'Selasa', '15:30', '18:00'),
    ('03045051', '5A', 5, 'Akhmad Rizal Dzikrillah, S.T., M.TI.', None, 'FTTI2', 'Senin', '13:00', '14:40'),
    ('03045050', '5A', 5, 'Tirta Anhari, S.T., M.Kom.', None, 'FT303', 'Rabu', '07:50', '10:20'),
    ('03045050', '5B', 5, 'E. Rizal, S.Kom., M.Kom.', '03020226504', 'FT301', 'Selasa', '09:30', '12:00'),
    ('03045053', '5A', 5, 'Isa Faqihuddin Hanif, M.Kom.', '0316099202', 'FT404', 'Senin', '10:20', '12:00'),
    ('03045052', '5A', 5, 'Akhmad Rizal Dzikrillah, S.T., M.TI.', None, 'FTTI2', 'Senin', '14:40', '15:30'),
]

def _table(bind, name):
    return sa.table(name, *[
        sa.column('code', sa.String(20)),
    ])

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # SQLite needs a batch table rebuild to make the previously required
    # room floor nullable; Postgres can ALTER the column directly.
    if 'rooms' in tables:
        if bind.dialect.name == 'sqlite':
            with op.batch_alter_table('rooms') as batch:
                batch.alter_column('floor', existing_type=sa.Integer(), nullable=True)
        else:
            op.alter_column('rooms', 'floor', existing_type=sa.Integer(), nullable=True)

    if 'course_classes' in tables:
        class_columns = {column['name'] for column in sa.inspect(bind).get_columns('course_classes')}
        if 'lecturer_name' not in class_columns:
            op.add_column('course_classes', sa.Column('lecturer_name', sa.String(180), nullable=True))

    if 'courses' in tables:
        course_columns = {column['name'] for column in sa.inspect(bind).get_columns('courses')}
        if 'default_class_name' not in course_columns:
            op.add_column('courses', sa.Column('default_class_name', sa.String(40), nullable=True))
        if 'default_lecturer_name' not in course_columns:
            op.add_column('courses', sa.Column('default_lecturer_name', sa.String(180), nullable=True))

    now = datetime.utcnow()

    room_table = sa.table(
        'rooms',
        sa.column('code', sa.String(10)),
        sa.column('floor', sa.Integer),
        sa.column('room_number', sa.String(3)),
        sa.column('capacity', sa.Integer),
        sa.column('room_type', sa.String(40)),
        sa.column('is_active', sa.Boolean),
        sa.column('source_status', sa.String(60)),
        sa.column('source_url', sa.String(500)),
        sa.column('notes', sa.Text),
        sa.column('verified_at', sa.DateTime),
        sa.column('created_at', sa.DateTime),
    )
    for code, floor, number in [
        ('FT301',3,'01'),('FT302',3,'02'),('FT303',3,'03'),('FT304',3,'04'),('FT305',3,'05'),
        ('FT401',4,'01'),('FT402',4,'02'),('FT403',4,'03'),('FT404',4,'04'),('FT405',4,'05'),('FT406',4,'06'),
    ]:
        bind.execute(room_table.update().where(room_table.c.code == code).values(
            capacity=35,
            is_active=True,
            source_status='user_confirmed_2026_11',
            source_url=ROOM_ARCHIVE,
            notes='Pengguna mengonfirmasi ruang masih ada/digunakan; kapasitas awal ditetapkan 35 kursi berdasarkan perkiraan 30–35 orang. Ini nilai kerja sementara yang dapat dikoreksi Admin setelah pengukuran fisik. Kode ruang ditemukan pada arsip jadwal FTII 2023/2024.',
            verified_at=now,
        ))

    for code, floor, number, room_type, source_notes in [
        ('FTTI1', None, '1', 'Laboratorium', 'Kode laboratorium FTTI1 tercantum pada KRS SIAKAD UHAMKA bertanggal 15 September 2026 untuk Praktikum Mobile Application. KRS terbaru 19 November 2026 memakai FTTI2 untuk mata kuliah yang sama; catatan historis dipertahankan.'),
        ('FTTI2', None, '2', 'Laboratorium', 'Kode laboratorium FTTI2 tercantum pada screenshot/PDF KRS SIAKAD UHAMKA bertanggal 19 November 2026 untuk Mobile Application dan Praktikum Mobile Application.'),
    ]:
        existing = bind.execute(sa.select(room_table.c.code).where(room_table.c.code == code)).first()
        if existing:
            bind.execute(room_table.update().where(room_table.c.code == code).values(
                floor=None, room_number=number, capacity=35, room_type=room_type,
                is_active=True, source_status='user_confirmed_krs_2026_11',
                source_url=KRS_SOURCE,
                notes=f'{source_notes} Kapasitas awal 35 kursi mengikuti perkiraan pengguna 30–35 orang dan tetap dapat disunting Admin.',
                verified_at=now,
            ))
        else:
            bind.execute(room_table.insert().values(
                code=code, floor=None, room_number=number, capacity=35,
                room_type=room_type, is_active=True,
                source_status='user_confirmed_krs_2026_11',
                source_url=KRS_SOURCE,
                notes=f'{source_notes} Kapasitas awal 35 kursi mengikuti perkiraan pengguna 30–35 orang dan tetap dapat disunting Admin.',
                verified_at=now,
                created_at=now,
            ))

    # Enrich existing rows and create the five additional course codes from
    # the KRS examples. Keep the supplied course codes exactly as printed.
    course_table = sa.table(
        'courses',
        sa.column('code', sa.String(20)),
        sa.column('name', sa.String(120)),
        sa.column('sks', sa.Integer),
        sa.column('semester', sa.Integer),
        sa.column('available_semesters', sa.String(40)),
        sa.column('category', sa.String(60)),
        sa.column('description', sa.Text),
        sa.column('capacity', sa.Integer),
        sa.column('prerequisite_codes', sa.String(255)),
        sa.column('is_active', sa.Boolean),
        sa.column('default_class_name', sa.String(40)),
        sa.column('default_lecturer_name', sa.String(180)),
    )
    for code, name, sks, semester, category, available, class_name, lecturer_name, description in COURSES:
        if bind.execute(sa.select(course_table.c.code).where(course_table.c.code == code)).first():
            bind.execute(course_table.update().where(course_table.c.code == code).values(
                name=name, sks=sks, semester=semester, available_semesters=available,
                category=category, is_active=True,
                default_class_name=class_name,
                default_lecturer_name=lecturer_name,
                description=description,
            ))
        else:
            bind.execute(course_table.insert().values(
                code=code, name=name, sks=sks, semester=semester,
                available_semesters=available, category=category,
                description=description, capacity=35, is_active=True,
                prerequisite_codes='',
                default_class_name=class_name,
                default_lecturer_name=lecturer_name,
            ))

    # Existing course capacities are intentionally preserved; each scheduled class
    # receives its own 35-seat cap, constrained by the assigned room.

    if 'lecturer_directory' in tables:
        directory = sa.table(
            'lecturer_directory',
            sa.column('id', sa.Integer),
            sa.column('nidn', sa.String(30)),
            sa.column('full_name', sa.String(180)),
            sa.column('program_study', sa.String(120)),
            sa.column('email', sa.String(120)),
            sa.column('education', sa.Text),
            sa.column('expertise', sa.Text),
            sa.column('source_type', sa.String(60)),
            sa.column('profile_url', sa.String(500)),
            sa.column('notes', sa.Text),
        )
        for entry in EXTRA_LECTURERS:
            exists = None
            if entry['nidn']:
                exists = bind.execute(sa.select(directory.c.id).where(directory.c.nidn == entry['nidn'])).first()
            if not exists:
                exists = bind.execute(sa.select(directory.c.id).where(
                    sa.func.lower(directory.c.full_name) == entry['name'].casefold()
                )).first()
            if exists:
                continue
            bind.execute(directory.insert().values(
                nidn=entry['nidn'],
                full_name=entry['name'],
                program_study=entry['program'],
                email=entry['email'],
                education=entry['education'],
                expertise=entry['expertise'],
                source_type=entry['type'],
                profile_url=entry['url'],
                notes=entry['notes'],
            ))

    if 'course_classes' in tables:
        class_table = sa.table(
            'course_classes',
            sa.column('id', sa.Integer),
            sa.column('course_code', sa.String(20)),
            sa.column('class_name', sa.String(40)),
            sa.column('lecturer_id', sa.Integer),
            sa.column('lecturer_name', sa.String(180)),
            sa.column('room', sa.String(40)),
            sa.column('day', sa.String(20)),
            sa.column('start_time', sa.String(5)),
            sa.column('end_time', sa.String(5)),
            sa.column('capacity', sa.Integer),
            sa.column('semester', sa.String(20)),
            sa.column('is_open', sa.Boolean),
        )
        users = sa.table('users',
            sa.column('id', sa.Integer), sa.column('nim', sa.String(20)),
            sa.column('full_name', sa.String(120)), sa.column('role', sa.String(20)))
        for code, class_name, semester, lecturer_display, lecturer_nim, room, day, start_time, end_time in SCHEDULES:
            existing = bind.execute(sa.select(class_table.c.id).where(sa.and_(
                class_table.c.course_code == code,
                class_table.c.class_name == class_name,
                class_table.c.semester == str(semester),
            ))).first()
            if existing:
                continue
            linked_id = None
            if lecturer_nim:
                linked_id = bind.execute(sa.select(users.c.id).where(
                    sa.and_(users.c.nim == lecturer_nim, users.c.role == 'dosen')
                )).scalar()
            bind.execute(class_table.insert().values(
                course_code=code,
                class_name=class_name,
                semester=str(semester),
                lecturer_id=linked_id,
                lecturer_name=lecturer_display,
                room=room,
                day=day,
                start_time=start_time,
                end_time=end_time,
                capacity=35,
                is_open=True,
            ))


def downgrade():
    # Seeded class/room data comes from actual academic documents and user
    # confirmations; preserve it rather than silently deleting live KRS data.
    pass
