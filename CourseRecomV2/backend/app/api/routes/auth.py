from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import authenticate_user, create_access_token, get_current_user, get_db, get_password_hash, verify_password
from app.models import User
from app.schemas import AccountProfileResponse, AccountProfileUpdate, PasswordChange, StudentRegistration, TokenResponse, UserLogin, UserOut
from app.services.validation import get_sks_quota
from app.services.audit import write_audit

router = APIRouter()


@router.post('/auth/register', status_code=status.HTTP_201_CREATED, response_model=UserOut)
def register_student(payload: StudentRegistration, db: Session = Depends(get_db)):
    if db.query(User).filter(User.nim == payload.nim).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='NIM sudah terdaftar.')
    username = (payload.username or payload.nim).strip()
    if db.query(User).filter((User.username == username) | (User.nim == username)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Username sudah terdaftar.')

    student = User(
        nim=payload.nim,
        full_name=payload.full_name,
        username=username,
        program_study=payload.program_study.strip() or None,
        angkatan=payload.angkatan.strip() or None,
        role='mahasiswa',
        password_hash=get_password_hash(payload.password),
        semester=1,
        sks_lulus=0,
        sks_sisa=settings.total_curriculum_sks,
        kuota_sks=get_sks_quota(None),
        interests='',
        advisor_id=None,
    )
    db.add(student)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='NIM sudah terdaftar.') from exc
    db.refresh(student)
    return student


@router.post('/auth/login', response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    login_name = payload.username.strip()
    user = db.query(User).filter(
        (User.nim == login_name)
        | (func.lower(User.username) == login_name.casefold())
        | (func.lower(User.email) == login_name.casefold())
    ).first()
    if not user:
        write_audit(db, None, 'login_failed', 'user', payload.username, None, {'role': payload.role})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Username tidak ditemukan.')
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Akun dinonaktifkan atau belum aktif.')
    if not authenticate_user(db, payload.username, payload.password):
        write_audit(db, user, 'login_failed', 'user', user.id, None, {'reason': 'invalid_password'})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Password salah.')
    if payload.role and payload.role != user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Peran yang dipilih tidak sesuai dengan akun.',
        )
    token = create_access_token(user.nim, user.role, user.token_version)
    write_audit(db, user, 'login_success', 'user', user.id, None, {'role': user.role})
    db.commit()
    return {'access_token': token, 'token_type': 'bearer'}


@router.get('/auth/me', response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get('/auth/profile', response_model=UserOut)
def account_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put('/auth/profile', response_model=AccountProfileResponse)
def update_account_profile(
    payload: AccountProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    username = payload.username.strip().casefold()
    if db.query(User).filter(User.username == username, User.id != current_user.id).first():
        raise HTTPException(status_code=409, detail='Username sudah digunakan oleh akun lain.')
    if payload.email and db.query(User).filter(User.email == payload.email.strip(), User.id != current_user.id).first():
        raise HTTPException(status_code=409, detail='Email sudah digunakan oleh akun lain.')
    if payload.new_password:
        if not verify_password(payload.current_password, current_user.password_hash):
            raise HTTPException(status_code=401, detail='Password saat ini salah.')
        current_user.password_hash = get_password_hash(payload.new_password)
    identity_changed = username != current_user.username.strip().casefold()
    password_changed = bool(payload.new_password)
    if identity_changed or password_changed:
        current_user.token_version += 1

    current_user.full_name = payload.full_name.strip()
    current_user.username = username
    current_user.email = payload.email.strip() if payload.email else None
    current_user.program_study = payload.program_study.strip() if payload.program_study else None
    current_user.angkatan = payload.angkatan.strip() if payload.angkatan else None
    current_user.phone_number = payload.phone_number
    write_audit(db, current_user, 'profile_updated', 'user', current_user.id, None, {'password_changed': bool(payload.new_password)})
    db.commit()
    db.refresh(current_user)
    response = UserOut.model_validate(current_user).model_dump()
    if identity_changed or password_changed:
        response['access_token'] = create_access_token(
            current_user.nim,
            current_user.role,
            current_user.token_version,
        )
    return response


@router.post('/auth/logout', status_code=status.HTTP_204_NO_CONTENT)
def logout(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_user.token_version += 1
    db.commit()
