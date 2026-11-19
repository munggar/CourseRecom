import base64
import hashlib
import hmac
import io
import ipaddress
import json
import time
import binascii
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

import qrcode
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    text = escape(str(value if value not in (None, '') else '-')).replace('\n', '<br/>')
    return Paragraph(text, style)


def build_official_krs_pdf(
    student_nim: str,
    student_name: str,
    plan_id: int,
    semester: int,
    courses: list[dict],
    verification_url: str,
    *,
    program_study: str = '',
    faculty_name: str = 'Fakultas Teknologi Industri dan Informatika',
    academic_term: str = '',
    advisor_name: str = '',
    advisor_nim: str = '',
    issue_date: str = '',
) -> tuple[bytes, str]:
    """Build a formal, UHAMKA-style KRS document with verifiable QR footer."""
    buffer = io.BytesIO()
    page_width, _ = A4
    left_margin = 17 * mm
    right_margin = 17 * mm
    usable_width = page_width - left_margin - right_margin

    styles = {
        'university': ParagraphStyle(
            'KrsUniversity', fontName='Helvetica-Bold', fontSize=13,
            leading=16, alignment=TA_CENTER, spaceAfter=4 * mm,
        ),
        'title': ParagraphStyle(
            'KrsTitle', fontName='Helvetica-Bold', fontSize=14,
            leading=17, alignment=TA_CENTER, spaceAfter=1.5 * mm,
        ),
        'subtitle': ParagraphStyle(
            'KrsSubtitle', fontName='Helvetica', fontSize=10.5,
            leading=13, alignment=TA_CENTER, spaceAfter=7 * mm,
        ),
        'meta_label': ParagraphStyle(
            'KrsMetaLabel', fontName='Helvetica', fontSize=9,
            leading=12, alignment=TA_LEFT,
        ),
        'meta_value': ParagraphStyle(
            'KrsMetaValue', fontName='Helvetica', fontSize=9,
            leading=12, alignment=TA_LEFT,
        ),
        'cell': ParagraphStyle(
            'KrsCell', fontName='Helvetica', fontSize=7.1,
            leading=8.6, alignment=TA_LEFT,
        ),
        'cell_center': ParagraphStyle(
            'KrsCellCenter', fontName='Helvetica', fontSize=7.1,
            leading=8.6, alignment=TA_CENTER,
        ),
        'header_cell': ParagraphStyle(
            'KrsHeaderCell', fontName='Helvetica-Bold', fontSize=7.1,
            leading=8.5, alignment=TA_CENTER,
        ),
        'summary': ParagraphStyle(
            'KrsSummary', fontName='Helvetica', fontSize=9,
            leading=12,
        ),
        'sign_label': ParagraphStyle(
            'KrsSignLabel', fontName='Helvetica', fontSize=9,
            leading=12, alignment=TA_CENTER,
        ),
        'sign_name': ParagraphStyle(
            'KrsSignName', fontName='Helvetica-Bold', fontSize=8.5,
            leading=10.5, alignment=TA_CENTER,
        ),
        'footnote': ParagraphStyle(
            'KrsFootnote', fontName='Helvetica', fontSize=6.4,
            leading=8, textColor=colors.HexColor('#53616a'),
        ),
    }

    story = [
        Paragraph('UNIVERSITAS MUHAMMADIYAH PROF. DR. HAMKA', styles['university']),
        Paragraph('KRS MAHASISWA', styles['title']),
        Paragraph(escape(academic_term or f'Semester {semester}'), styles['subtitle']),
    ]

    identity_rows = [
        [_paragraph('NIM', styles['meta_label']), _paragraph(':', styles['meta_label']), _paragraph(student_nim, styles['meta_value'])],
        [_paragraph('Nama', styles['meta_label']), _paragraph(':', styles['meta_label']), _paragraph(student_name, styles['meta_value'])],
        [_paragraph('Fakultas', styles['meta_label']), _paragraph(':', styles['meta_label']), _paragraph(faculty_name, styles['meta_value'])],
        [_paragraph('Prog. Studi', styles['meta_label']), _paragraph(':', styles['meta_label']), _paragraph(program_study, styles['meta_value'])],
    ]
    identity = Table(identity_rows, colWidths=[25 * mm, 5 * mm, usable_width - 30 * mm], hAlign='LEFT')
    identity.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 1.4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.4),
    ]))
    story.extend([identity, Spacer(1, 6 * mm)])

    headers = ['NO', 'Kode', 'Mata Kuliah', 'Kelas', 'Jadwal Kuliah', 'Ruang', 'Kampus', 'SKS', 'Pengajar']
    table_data = [[Paragraph(escape(label), styles['header_cell']) for label in headers]]
    total_sks = 0
    for index, course in enumerate(courses, start=1):
        credits = int(course.get('sks') or 0)
        total_sks += credits
        day = str(course.get('day') or '').strip()
        start_time = str(course.get('start_time') or '').strip()
        end_time = str(course.get('end_time') or '').strip()
        if day and start_time and end_time:
            schedule = f'{day} {start_time}-{end_time}'
        else:
            schedule = course.get('schedule') or course.get('time') or '-'
        lecturer = course.get('lecturer_name') or course.get('lecturer') or '-'
        table_data.append([
            _paragraph(index, styles['cell_center']),
            _paragraph(course.get('code') or '-', styles['cell_center']),
            _paragraph(course.get('name') or '-', styles['cell']),
            _paragraph(course.get('class_name') or '-', styles['cell_center']),
            _paragraph(schedule, styles['cell_center']),
            _paragraph(course.get('room') or '-', styles['cell_center']),
            Paragraph(escape(str(course.get('campus') or '')), styles['cell_center']),
            _paragraph(credits, styles['cell_center']),
            _paragraph(lecturer, styles['cell']),
        ])

    column_widths = [
        7 * mm, 17 * mm, 31 * mm, 11 * mm,
        25 * mm, 12 * mm, 15 * mm, 8 * mm,
        usable_width - (7 + 17 + 31 + 11 + 25 + 12 + 15 + 8) * mm,
    ]
    course_table = Table(
        table_data,
        colWidths=column_widths,
        repeatRows=1,
        hAlign='LEFT',
        splitByRow=1,
    )
    course_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.65, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef2f4')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (1, -1), 'CENTER'),
        ('ALIGN', (3, 0), (7, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3.2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3.2),
        ('TOPPADDING', (0, 0), (-1, -1), 4.2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4.2),
    ]))
    story.append(course_table)
    story.append(Spacer(1, 5 * mm))

    summary_rows = [
        [Paragraph(f'Jumlah Mata Kuliah&nbsp;&nbsp;&nbsp;&nbsp;: &nbsp;{len(courses)}', styles['summary'])],
        [Paragraph(f'Jumlah SKS Mata Kuliah&nbsp;&nbsp;: &nbsp;{total_sks}', styles['summary'])],
    ]
    summary = Table(summary_rows, colWidths=[usable_width], hAlign='LEFT')
    summary.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    story.append(summary)
    story.append(Spacer(1, 10 * mm))

    advisor_display = advisor_name or 'Belum ditetapkan'
    if advisor_nim:
        advisor_display = f'{advisor_display}<br/><font size="7">NIP: {escape(str(advisor_nim))}</font>'
    student_display = f'{escape(student_name)}<br/><font size="7">NIM: {escape(student_nim)}</font>'
    signing_data = [[
        Paragraph('Dosen PA', styles['sign_label']),
        Paragraph(f'{escape(issue_date) if issue_date else "Jakarta"}<br/>Mahasiswa yang bersangkutan', styles['sign_label']),
    ], ['', ''], [
        Paragraph(advisor_display, styles['sign_name']),
        Paragraph(student_display, styles['sign_name']),
    ]]
    signing = Table(signing_data, colWidths=[usable_width / 2, usable_width / 2], rowHeights=[17, 24, None])
    signing.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEABOVE', (0, 2), (-1, 2), 0.4, colors.HexColor('#687780')),
    ]))
    story.append(signing)

    qr = qrcode.make(verification_url)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    qr_image = ImageReader(qr_buffer)

    def draw_footer(pdf_canvas, document):
        pdf_canvas.saveState()
        pdf_canvas.setStrokeColor(colors.HexColor('#c9d2d8'))
        pdf_canvas.setLineWidth(0.45)
        pdf_canvas.line(left_margin, 31 * mm, page_width - right_margin, 31 * mm)
        pdf_canvas.setFont('Helvetica', 6.6)
        pdf_canvas.setFillColor(colors.HexColor('#53616a'))
        pdf_canvas.drawString(left_margin, 24 * mm, f'CourseRecom | Ref. KRS #{plan_id}')
        pdf_canvas.drawString(left_margin, 19 * mm, 'Pindai QR code untuk memverifikasi keaslian dokumen.')
        pdf_canvas.drawRightString(page_width - right_margin - 27 * mm, 10 * mm, f'Halaman {document.page}')
        qr_x = page_width - right_margin - 25 * mm
        qr_y = 3 * mm
        pdf_canvas.drawImage(qr_image, qr_x, qr_y, width=23 * mm, height=23 * mm, preserveAspectRatio=True, mask='auto')
        pdf_canvas.linkURL(verification_url, (qr_x, qr_y, qr_x + 23 * mm, qr_y + 23 * mm), relative=0, thickness=0)
        pdf_canvas.restoreState()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=right_margin,
        leftMargin=left_margin,
        topMargin=15 * mm,
        bottomMargin=34 * mm,
        title=f'KRS Resmi {student_nim}',
        author='CourseRecom - Universitas Muhammadiyah Prof. Dr. Hamka',
        subject=f'KRS semester {semester} mahasiswa {student_nim}',
    )
    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)

    content = buffer.getvalue()
    return content, hashlib.sha256(content).hexdigest()
