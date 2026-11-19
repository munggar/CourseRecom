import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.dosen import router as dosen_router
from app.api.routes.mahasiswa import router as mahasiswa_router
from app.config import settings
from app.database import ensure_schema
from app.seed import seed_data

logger = logging.getLogger("courserecom.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup.begin environment=%s", settings.environment)
    try:
        logger.info("startup.schema.begin")
        await asyncio.to_thread(ensure_schema)
        logger.info("startup.schema.complete")
        logger.info("startup.seed.begin")
        await asyncio.to_thread(seed_data)
        logger.info("startup.seed.complete")
    except Exception:
        logger.exception("startup.failed")
        raise
    app.state.ready = True
    logger.info("startup.ready")
    try:
        yield
    finally:
        app.state.ready = False
        logger.info("shutdown.complete")


app = FastAPI(title='CourseRecom', version='1.0.0', lifespan=lifespan)
app.state.ready = False
frontend_origin = urlsplit(settings.frontend_url)
allowed_origins = {settings.frontend_url.rstrip('/')}
for preview_port in ('4173', '5173'):
    for preview_host in ('localhost', '127.0.0.1'):
        allowed_origins.add(f'{frontend_origin.scheme}://{preview_host}:{preview_port}')
if frontend_origin.hostname in {'localhost', '127.0.0.1'}:
    alternate_host = '127.0.0.1' if frontend_origin.hostname == 'localhost' else 'localhost'
    alternate_netloc = alternate_host
    if frontend_origin.port:
        alternate_netloc = f'{alternate_netloc}:{frontend_origin.port}'
    allowed_origins.add(urlunsplit((
        frontend_origin.scheme,
        alternate_netloc,
        '',
        '',
        '',
    )))
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allowed_origins),
    allow_origin_regex=r'https?://(localhost|127\\.0\\.0\\.1)(:\\d+)?',
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(auth_router, prefix='/api')
app.include_router(mahasiswa_router, prefix='/api')
app.include_router(dosen_router, prefix='/api')
app.include_router(admin_router, prefix='/api')


@app.get('/api/health')
def health():
    if not app.state.ready:
        raise HTTPException(status_code=503, detail='Application is starting')
    return {'status': 'ok', 'app': 'CourseRecom'}


frontend_dir = Path(__file__).resolve().parent / 'static'
if frontend_dir.is_dir():
    app.mount('/', StaticFiles(directory=frontend_dir, html=True), name='frontend')
