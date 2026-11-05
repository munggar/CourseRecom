# Catatan Perbaikan Bug CourseRecom

Tanggal pengerjaan: 4 November 2026

Dokumen ini mencatat tiga perbaikan yang diminta pada source code CourseRecom.

## BUG-01 — Username registrasi menghalangi submit

**Penyebab:** Input Username pada halaman registrasi memiliki atribut HTML `required`, padahal alur registrasi mengisi username dengan NIM ketika kolom dibiarkan kosong.

**Perbaikan:** Atribut `required` dihapus dari input Username. Validasi panjang tetap berlaku bila pengguna mengisi username. Handler frontend dan backend tetap memakai NIM sebagai nilai default.

**Berkas:** `frontend/src/App.jsx`

## BUG-02 — Daftar mata kuliah yang belum diambil berasal dari seed statis

**Penyebab:** Endpoint `GET /api/mahasiswa/profil` membentuk `not_taken_course_codes` dari `course_catalog` pada seed data, bukan dari katalog aktif yang tersimpan di database.

**Perbaikan:** Endpoint sekarang mengambil kode dari tabel `Course` dengan filter `Course.is_active = true`, lalu mengurangi kode yang sudah tercatat pada riwayat akademik mahasiswa. Import seed catalog yang tidak lagi digunakan dihapus.

**Berkas:** `backend/app/api/routes/mahasiswa.py`

## BUG-03 — Validasi minat tidak mengikuti batas kolom database

**Penyebab:** Skema `ProfileUpdate` sebelumnya tidak menetapkan batas panjang dan menerima string kosong. Kolom database `User.interests` memiliki batas `String(255)`.

**Perbaikan:** Skema API sekarang menolak nilai kosong/whitespace dan membatasi `interests` maksimal 255 karakter. Nilai yang valid di-trim sebelum disimpan. Di UI, tombol Simpan Minat dinonaktifkan dan instruksi ditampilkan ketika belum ada peminatan yang dipilih.

**Berkas:**
- `backend/app/schemas.py`
- `frontend/src/App.jsx`

## Regression test yang ditambahkan

Berkas `backend/tests/test_profile_regressions.py` menambahkan pengujian untuk:

1. Memastikan endpoint profil menggunakan katalog aktif dari database dan mengabaikan mata kuliah nonaktif.
2. Memastikan endpoint update profil menolak minat kosong, whitespace, dan input di atas 255 karakter, serta menerima panjang maksimum 255 karakter.

## Status verifikasi pada environment pengerjaan

- Pemeriksaan sintaks Python (`py_compile`) untuk file backend yang diubah dan file test baru: **LULUS**.
- Pengujian langsung skema Pydantic: **LULUS** — string kosong, whitespace, dan 256/300 karakter ditolak; 255 karakter diterima; nilai valid di-trim.
- Pytest integrasi: **BELUM DAPAT DIJALANKAN** — environment eksekusi tidak memiliki `python-jose` dan `passlib`, dan instalasi dependensi terhalang karena akses package registry tidak tersedia.
- Frontend lint/build: **BELUM DAPAT DIJALANKAN** — `node_modules` yang ikut dalam ZIP asal berisi dependensi native untuk Windows, sedangkan environment pemeriksaan menggunakan Linux. Dependency folder tidak disertakan dalam ZIP hasil; jalankan instalasi npm pada mesin target sebelum lint/build.
- Uji browser untuk registrasi: **BELUM DIJALANKAN** pada environment ini. Perbaikan HTML telah diverifikasi dari source; uji akhir dapat dilakukan di browser dengan membiarkan Username kosong dan mendaftarkan mahasiswa menggunakan NIM sebagai username.

Tidak ada klaim bahwa seluruh aplikasi bebas bug. Catatan ini hanya mencakup tiga bug yang diminta dan verifikasi yang benar-benar dapat dilakukan pada environment ini.
