import os

import pytest


def test_demo_roles_can_navigate_their_browser_pages_on_desktop_and_mobile():
    base_url = os.getenv("E2E_BASE_URL")
    if not base_url:
        pytest.skip("E2E_BASE_URL is only configured in the isolated browser job")

    from playwright.sync_api import expect, sync_playwright

    credentials = {
        "Mahasiswa": ("2203001", "password123"),
        "Dosen PA": ("pa001", "password123"),
        "Admin Prodi": ("admin", "password123"),
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(base_url, wait_until="networkidle")
        expect(page.get_by_role("heading", name="CourseRecom")).to_be_visible()

        def login(role_label: str):
            username, password = credentials[role_label]
            page.get_by_role("radio", name=role_label).click()
            page.get_by_label("Username").fill(username)
            page.get_by_label("Password").fill(password)
            page.get_by_role("button", name="Masuk").click()
            expect(page.locator(".topbar-label")).to_contain_text(
                "Dashboard Mahasiswa" if role_label == "Mahasiswa"
                else "Dashboard Dosen PA" if role_label == "Dosen PA"
                else "Dashboard Admin Prodi"
            )

        def logout():
            page.locator(".sidebar").get_by_role("button", name="Keluar").click()
            expect(page.get_by_role("button", name="Masuk")).to_be_visible()

        # Student: dashboard plus all primary student navigation areas.
        login("Mahasiswa")
        student_pages = [
            ("Kurikulum", "Kurikulum Program Studi"),
            ("Upload KHS", "Unggah KHS Lengkap"),
            ("Rekomendasi MK", "Rekomendasi Mata Kuliah"),
            ("Riwayat KHS", "Riwayat KHS"),
            ("Minat & Profil", "Minat & Profil"),
        ]
        for nav_label, heading in student_pages:
            page.locator(".sidebar").get_by_role("button", name=nav_label).click()
            expect(page.get_by_role("heading", name=heading).first).to_be_visible()
        page.locator(".sidebar").get_by_role("button", name="Rekomendasi MK").click()
        expect(page.get_by_text("Unggah dan konfirmasi KHS untuk melihat rekomendasi mata kuliah.", exact=True)).to_be_visible()
        logout()

        # Advisor: dashboard and guidance/review area.
        login("Dosen PA")
        page.locator(".sidebar").get_by_role("button", name="Bimbingan Mahasiswa").click()
        expect(page.get_by_role("heading", name="Bimbingan Mahasiswa")).to_be_visible()
        logout()

        # Admin: dashboard and management areas.
        login("Admin Prodi")
        admin_pages = [
            ("Manajemen Data", "Manajemen Data"),
            ("Daftar Akun Dosen PA", "Akun Dosen PA"),
            ("Riwayat Dosen PA", "Riwayat Penetapan Dosen PA"),
        ]
        for nav_label, heading in admin_pages:
            page.locator(".sidebar").get_by_role("button", name=nav_label).click()
            expect(page.get_by_role("heading", name=heading).first).to_be_visible()
        logout()

        # Mobile viewport: check the responsive menu and student navigation.
        page.set_viewport_size({"width": 390, "height": 844})
        login("Mahasiswa")
        page.get_by_role("button", name="Buka menu").click()
        expect(page.get_by_role("navigation", name="Navigasi utama")).to_be_visible()
        page.locator("#mobile-navigation").get_by_role("button", name="Upload KHS").click()
        expect(page.get_by_role("heading", name="Unggah KHS Lengkap")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth") is True

        browser.close()

def test_student_khs_recommendation_submission_and_advisor_approval_flow():
    base_url = os.getenv("E2E_BASE_URL")
    if not base_url:
        pytest.skip("E2E_BASE_URL is only configured in the isolated browser job")

    from io import BytesIO

    from reportlab.pdfgen import canvas

    from app.database import SessionLocal
    from app.models import User

    from playwright.sync_api import expect, sync_playwright

    # Link the seeded demo student to the seeded advisor only in this
    # disposable SQLite database used by the browser test job.
    db = SessionLocal()
    student = db.query(User).filter(User.nim == "2203001").one()
    advisor = db.query(User).filter(User.nim == "pa001").one()
    student.advisor_id = advisor.id
    db.commit()
    db.close()
    verify_db = SessionLocal()
    assert verify_db.query(User).filter(User.nim == "2203001").one().advisor_id == advisor.id
    verify_db.close()

    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer)
    pdf.setFont("Helvetica", 11)
    lines = [
        "NIM: 2203001",
        "Nama: Andi Pratama",
        "Program Studi: Sistem dan Teknologi Informasi",
        "IPK: 3.60",
        "Semester 4",
        "STAT Statistika 3 90 A",
        "TI201 Analisis Data 3 88 A",
        "TI204 Basis Data 3 85 A",
    ]
    y = 790
    for line in lines:
        pdf.drawString(48, y, line)
        y -= 22
    pdf.save()
    pdf_bytes = pdf_buffer.getvalue()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(base_url, wait_until="networkidle")

        # Student uploads a synthetic KHS PDF, checks its extracted preview,
        # confirms the data, then requests recommendations for semester five.
        page.get_by_role("radio", name="Mahasiswa").click()
        page.get_by_label("Username").fill("2203001")
        page.get_by_label("Password").fill("password123")
        page.get_by_role("button", name="Masuk").click()
        expect(page.get_by_role("heading", name="Dashboard Mahasiswa")).to_be_visible()

        page.locator(".sidebar").get_by_role("button", name="Upload KHS").click()
        page.locator("#khs-pdf").set_input_files({
            "name": "khs-demo-2203001.pdf",
            "mimeType": "application/pdf",
            "buffer": pdf_bytes,
        })
        page.get_by_role("button", name="Baca dan Pratinjau KHS").click()
        expect(page.get_by_role("heading", name="Periksa hasil ekstraksi")).to_be_visible()
        expect(page.get_by_label("NIM", exact=True)).to_have_value("2203001")
        expect(page.get_by_label("Nama mahasiswa")).to_have_value("Andi Pratama")
        expect(page.get_by_text("Menunggu konfirmasi")).to_be_visible()
        expect(page.get_by_label("Kode mata kuliah semester 4")).to_have_count(3)

        page.get_by_role(
            "button",
            name="Data sudah benar — konfirmasi & simpan",
        ).click()
        expect(page.get_by_text("KHS khs-demo-2203001.pdf berhasil dikonfirmasi.", exact=False)).to_be_visible()

        page.locator(".sidebar").get_by_role("button", name="Rekomendasi MK").click()
        expect(page.get_by_role("heading", name="Kandidat yang lolos aturan akademik")).to_be_visible()
        machine_learning = page.locator(".recommendation-card").filter(has_text="TI301")
        expect(machine_learning).to_be_visible()
        machine_learning.get_by_role("button", name="Tambah ke Draft KRS").click()
        expect(page.get_by_text("Draft KRS:", exact=False)).to_contain_text("1 mata kuliah")
        page.get_by_role("button", name="Ajukan ke Dosen PA").click()
        expect(page.get_by_text("Rencana studi berhasil diajukan ke dosen PA.", exact=False)).to_be_visible()

        page.locator(".sidebar").get_by_role("button", name="Keluar").click()
        expect(page.get_by_role("button", name="Masuk")).to_be_visible()

        # The assigned advisor receives the pending plan and approves it.
        page.get_by_role("radio", name="Dosen PA").click()
        page.get_by_label("Username").fill("pa001")
        page.get_by_label("Password").fill("password123")
        page.get_by_role("button", name="Masuk").click()
        expect(page.get_by_role("heading", name="Dashboard Dosen PA")).to_be_visible()
        page.locator(".sidebar").get_by_role("button", name="Bimbingan Mahasiswa").click()
        student_plan = page.locator(".history-document").filter(has_text="2203001")
        expect(student_plan).to_be_visible()
        expect(student_plan.get_by_text("Menunggu review")).to_be_visible()
        student_plan.get_by_role("button", name="Setujui rencana studi").click()
        expect(student_plan.get_by_text("Disetujui")).to_be_visible()

        page.locator(".sidebar").get_by_role("button", name="Keluar").click()
        expect(page.get_by_role("button", name="Masuk")).to_be_visible()

        # The student sees the final approval and can download the official PDF.
        page.get_by_role("radio", name="Mahasiswa").click()
        page.get_by_label("Username").fill("2203001")
        page.get_by_label("Password").fill("password123")
        page.get_by_role("button", name="Masuk").click()
        expect(page.get_by_text("Disetujui dosen PA")).to_be_visible()
        with page.expect_download() as download_info:
            page.get_by_role("button", name="Unduh PDF KRS Resmi").click()
        download = download_info.value
        assert download.suggested_filename.endswith(".pdf")
        downloaded_path = download.path()
        with open(downloaded_path, "rb") as downloaded_file:
            assert downloaded_file.read(5) == b"%PDF-"

        browser.close()
