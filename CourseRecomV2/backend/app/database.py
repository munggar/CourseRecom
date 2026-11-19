from pathlib import Path
from threading import Lock

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

is_sqlite = settings.database_url.startswith('sqlite')
connect_args = {'check_same_thread': False} if is_sqlite else {'connect_timeout': 10}
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=not is_sqlite,
    pool_timeout=15,
    pool_recycle=300,
)
if is_sqlite:
    @event.listens_for(engine, 'connect')
    def enable_sqlite_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
_schema_lock = Lock()
_schema_ready = False


def ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        config_path = Path(__file__).resolve().parent.parent / 'alembic.ini'
        config = Config(str(config_path))
        config.set_main_option(
            'sqlalchemy.url',
            settings.database_url.replace('%', '%%'),
        )
        config.set_main_option(
            'script_location',
            str(Path(__file__).resolve().parent.parent / 'alembic'),
        )
        command.upgrade(config, 'head')
        _schema_ready = True


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
