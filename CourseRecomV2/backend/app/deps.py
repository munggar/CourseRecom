from datetime import timedelta

from fastapi import Depends, HTTPException, status
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
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
    token = credentials.credentials
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
