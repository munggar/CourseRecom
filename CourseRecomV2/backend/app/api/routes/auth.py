import re
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import AUTH_COOKIE_NAME, authenticate_user, clear_session_cookie, create_access_token, get_current_user, get_db, get_password_hash, set_session_cookie, verify_password
from app.models import SystemSetting, User
from app.schemas import AccountProfileResponse, AccountProfileUpdate, PasswordChange, TokenResponse, UserLogin, UserOut
from app.services.validation import get_sks_quota
from app.services.audit import write_audit
from app.services.program_interests import get_program_interest_catalog, normalize_program_name, validate_program_interest

router = APIRouter()


def _academic_year_context(db: Session) -> dict[str, int | str]:
    setting = db.query(SystemSetting).filter(SystemSetting.key == 'active_academic_year').first()
    current_year = datetime.now(ZoneInfo('Asia/Jakarta')).year
    academic_year = setting.value.strip() if setting and setting.value else f'{current_year}/{current_year + 1}'
    match = re.fullmatch(r'(\d{4})/(\d{4})', academic_year)
    if not match or int(match.group(2)) != int(match.group(1)) + 1:
        academic_year = f'{current_year}/{current_year + 1}'
    return {
        'academic_year': academic_year,
        'max_angkatan': int(academic_year.split('/')[0]),
    }


@router.get('/auth/program-interests')
def get_program_interests():
    return get_program_interest_catalog()


@router.get('/auth/academic-year')
def get_academic_year(db: Session = Depends(get_db)):
    return _academic_year_context(db)


@router.post('/auth/register', status_code=status.HTTP_403_FORBIDDEN)
def register_student():
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail='Pendaftaran mandiri dinonaktifkan. Akun mahasiswa dibuat oleh Admin Prodi melalui impor roster Excel/CSV.',
    )


@router.post('/auth/login', response_model=TokenResponse)
def login(payload: UserLogin, request: Request, http_response: Response, db: Session = Depends(get_db)):
    login_name = payload.username.strip()
    user = db.query(User).filter(
        (User.nim == login_name)
        | (func.lower(User.username) == login_name.casefold())
        | (func.lower(User.email) == login_name.casefold())
    ).first()
    if not user:
        write_audit(db, None, 'login_failed', 'user', payload.username, None, {'role': payload.role})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Username atau password salah.')
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Akun dinonaktifkan atau belum aktif.')
    if not authenticate_user(db, payload.username, payload.password):
        write_audit(db, user, 'login_failed', 'user', user.id, None, {'reason': 'invalid_password'})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Username atau password salah.')
    if payload.role and payload.role != user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Peran yang dipilih tidak sesuai dengan akun.',
        )
    token = create_access_token(user.nim, user.role, user.token_version)
    cookie_mode = request.headers.get('x-auth-mode', '').casefold() == 'cookie'
    if cookie_mode:
        set_session_cookie(http_response, token)
    write_audit(db, user, 'login_success', 'user', user.id, None, {'role': user.role, 'auth_mode': 'cookie' if cookie_mode else 'bearer'})
    db.commit()
    return {
        'access_token': None if cookie_mode else token,
        'token_type': 'cookie' if cookie_mode else 'bearer',
    }


@router.post('/auth/session/migrate', status_code=status.HTTP_204_NO_CONTENT)
def migrate_legacy_session(
    http_response: Response,
    current_user: User = Depends(get_current_user),
):
    """Exchange a previously stored Bearer token for an HttpOnly browser cookie."""
    token = create_access_token(current_user.nim, current_user.role, current_user.token_version)
    set_session_cookie(http_response, token)
    http_response.status_code = status.HTTP_204_NO_CONTENT
    return http_response


@router.get('/auth/me', response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get('/auth/profile', response_model=UserOut)
def account_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put('/auth/profile', response_model=AccountProfileResponse)
def update_account_profile(
    payload: AccountProfileUpdate,
    request: Request,
    http_response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    username = payload.username.strip().casefold()
    if db.query(User).filter(
        User.id != current_user.id,
        (func.lower(User.username) == username) | (func.lower(User.nim) == username),
    ).first():
        raise HTTPException(status_code=409, detail='Username sudah digunakan oleh akun lain.')
    if payload.email and db.query(User).filter(func.lower(User.email) == payload.email.strip().casefold(), User.id != current_user.id).first():
        raise HTTPException(status_code=409, detail='Email sudah digunakan oleh akun lain.')
    if payload.new_password:
        if not verify_password(payload.current_password, current_user.password_hash):
            raise HTTPException(status_code=401, detail='Password saat ini salah.')
        current_user.password_hash = get_password_hash(payload.new_password)
    if current_user.role == 'mahasiswa':
        stored_program = normalize_program_name(current_user.program_study or '')
        requested_program = normalize_program_name(payload.program_study or current_user.program_study or '')
        if payload.program_study is not None and requested_program != stored_program:
            raise HTTPException(
                status_code=409,
                detail='Program studi merupakan data akademik dan hanya dapat diubah melalui admin akademik.',
            )
        if payload.angkatan is not None and payload.angkatan.strip() != (current_user.angkatan or ''):
            raise HTTPException(
                status_code=409,
                detail='Angkatan merupakan data akademik dan hanya dapat diubah melalui admin akademik.',
            )
    identity_changed = username != (current_user.username or '').strip().casefold()
    password_changed = bool(payload.new_password)
    if identity_changed or password_changed:
        current_user.token_version += 1

    current_user.full_name = payload.full_name.strip()
    current_user.username = username
    current_user.email = payload.email.strip() if payload.email else None
    if current_user.role != 'mahasiswa':
        if payload.program_study is not None:
            current_user.program_study = payload.program_study.strip() or None
        if payload.angkatan is not None:
            current_user.angkatan = payload.angkatan.strip() or None
    current_user.phone_number = payload.phone_number
    write_audit(db, current_user, 'profile_updated', 'user', current_user.id, None, {'password_changed': bool(payload.new_password)})
    db.commit()
    db.refresh(current_user)
    response_data = UserOut.model_validate(current_user).model_dump()
    if identity_changed or password_changed:
        renewed_token = create_access_token(
            current_user.nim,
            current_user.role,
            current_user.token_version,
        )
        if request.cookies.get(AUTH_COOKIE_NAME) or request.headers.get('x-auth-mode', '').casefold() == 'cookie':
            set_session_cookie(http_response, renewed_token)
        else:
            response_data['access_token'] = renewed_token
    return response_data


@router.post('/auth/logout', status_code=status.HTTP_204_NO_CONTENT)
def logout(
    http_response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.token_version += 1
    db.commit()
    clear_session_cookie(http_response)
    http_response.status_code = status.HTTP_204_NO_CONTENT
    return http_response
