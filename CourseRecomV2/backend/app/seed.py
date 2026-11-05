import bcrypt

from app.data.seed_data import course_catalog
from app.config import settings
from app.database import SessionLocal
from app.models import Course, User

DEMO_PASSWORD = 'password123'
DEMO_USER_NIMS = frozenset({'2203001', '2203002', '2203003', '2203004', '2203005', 'pa001', 'admin'})


def build_demo_password() -> str:
    return bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt()).decode()


def seed_data() -> None:
    db = SessionLocal()
    try:
        if db.query(Course).count() == 0:
            for item in course_catalog:
                course_data = dict(item)
                course_data['prerequisite_codes'] = course_data.get('prerequisite_codes', '') or ''
                db.add(Course(**course_data))
        if settings.seed_demo_users:
            users = [
                User(nim='2203001', full_name='Andi Pratama', role='mahasiswa', email='andi@campus.id', password_hash=build_demo_password(), semester=5, ipk=3.42, sks_lulus=96, sks_sisa=48, kuota_sks=24, interests='AI/ML,Data'),
                User(nim='2203002', full_name='Siti Aisyah', role='mahasiswa', email='siti@campus.id', password_hash=build_demo_password(), semester=5, ipk=3.78, sks_lulus=102, sks_sisa=42, kuota_sks=24, interests='AI/ML,Web/Mobile'),
                User(nim='2203003', full_name='Budi Santoso', role='mahasiswa', email='budi@campus.id', password_hash=build_demo_password(), semester=5, ipk=2.65, sks_lulus=80, sks_sisa=52, kuota_sks=20, interests='Jaringan'),
                User(nim='2203004', full_name='Dewi Lestari', role='mahasiswa', email='dewi@campus.id', password_hash=build_demo_password(), semester=5, ipk=3.10, sks_lulus=88, sks_sisa=44, kuota_sks=22, interests='Data'),
                User(nim='2203005', full_name='Rizky Ramadhan', role='mahasiswa', email='rizky@campus.id', password_hash=build_demo_password(), semester=5, ipk=3.55, sks_lulus=100, sks_sisa=40, kuota_sks=24, interests='Web/Mobile,AI/ML'),
                User(nim='pa001', full_name='Dosen PA', role='dosen', email='dosen@campus.id', password_hash=build_demo_password()),
                User(nim='admin', full_name='Admin Prodi', role='admin', email='admin@campus.id', password_hash=build_demo_password()),
            ]
            for user in users:
                if not db.query(User).filter(User.nim == user.nim).first():
                    db.add(user)
        elif (
            db.query(User).count() == 0
            and settings.bootstrap_admin_nim
            and settings.bootstrap_admin_name
            and settings.bootstrap_admin_password
        ):
            password_hash = bcrypt.hashpw(
                settings.bootstrap_admin_password.encode(),
                bcrypt.gensalt(),
            ).decode()
            db.add(User(
                nim=settings.bootstrap_admin_nim,
                full_name=settings.bootstrap_admin_name,
                role='admin',
                password_hash=password_hash,
            ))
        db.commit()
    finally:
        db.close()
