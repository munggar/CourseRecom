# Daftar Bug dan Perbaikan

## Ringkasan

Pengujian suite backend tidak menemukan kegagalan runtime yang dapat direproduksi pada fungsi CourseRecom yang teruji. Tidak ada perubahan kode aplikasi yang dibuat.

Temuan berikut dibedakan sebagai:

- gap scope/artefak;
- perlu pengujian tambahan;
- bug implementasi yang belum terbukti.

Tidak ada temuan dengan bukti kegagalan aktual yang memenuhi kriteria bug aplikasi dan dapat diperbaiki pada tahap ini.

## Daftar Temuan

| ID | Deskripsi | Lokasi File | Prioritas | Penyebab | Tindakan Perbaikan | Hasil Pengujian Ulang |
|---|---|---|---|---|---|---|
| BUG-001 | Workspace tidak menyediakan WarungPintar yang dapat diuji | Workspace root; tidak ada implementasi terkait warung | **CRITICAL untuk tugas WarungPintar** | Workspace memiliki CourseRecom dan dokumen PDF CourseRecom; tidak ada sumber kode warung yang terbuka | Tambahkan atau buka workspace WarungPintar yang benar. Jangan menebak atau mengimplementasikan fitur Warung pada CourseRecom. | Setelah workspace benar tersedia, jalankan ulang seluruh skenario kritis. Saat ini **BLOCKED**; belum ada tindakan kode yang bisa diperbaiki tanpa workspace sumber. |
| GAP-001 | Laporan draft KRS PDF tidak tersedia meskipun diperlukan proposal | Tidak ditemukan route/komponen PDF pada `frontend/src/App.jsx` dan `backend/app/api/routes/*.py` | **HIGH** | Tidak ada implementation generator/download PDF pada repository | Kembangkan implementasi PDF hanya sesuai scope CourseRecom setelah keputusan tugas, atau konfirmasi bahwa requirement keluar dari assignment. Tambah test API dan browser download. | Belum diuji ulang; belum menjadi bagian kode saat ini. Status: **BELUM DIUJI/GAP**. |
| GAP-002 | Koneksi database outage belum diuji secara nyata | `backend/app/database.py`; environment deployment | **HIGH** | Tidak ada test integration yang memutus database pada sesi ini | Tambah test environment terisolasi yang memulai backend dengan DSN database gagal; verifikasi status HTTP dan pesan error tidak bocor rahasia. | Belum dijalankan; status saat ini **BELUM DIUJI**. |
| GAP-003 | Kegagalan layanan Gemini tidak diuji dengan error upstream | `backend/app/ai_explainer.py`; `backend/app/config.py` | **MEDIUM** | Tidak ada panggilan terverifikasi dari recommendation utama dan tidak ada test failure API eksternal | Tambah mock HTTP yang mengembalikan timeout/error; verifikasi fallback dipakai atau error ditangani. | Belum dijalankan; status saat ini **BELUM DIUJI**. |
| GAP-004 | UI end-to-end dan responsivitas belum diuji dengan browser nyata | `frontend/src/App.jsx`; `frontend/src/App.css` | **HIGH** | Browser tidak dibagikan dan tidak ada test Playwright/Cypress terkonfigurasi | Konfigurasikan test browser lokal pada viewport desktop/mobile dengan data sintetis; ujikan login → KHS → recommendation → submit → review. | Frontend lint dan build lulus. UI E2E tetap **BLOCKED/BELUM DIUJI**. |

## Langkah Reproduksi

### BUG-001

1. Buka workspace root.
2. Cari istilah kasir, stok, penjualan, supplier, atau produk pada frontend/backend.
3. Tidak ada hasil yang relevan.
4. Konfirmasi identitas kode adalah CourseRecom melalui UI dan nama API.

### GAP-001

1. Buka halaman rekomendasi/draft KRS.
2. Cari tombol unduh atau cetak PDF.
3. Cari route backend/report PDF.
4. Tidak ditemukan generator atau endpoint download.

### GAP-002

1. Gunakan database SQLite/PostgreSQL normal.
2. Jalankan backend.
3. Jadikan database tidak tersedia pada lingkungan terisolasi.
4. Request endpoint yang memerlukan DB.
5. Belum ada test reproducible yang memverifikasi respons API pada sesi ini.

### GAP-003

1. Aktifkan jalur Gemini pada konfigurasi terkontrol.
2. Mock API menjadi timeout/401/500.
3. Jalankan layanan rekomendasi.
4. Belum ada bukti test bahwa fallback menangani seluruh kegagalan.

### GAP-004

1. Buka frontend pada browser.
2. Login dan navigasi role.
3. Jalankan alur kritis UI.
4. Audit pada desktop/mobile.
5. Browser tidak tersedia untuk automation pada sesi ini.

## Perbaikan dan Pengujian Ulang

Tidak ada bug kode yang terbukti, direproduksi, dan diperbaiki pada pengujian ini. Oleh karena itu tidak ada regression fix yang dibuat.

Pengujian regresi yang dilakukan pada suite backend aktual menghasilkan `34 passed`; frontend lint dan build juga lulus.

## Risiko dan Kesimpulan

- Tidak ada klaim bahwa aplikasi bebas bug.
- Pengujian WarungPintar tidak dapat dinyatakan lulus.
- Gap PDF adalah gap requirement yang perlu keputusan scope.
- Database outage, eksternal API failure, browser E2E, dan responsivitas memerlukan pengujian lanjut.
