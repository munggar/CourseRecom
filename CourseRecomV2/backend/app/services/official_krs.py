import base64
import hashlib
import hmac
import io
import ipaddress
import json
import time
import binascii
from urllib.parse import urlsplit

import qrcode
from reportlab.pdfgen import canvas

from app.config import settings


def build_verification_url(request_base_url: str, token: str) -> str:
    api_base = settings.public_api_base_url
    if not api_base:
        if settings.environment.casefold() in {'prod', 'production'}:
            raise ValueError('PUBLIC_API_BASE_URL wajib dikonfigurasi pada production.')
        api_base = request_base_url.rstrip('/') + '/api'
    parsed = urlsplit(api_base)
    if (
        parsed.scheme not in {'http', 'https'}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError('PUBLIC_API_BASE_URL atau request origin tidak valid.')
    hostname = parsed.hostname.rstrip('.').casefold()
    if hostname in {
        'backend',
        'db',
        'postgres',
        'frontend',
        'localhost.localdomain',
    } or hostname.endswith(('.internal', '.local', '.localhost')):
        raise ValueError('URL verifikasi tidak boleh menggunakan hostname internal.')
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address and not address.is_global:
        if settings.environment.casefold() in {'prod', 'production'}:
            raise ValueError('URL verifikasi production harus menggunakan host publik.')
    if not parsed.path.rstrip('/').endswith('/api'):
        raise ValueError('PUBLIC_API_BASE_URL harus diakhiri dengan /api.')
    return f'{api_base.rstrip("/")}/krs/verify/{token}'


def create_verification_token(study_plan_id: int, student_id: int, document_hash: str) -> str:
    payload = json.dumps(
        {
            'plan': study_plan_id,
            'student': student_id,
            'sha256': document_hash,
            'exp': int(time.time()) + 365 * 24 * 60 * 60,
        },
        separators=(',', ':'),
        sort_keys=True,
    )
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
    signature = hmac.new(settings.qr_verification_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f'{encoded}.{signature}'


def verify_token(token: str) -> dict | None:
    try:
        encoded, signature = token.rsplit('.', 1)
        expected = hmac.new(settings.qr_verification_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padding = '=' * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        if payload.get('exp', 0) < int(time.time()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error, UnicodeDecodeError):
        return None


def build_official_krs_pdf(
    student_nim: str,
    student_name: str,
    plan_id: int,
    semester: int,
    courses: list[dict],
    verification_url: str,
) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle(f'KRS Resmi {student_nim}')
    pdf.drawString(72, 770, 'KARTU RENCANA STUDI (KRS) RESMI')
    pdf.drawString(72, 742, f'NIM: {student_nim}')
    pdf.drawString(72, 726, f'Nama: {student_name}')
    pdf.drawString(72, 710, f'Semester: {semester}')
    pdf.drawString(72, 694, f'Referensi KRS: {plan_id}')
    pdf.line(72, 682, 540, 682)
    y = 658
    total_sks = 0
    for course in courses:
        sks = int(course.get('sks', 0))
        total_sks += sks
        pdf.drawString(72, y, f"{course.get('code', '')} - {course.get('name', '')} ({sks} SKS)")
        y -= 18
        if y < 110:
            pdf.showPage()
            y = 770
    pdf.drawString(72, 96, f'Total SKS: {total_sks}')
    pdf.drawString(72, 80, f'Verifikasi: {verification_url}')

    qr = qrcode.make(verification_url)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    from reportlab.lib.utils import ImageReader
    pdf.drawImage(ImageReader(qr_buffer), 450, 60, width=90, height=90, preserveAspectRatio=True, mask='auto')
    pdf.save()

    content = buffer.getvalue()
    return content, hashlib.sha256(content).hexdigest()
