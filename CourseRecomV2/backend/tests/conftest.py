import os
import tempfile
from pathlib import Path

import pytest


_test_database = Path(tempfile.gettempdir()) / f'courserecom-tests-{os.getpid()}.db'
os.environ['DATABASE_URL'] = f'sqlite:///{_test_database.as_posix()}'
os.environ['ENVIRONMENT'] = 'testing'
os.environ['SEED_DEMO_USERS'] = 'true'


@pytest.fixture(scope='session', autouse=True)
def remove_test_database():
    from app.database import ensure_schema
    from app.seed import seed_data

    ensure_schema()
    seed_data()
    yield
    from app.database import engine

    engine.dispose()
    try:
        _test_database.unlink(missing_ok=True)
    except PermissionError:
        pass
