from __future__ import annotations

import csv
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / 'backend'
FRONTEND_DIR = PROJECT_DIR / 'frontend'
BACKEND_URL = 'http://127.0.0.1:8000'
FRONTEND_URL = 'http://127.0.0.1:5173'


def wait_for_url(url: str, process: subprocess.Popen, timeout_seconds: int, log_path: Path) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = 'not contacted yet'
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_tail = log_path.read_text(encoding='utf-8', errors='replace')[-6000:]
            raise RuntimeError(f'Server exited with code {process.returncode}: {log_tail}')
        try:
            request = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(request, timeout=3) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    log_tail = log_path.read_text(encoding='utf-8', errors='replace')[-6000:]
    raise TimeoutError(f'Timed out waiting for {url}: {last_error}\n{log_tail}')


def login(page, role_label: str, username: str) -> None:
    page.get_by_role('radio', name=role_label).click()
    page.get_by_label('Username').fill(username)
    page.get_by_label('Password').fill('password123')
    page.get_by_role('button', name='Masuk', exact=True).click()
    page.locator('.topbar-label').wait_for(state='visible', timeout=20000)


def run_browser_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix='courserecom-e2e-') as temp_dir:
        temp_path = Path(temp_dir)
        database_path = temp_path / 'courserecom-e2e.sqlite3'
        backend_log = temp_path / 'backend.log'
        frontend_log = temp_path / 'frontend.log'

        environment = os.environ.copy()
        environment.update({
            'ENVIRONMENT': 'testing',
            'DATABASE_URL': f'sqlite:///{database_path}',
            'JWT_SECRET': 'courserecom-e2e-jwt-secret-value-at-least-32-bytes',
            'QR_VERIFICATION_SECRET': 'courserecom-e2e-qr-secret-value-at-least-32-bytes',
            'FRONTEND_URL': FRONTEND_URL,
            'SEED_DEMO_USERS': 'true',
            'REQUIRE_STUDENT_ROSTER': 'true',
            'API_PROXY_TARGET': BACKEND_URL,
        })

        with backend_log.open('w', encoding='utf-8') as backend_output, frontend_log.open('w', encoding='utf-8') as frontend_output:
            backend = subprocess.Popen(
                [
                    os.environ.get('PYTHON', 'python'),
                    '-m', 'uvicorn',
                    'app.main:app',
                    '--host', '127.0.0.1',
                    '--port', '8000',
                ],
                cwd=BACKEND_DIR,
                env=environment,
                stdout=backend_output,
                stderr=subprocess.STDOUT,
            )
            frontend = None
            try:
                wait_for_url(f'{BACKEND_URL}/api/health', backend, 90, backend_log)
                frontend = subprocess.Popen(
                    [
                        'npm', 'run', 'dev', '--',
                        '--host', '127.0.0.1',
                        '--port', '5173',
                        '--strictPort',
                    ],
                    cwd=FRONTEND_DIR,
                    env=environment,
                    stdout=frontend_output,
                    stderr=subprocess.STDOUT,
                )
                wait_for_url(FRONTEND_URL, frontend, 60, frontend_log)

                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                    page = context.new_page()
                    page_errors: list[str] = []
                    page.on('pageerror', lambda error: page_errors.append(str(error)))

                    # Admin journey: cookie login -> class schedule -> Excel import template.
                    page.goto(FRONTEND_URL, wait_until='domcontentloaded')
                    login(page, 'Admin Prodi', 'admin')
                    assert page.locator('.topbar-label').inner_text() == 'Dashboard Admin Prodi'

                    session_cookie = next(
                        (cookie for cookie in context.cookies() if cookie['name'] == 'course_recom_session'),
                        None,
                    )
                    assert session_cookie is not None, 'Browser login did not create the session cookie.'
                    assert session_cookie['httpOnly'] is True, 'Session cookie must be HttpOnly.'
                    assert session_cookie['sameSite'].lower() == 'lax'
                    assert page.evaluate("localStorage.getItem('courseRecomToken')") is None, (
                        'Browser login must not persist JWT in localStorage.'
                    )

                    page.get_by_role('button', name='Kelas & Jadwal').click()
                    page.get_by_role('heading', name='Tambah kelas dari Excel').wait_for(
                        state='visible',
                        timeout=15000,
                    )
                    with page.expect_download(timeout=20000) as download_info:
                        page.get_by_role('button', name='Unduh template Excel').click()
                    download = download_info.value
                    downloaded_path = Path(download.path())
                    assert downloaded_path.read_bytes()[:2] == b'PK', 'Excel template is not a valid XLSX ZIP package.'

                    # Admin onboarding journey: import a temporary official roster row and issue one-time code.
                    student_nim = 'E2E' + str(int(time.time()))[-10:]
                    student_name = 'Mahasiswa Browser Uji'
                    roster_file = temp_path / 'roster-e2e.csv'
                    with roster_file.open('w', encoding='utf-8-sig', newline='') as stream:
                        writer = csv.writer(stream)
                        writer.writerow(['NIM', 'Nama Lengkap', 'Program Studi', 'Angkatan'])
                        writer.writerow([student_nim, student_name, 'Sistem dan Teknologi Informasi', '2022'])

                    page.get_by_role('button', name='Pendaftaran Mahasiswa').click()
                    page.get_by_role('heading', name='Pendaftaran Mahasiswa').wait_for(state='visible', timeout=15000)
                    page.locator('input[type="file"]').set_input_files(str(roster_file))
                    page.get_by_role('button', name='Validasi & impor roster').click()
                    page.get_by_text('1 / 100').wait_for(state='visible', timeout=15000)
                    page.once('dialog', lambda dialog: dialog.accept())
                    with page.expect_download(timeout=20000) as invitation_download_info:
                        page.get_by_role('button', name='Buat & unduh 1 kode pendaftaran').click()
                    invitation_path = Path(invitation_download_info.value.path())
                    with invitation_path.open('r', encoding='utf-8-sig', newline='') as stream:
                        invitation = next(csv.DictReader(stream))
                    assert invitation['NIM'] == student_nim
                    invitation_code = invitation['Kode Pendaftaran']
                    assert len(invitation_code) >= 24

                    # Logout must revoke and remove the cookie before the new real-style student registers.
                    page.get_by_role('button', name='Keluar').click()
                    page.get_by_text('Rencanakan Studi Lebih Cerdas').wait_for(state='visible', timeout=15000)
                    assert not any(cookie['name'] == 'course_recom_session' for cookie in context.cookies())

                    # Student self-registration: roster identity + one-time invitation + personal password.
                    page.get_by_role('button', name='Daftar akun mahasiswa').click()
                    registration_form = page.locator('.login-box form')
                    registration_form.get_by_role('textbox', name='NIM', exact=True).fill(student_nim)
                    registration_form.get_by_role('textbox', name='Nama lengkap', exact=True).fill(student_name)
                    registration_form.get_by_role('combobox', name='Program studi', exact=True).select_option(label='Sistem dan Teknologi Informasi')
                    registration_form.get_by_role('spinbutton', name='Angkatan', exact=True).fill('2022')
                    registration_form.get_by_role('textbox', name='Kode pendaftaran resmi Kode', exact=True).fill(invitation_code)
                    registration_form.get_by_role('textbox', name='Password (minimal 8 karakter)', exact=True).fill('secure-student-password-123')
                    registration_form.get_by_role('textbox', name='Konfirmasi password', exact=True).fill('secure-student-password-123')
                    registration_form.get_by_role('button', name='Daftar sebagai mahasiswa').click()
                    page.get_by_text('Pendaftaran mahasiswa berhasil', exact=False).wait_for(state='visible', timeout=15000)

                    # Login as the newly registered student and open KHS upload screen.
                    login(page, 'Mahasiswa', student_nim)
                    assert page.locator('.topbar-label').inner_text() == 'Dashboard Mahasiswa'
                    page.get_by_role('button', name='Upload KHS').click()
                    page.get_by_role('heading', name='Unggah KHS Lengkap').wait_for(
                        state='visible',
                        timeout=15000,
                    )
                    assert page.locator('input[type="file"]').count() >= 1
                    assert page.evaluate("localStorage.getItem('courseRecomToken')") is None
                    assert not page_errors, f'Browser JavaScript errors: {page_errors}'

                    browser.close()
            finally:
                for process in (frontend, backend):
                    if process is not None and process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


if __name__ == '__main__':
    try:
        run_browser_smoke()
    except PlaywrightTimeoutError as exc:
        raise SystemExit(f'Browser E2E timed out: {exc}') from exc
    print('CourseRecom browser E2E smoke checks passed.')
