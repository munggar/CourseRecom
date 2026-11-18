"""Room inventory and FTII public lecturer directory.

Revision ID: 20261118_04
Revises: 20261118_03
Create Date: 2026-11-18
"""
from datetime import datetime
import sqlalchemy as sa
from alembic import op

revision = '20261118_04'
down_revision = '20261118_03'
branch_labels = None
depends_on = None

ROOM_SOURCE = 'https://ft.uhamka.ac.id/wp-content/uploads/2023/10/Jadwal-Blended-Learning-FTII-UHAMKA-Gasal-2023-2024-Rev2.pdf'
ROOMS = [('FT301',3,'01'),('FT302',3,'02'),('FT303',3,'03'),('FT304',3,'04'),('FT305',3,'05'),
         ('FT401',4,'01'),('FT402',4,'02'),('FT403',4,'03'),('FT404',4,'04'),('FT405',4,'05'),('FT406',4,'06')]
STI = 'https://ft.uhamka.ac.id/dosen-sti/'
TI = 'https://ft.uhamka.ac.id/dosen-ti/'
TM = 'https://ft.uhamka.ac.id/dosen-teknik-mesin/'
TRM = 'https://ft.uhamka.ac.id/dosen-rekayasa-teknologi-mekatronika/'
TE = 'https://ft.uhamka.ac.id/prodi/elektro/'
LECTURERS = [
('0302026504','E. Rizal, S.Kom., M.Kom.','Sistem dan Teknologi Informasi',STI,'S2 Ilmu Komputer, Universitas Budi Luhur','Pemrograman; logika fuzzy',None),
('0305046403','Dr. Ir. Mohammad Givi Efgivia, M.Kom.','Sistem dan Teknologi Informasi',STI,'S3 Teknologi Pendidikan','Distance Learning',None),
('0301087904','Faldy Irwiensyah, S.Kom., M.TI.','Sistem dan Teknologi Informasi',STI,'S2 Teknologi Informasi, Universitas Indonesia','ICT; SDLC; CRM',None),
('0316099202','Isa Faqihuddin, S.Kom., M.MSI.','Sistem dan Teknologi Informasi',STI,'S2 Sistem Informasi, Universitas Gunadarma','Information system; software design',None),
('0330019204','Rahmi Imanda, S.Kom., M.Kom.','Sistem dan Teknologi Informasi',STI,'S2 Ilmu Komputer, Universitas Indonesia','Sistem informasi',None),
('4063770671130303','Tirta Anhari, S.T., M.Kom.','Sistem dan Teknologi Informasi',STI,'S2 Teknik Informatika, Universitas Bina Nusantara','Business Intelligence; IT Governance','NIDN disalin persis sesuai profil; verifikasi sebelum dipakai sebagai ID akun'),
(None,'Aditya Rawasa Putra Aidy, S.T., M.M.','Sistem dan Teknologi Informasi',STI,'S2 Magister Manajemen, Prasetiya Mulya','Bisnis; manajemen; finance; AI','NIDN tidak ditampilkan pada profil'),
('0312028704','Mia Kamayani Sulaeman, S.T., M.T.','Teknik Informatika',TI,'S2 Teknik Informatika, ITB','Machine learning; NLP','Ketua Prodi TI'),
('0328056901','Ir. Arry Avorizano, S.Kom., M.Kom.','Teknik Informatika',TI,'S2 Ilmu Komputer, Universitas Budi Luhur','Information system; network; security',None),
('0331017304','Atiqah Meutia Hilda, S.Kom., M.Kom.','Teknik Informatika',TI,'S2 Ilmu Komputer, UGM',None,None),
('0322077101','Endy Syaiful Alim, S.T., M.T., Ph.D.','Teknik Informatika',TI,'S3 Computer Applied Technology, HUST','ICT; cloud computing',None),
('0301088305','Firman Noor Hasan, S.Kom., M.TI.','Teknik Informatika',TI,'S2 Teknik Informatika, Binus','Data warehouse; business intelligence',None),
('0307128301','Ir. Muchammad Sholeh, S.Kom., M.Kom.','Teknik Informatika',TI,'S2 Ilmu Komputer, Universitas Budi Luhur','Cyber security; IT governance',None),
('0314098403','Estu Sinduningrum, S.T., M.T.','Teknik Informatika',TI,'S2 Manajemen Telekomunikasi, Telkom','Sistem digital; pengolahan citra',None),
('0306028502','Dimas Febriawan, S.Kom., M.TI.','Teknik Informatika',TI,'S2 Teknologi Informasi, UI','IT security',None),
('0304048505','Nuroji, S.T., M.Kom.','Teknik Informatika',TI,'S2 Ilmu Komputer','Informatika; sistem informasi',None),
('0313028602','Ir. Zuhri Halim, S.Kom., M.Kom.','Teknik Informatika',TI,'S2 Teknik Informatika, STMIK Eresha','Data mining; sistem informasi',None),
('0302069105','Ir. Nunik Pratiwi, S.T., M.Kom.','Teknik Informatika',TI,'S2 Ilmu Komputer, UI','Image processing',None),
('0321089205','Irwansyah, S.Kom., M.Kom.','Teknik Informatika',TI,'S2 Teknologi Sistem Informasi, UBL','Data mining; sistem pendukung keputusan',None),
('0325119302','Ir. Ade Davy Wiranata, M.Kom.','Teknik Informatika',TI,'S2 Teknologi Sistem Informasi, UBL','Informatika; sistem informasi',None),
('0305046501','Ir. Rifky, S.T., M.M., M.T., IPP.','Teknik Mesin',TM,'Magister Teknik Mesin, Universitas Pancasila; PPI ITB','Material; energi',None),
('0301126901','Dr. Ir. Dan Mugisidi, S.T., M.Si., IPP.','Teknik Mesin',TM,'S3 UI / Undip','Desalinasi; energi hidro','Juga dicantumkan sebagai Dekan FTII'),
('0305067702','Dr. Oktarina Heriyani, S.Si., M.T.','Teknik Mesin',TM,'S3 Undip','Teknik dan manajemen industri',None),
('0311087002','Delvis Agusman, S.T., M.Sc.','Teknik Mesin',TM,'Computer Integrated Manufacturing','Teknik produksi; manufaktur',None),
('0301087803','Hendi Saryanto, S.T., M.Eng.','Teknik Mesin',TM,'S2 Universiti Tun Hussein Onn Malaysia','Material teknik; engineering design',None),
('0324069102','Dr. Ir. Riyan Ariyansah, S.T., M.T., IPM.','Teknik Mesin',TM,'S2 Teknik Mesin','Manufaktur',None),
('0311128701','Akhmad Rizal Dzikrillah, S.T., M.TI.','Teknologi Rekayasa Mekatronika',TRM,'S2 Teknologi Informasi, UI','DSS; artificial intelligence','Ketua Prodi TRM'),
('0304017001','Rosalina, S.T., M.T.','Teknologi Rekayasa Mekatronika',TRM,'S2',None,None),
('0315046802','Pancatatva Hesti Gunawan, S.T., M.T.','Teknologi Rekayasa Mekatronika',TRM,'S2, UI','Teknik mesin; desain produk',None),
('0319087101','Agus Fikri, S.T., M.M., M.T.','Teknologi Rekayasa Mekatronika',TRM,'S2','Teknik mesin',None),
('0319027901','Yos Nofendri, S.Pd., MSME.','Teknologi Rekayasa Mekatronika',TRM,'S2, Universiti Kebangsaan Malaysia','Konversi energi',None),
('0310049502','Nur Chalik Azhar, S.Kom., M.Kom.','Teknologi Rekayasa Mekatronika',TRM,'S2 Manajemen Sistem Informasi, Binus','Information system',None),
(None,'Ir. Harry Ramza, M.T., Ph.D., MIPM','Teknik Elektro',TE,None,None,'Laman Prodi Elektro menyebut Ketua Program Studi; direktori dosen khusus belum ditemukan'),
]

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'rooms' not in inspector.get_table_names():
        op.create_table(
            'rooms',
            sa.Column('code', sa.String(10), primary_key=True, nullable=False),
            sa.Column('floor', sa.Integer(), nullable=False),
            sa.Column('room_number', sa.String(3), nullable=False),
            sa.Column('capacity', sa.Integer(), nullable=True),
            sa.Column('room_type', sa.String(40), nullable=False, server_default='Ruang kuliah'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('source_status', sa.String(60), nullable=False, server_default='needs_verification'),
            sa.Column('source_url', sa.String(500), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('verified_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
    if 'lecturer_directory' not in inspector.get_table_names():
        op.create_table(
            'lecturer_directory',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('nidn', sa.String(30), nullable=True),
            sa.Column('full_name', sa.String(180), nullable=False),
            sa.Column('program_study', sa.String(120), nullable=False),
            sa.Column('email', sa.String(120), nullable=True),
            sa.Column('education', sa.Text(), nullable=True),
            sa.Column('expertise', sa.Text(), nullable=True),
            sa.Column('source_type', sa.String(60), nullable=False, server_default='official_program_profile'),
            sa.Column('profile_url', sa.String(500), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('linked_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )
        op.create_index('ix_lecturer_directory_nidn', 'lecturer_directory', ['nidn'], unique=True)
        op.create_index('ix_lecturer_directory_linked_user_id', 'lecturer_directory', ['linked_user_id'])
    now = datetime.utcnow()
    rooms_table = sa.table('rooms',
        sa.column('code', sa.String), sa.column('floor', sa.Integer),
        sa.column('room_number', sa.String), sa.column('capacity', sa.Integer),
        sa.column('room_type', sa.String), sa.column('is_active', sa.Boolean),
        sa.column('source_status', sa.String), sa.column('source_url', sa.String),
        sa.column('notes', sa.String), sa.column('created_at', sa.DateTime))
    directory_table = sa.table('lecturer_directory',
        sa.column('nidn', sa.String), sa.column('full_name', sa.String),
        sa.column('program_study', sa.String), sa.column('email', sa.String),
        sa.column('education', sa.String), sa.column('expertise', sa.String),
        sa.column('source_type', sa.String), sa.column('profile_url', sa.String),
        sa.column('notes', sa.String))
    for code, floor, number in ROOMS:
        if not bind.execute(sa.select(rooms_table.c.code).where(rooms_table.c.code == code)).first():
            bind.execute(rooms_table.insert().values(
                code=code, floor=floor, room_number=number, capacity=None,
                room_type='Ruang kuliah', is_active=False,
                source_status='arsip_2023_2024_perlu_konfirmasi',
                source_url=ROOM_SOURCE,
                notes='Terdapat pada arsip jadwal Gasal 2023/2024. Kapasitas dan status aktif 2026/2027 tidak dipublikasikan; verifikasi fisik sebelum diaktifkan.',
                created_at=now))
    for nidn, name, program, url, education, expertise, notes in LECTURERS:
        if nidn and bind.execute(sa.select(directory_table.c.nidn).where(directory_table.c.nidn == nidn)).first():
            continue
        # Names without NIDN are kept as distinct profile records; prevent duplicate inserts by name+program.
        if not nidn and bind.execute(sa.select(directory_table.c.full_name).where(
            sa.and_(directory_table.c.full_name == name, directory_table.c.program_study == program)
        )).first():
            continue
        bind.execute(directory_table.insert().values(
            nidn=nidn, full_name=name, program_study=program, email=None,
            education=education, expertise=expertise,
            source_type='official_program_chair' if program == 'Teknik Elektro' else 'official_program_profile',
            profile_url=url, notes=notes))

def downgrade():
    op.drop_index('ix_lecturer_directory_linked_user_id', table_name='lecturer_directory')
    op.drop_index('ix_lecturer_directory_nidn', table_name='lecturer_directory')
    op.drop_table('lecturer_directory')
    op.drop_table('rooms')
