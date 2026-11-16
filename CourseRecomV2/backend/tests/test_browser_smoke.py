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
        expect(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")).to_be_truthy()

        browser.close()
