from datetime import timedelta
import os
from urllib.parse import urlsplit, urlunsplit

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import User
from app.seed import DEMO_PASSWORD, DEMO_USER_NIMS
from app.services.time_utils import utc_now

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
security = HTTPBearer(auto_error=False)
AUTH_COOKIE_NAME = 'course_recom_session'
AUTH_SESSION_MAX_AGE = 8 * 60 * 60


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=AUTH_SESSION_MAX_AGE,
        httponly=True,
        secure=settings.environment.casefold() in {'prod', 'production'},
        samesite='lax',
        path='/',
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path='/',
        httponly=True,
        secure=settings.environment.casefold() in {'prod', 'production'},
        samesite='lax',
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def authenticate_user(db: Session, username: str, password: str):
    normalized_username = username.strip().casefold()
    user = db.query(User).filter(
        (User.nim == username)
        | (User.username == username)
        | (User.email == username)
        | (User.username.ilike(normalized_username))
        | (User.email.ilike(normalized_username))
    ).first()
    if not user or not user.is_active:
        return None
    if (
        settings.environment.casefold() in {'prod', 'production'}
        and user.nim.casefold() in DEMO_USER_NIMS
        and password == DEMO_PASSWORD
    ):
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(username: str, role: str, token_version: int = 0):
    payload = {
        'sub': username,
        'role': role,
        'token_version': token_version,
        'exp': utc_now() + timedelta(hours=8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm='HS256')


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    token = credentials.credentials if credentials and credentials.credentials else cookie_token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')

    # Cookie-authenticated unsafe requests must originate from the configured
    # frontend/API origin. Bearer clients remain compatible and bypass CSRF checks.
    if not credentials and cookie_token and request.method.upper() not in {'GET', 'HEAD', 'OPTIONS'}:
        origin = (request.headers.get('origin') or '').rstrip('/')
        configured_origin = urlsplit(settings.frontend_url)
        allowed_origins = {
            urlunsplit((configured_origin.scheme, configured_origin.netloc, '', '', '')).rstrip('/')
        }
        if configured_origin.hostname in {'localhost', '127.0.0.1'}:
            alternate_host = '127.0.0.1' if configured_origin.hostname == 'localhost' else 'localhost'
            alternate_netloc = f'{alternate_host}:{configured_origin.port}' if configured_origin.port else alternate_host
            allowed_origins.add(urlunsplit((configured_origin.scheme, alternate_netloc, '', '', '')))
        render_origin = os.environ.get('RENDER_EXTERNAL_URL', '').rstrip('/')
        if render_origin:
            allowed_origins.add(render_origin)
        if not origin or origin not in allowed_origins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Origin tidak diizinkan untuk autentikasi berbasis cookie.',
            )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=['HS256'])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token') from exc
    username = payload.get('sub')
    token_role = payload.get('role')
    token_version = payload.get('token_version', 0)
    user = db.query(User).filter(User.nim == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User account is inactive')
    if token_role != user.role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token role is no longer valid')
    if token_version != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token is no longer valid')
    return user


def require_roles(*roles):
    def dependency(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden for this role')
        return user
    return dependency
