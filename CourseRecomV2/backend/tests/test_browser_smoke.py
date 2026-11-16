import os
from io import BytesIO

import pytest


def test_demo_roles_navigate_on_desktop_and_mobile():
    base_url = os.getenv("E2E_BASE_URL")
    if not base_url:
        pytest.skip("E2E_BASE_URL is only configured in the isolated browser job")

    from playwright.sync_api import expect, sync_playwright

    accounts = {
        "Mahasiswa": ("2203001", "password123", "Dashboard Mahasiswa"),
        "Dosen PA": ("pa001", "password123", "Dashboard Dosen PA"),
        "Admin Prodi": ("admin", "password123", "Dashboard Admin Prodi"),
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(base_url, wait_until="networkidle")
        expect(page.get_by_role("heading", name="CourseRecom")).to_be_visible()

        def login(role):
            username, password, dashboard_label = accounts[role]
            page.get_by_role("radio", name=role).click()
            page.get_by_label("Username").fill(username)
            page.get_by_label("Password").fill(password)
            page.get_by_role("button", name="Masuk").click()
            expect(page.locator(".topbar-label")).to_contain_text(dashboard_label)

        def logout():
            page.locator(".sidebar").get_by_role("button", name="Keluar").click()
            expect(page.get_by_role("button", name="Masuk")).to_be_visible()

        login("Mahasiswa")
        for nav_label, heading in [
            ("Kurikulum", "Kurikulum Program Studi"),
            ("Upload KHS", "Unggah KHS Lengkap"),
            ("Rekomendasi MK", "Rekomendasi Mata Kuliah"),
            ("Riwayat KHS", "Riwayat KHS"),
            ("Minat & Profil", "Minat & Profil"),
        ]:
            page.locator(".sidebar").get_by_role("button", name=nav_label).click()
            expect(page.get_by_role("heading", name=heading).first).to_be_visible()
        logout()

        login("Dosen PA")
        page.locator(".sidebar").get_by_role("button", name="Bimbingan Mahasiswa").click()
        expect(page.get_by_role("heading", name="Bimbingan Mahasiswa")).to_be_visible()
        logout()

        login("Admin Prodi")
        for nav_label, heading in [
            ("Manajemen Data", "Manajemen Data"),
            ("Daftar Akun Dosen PA", "Akun Dosen PA"),
            ("Riwayat Dosen PA", "Riwayat Penetapan Dosen PA"),
        ]:
            page.locator(".sidebar").get_by_role("button", name=nav_label).click()
            expect(page.get_by_role("heading", name=heading).first).to_be_visible()
        logout()

        page.set_viewport_size({"width": 390, "height": 844})
        login("Mahasiswa")
        page.get_by_role("button", name="Buka menu").click()
        expect(page.get_by_role("navigation", name="Navigasi utama")).to_be_visible()
        page.locator("#mobile-navigation").get_by_role("button", name="Upload KHS").click()
        expect(page.get_by_role("heading", name="Unggah KHS Lengkap")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth") is True
        browser.close()


def test_student_khs_recommendation_submission_advisor_review_and_official_pdf():
    base_url = os.getenv("E2E_BASE_URL")
    if not base_url:
        pytest.skip("E2E_BASE_URL is only configured in the isolated browser job")

    from reportlab.pdfgen import canvas
    from playwright.sync_api import expect, sync_playwright

    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer)
    pdf.setFont("Helvetica", 11)
    rows = [
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
    for row in rows:
        pdf.drawString(48, y, row)
        y -= 22
    pdf.save()
    khs_pdf = pdf_buffer.getvalue()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(base_url, wait_until="networkidle")

        # Run the real admin assignment endpoint against the isolated test app.
        admin_login = page.request.post(
            base_url + "/api/auth/login",
            data={"username": "admin", "password": "password123", "role": "admin"},
        )
        assert admin_login.status == 200, admin_login.text
        admin_token = admin_login.json()["access_token"]
        assignment = page.request.patch(
            base_url + "/api/admin/students/2203001/advisor",
            headers={"Authorization": "Bearer " + admin_token},
            data={"advisor_nim": "pa001", "reason": "Isolated browser acceptance test"},
        )
        assert assignment.status == 200, assignment.text
        assert assignment.json()["advisor_nim"] == "pa001"

        # Student uploads a synthetic text-based PDF KHS and confirms the preview.
        page.get_by_role("radio", name="Mahasiswa").click()
        page.get_by_label("Username").fill("2203001")
        page.get_by_label("Password").fill("password123")
        page.get_by_role("button", name="Masuk").click()
        expect(page.locator(".topbar-label")).to_contain_text("Dashboard Mahasiswa")

        token = page.evaluate("localStorage.getItem('courseRecomToken')")
        profile_response = page.request.get(
            base_url + "/api/mahasiswa/profil",
            headers={"Authorization": "Bearer " + token},
        )
        assert profile_response.status == 200, profile_response.text
        assert profile_response.json()["advisor"]["nim"] == "pa001"

        page.locator(".sidebar").get_by_role("button", name="Upload KHS").click()
        page.locator("#khs-pdf").set_input_files({
            "name": "khs-demo-2203001.pdf",
            "mimeType": "application/pdf",
            "buffer": khs_pdf,
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

        # Open recommendations, add Machine Learning, and submit the KRS.
        page.locator(".sidebar").get_by_role("button", name="Rekomendasi MK").click()
        expect(page.get_by_role("heading", name="Kandidat yang lolos aturan akademik")).to_be_visible()
        machine_learning = page.locator(".recommendation-card").filter(has_text="TI301")
        expect(machine_learning).to_be_visible()
        add_button = machine_learning.get_by_role("button", name="Tambah ke Draft KRS")
        if add_button.is_enabled():
            add_button.click()
        expect(page.locator(".draft-summary")).to_contain_text("1 mata kuliah")
        page.get_by_role("button", name="Ajukan ke Dosen PA").click()
        expect(page.get_by_text("Rencana studi berhasil diajukan ke dosen PA.", exact=False)).to_be_visible()

        page.locator(".sidebar").get_by_role("button", name="Keluar").click()
        expect(page.get_by_role("button", name="Masuk")).to_be_visible()

        # Advisor receives the student's plan and approves it.
        page.get_by_role("radio", name="Dosen PA").click()
        page.get_by_label("Username").fill("pa001")
        page.get_by_label("Password").fill("password123")
        page.get_by_role("button", name="Masuk").click()
        expect(page.locator(".topbar-label")).to_contain_text("Dashboard Dosen PA")
        page.locator(".sidebar").get_by_role("button", name="Bimbingan Mahasiswa").click()
        student_plan = page.locator(".history-document").filter(has_text="2203001")
        expect(student_plan).to_be_visible()
        expect(student_plan.get_by_text("Menunggu review")).to_be_visible()
        student_plan.get_by_role("button", name="Setujui rencana studi").click()
        expect(student_plan.get_by_text("Disetujui")).to_be_visible()

        page.locator(".sidebar").get_by_role("button", name="Keluar").click()
        expect(page.get_by_role("button", name="Masuk")).to_be_visible()

        # Student sees the approval and downloads the official PDF.
        page.get_by_role("radio", name="Mahasiswa").click()
        page.get_by_label("Username").fill("2203001")
        page.get_by_label("Password").fill("password123")
        page.get_by_role("button", name="Masuk").click()
        expect(page.get_by_text("Disetujui dosen PA")).to_be_visible()
        with page.expect_download() as download_info:
            page.get_by_role("button", name="Unduh PDF KRS Resmi").click()
        download = download_info.value
        assert download.suggested_filename.endswith(".pdf")
        downloaded = download.path()
        with open(downloaded, "rb") as stream:
            assert stream.read(5) == b"%PDF-"
        browser.close()
