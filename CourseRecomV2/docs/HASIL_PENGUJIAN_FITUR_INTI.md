# Hasil Pengujian Fitur Inti

## Lingkup Pengujian dan Batas Bukti

Pengujian dilakukan pada workspace yang tersedia pada 3 November 2026. Workspace teridentifikasi sebagai **CourseRecom**, bukan WarungPintar. Tidak ditemukan kode kasir, inventori, produk, stok, penjualan, pelanggan, supplier, pembayaran, atau laporan warung.

Karena itu:

- Fitur WarungPintar tidak dapat dieksekusi dan diberi status `BLOCKED`.
- Fitur CourseRecom yang menjadi pengganti demonstrasi diuji secara nyata melalui API/pytest, lint frontend, dan build frontend.
- Tidak ada browser automation atau halaman yang dibagikan untuk uji UI browser. Hasil UI yang hanya berupa status build/lint tidak dinyatakan sebagai pengujian interaksi browser.

## Perintah dan Bukti Nyata

Backend:

```text
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

Hasil aktual:

```text
34 passed, 162 warnings
```

Frontend lint:

```text
cd frontend
npm run lint
```

Hasil: exit code 0.

Frontend build:

```text
cd frontend
npm run build
```

Hasil: exit code 0; 1896 modul berhasil ditransformasi dan bundle production berhasil dibuat.

## Tabel Hasil Pengujian

| No. | Fitur/skenario | Data atau langkah uji | Hasil yang diharapkan | Hasil aktual | Status | Catatan |
|---|---|---|---|---|---|---|
| 1 | WarungPintar: alur utama | Cari kode kasir, produk, transaksi, stok, dan API WarungPintar; jalankan aplikasi demo | Alur warung dapat dijalankan dari awal sampai akhir dengan data sintetis | Tidak ada modul/domain WarungPintar dalam workspace | **BLOCKED** | Aplikasi aktual adalah CourseRecom. |
| 2 | Input valid: autentikasi mahasiswa | Login sintetis dengan akun mahasiswa yang tersedia pada test suite | API mengembalikan JWT dan akses role mahasiswa | Test `test_login_student` berhasil; JWT diterima | **LULUS** | Data berasal dari fixture/seed test. |
| 3 | Alur utama CourseRecom sebagai proxy | Login mahasiswa; buka katalog; unggah preview KHS sintetis; konfirmasi; tampilkan rekomendasi; ajukan rencana | Preview tidak tersimpan sebagai record, konfirmasi menyimpan record, rekomendasi mematuhi aturan, rencana tersimpan | Test workflow pass pada suite | **LULUS** | Pengujian backend nyata, bukan pengujian browser UI. |
| 4 | Input valid: registrasi mahasiswa | POST registrasi dengan NIM sintetis dan password memenuhi aturan | Akun mahasiswa dibuat; role dipaksa `mahasiswa`; login berhasil | Test `test_student_registration_creates_student_only_account` pass | **LULUS** | Percobaan role admin pada registrasi ditolak sebagai role dan tetap mahasiswa. |
| 5 | Input kosong/tidak valid: password terlalu pendek | Registrasi dengan password pendek | API menolak dengan validasi HTTP 422 | Test `test_student_registration_rejects_short_password` pass | **LULUS** | Bukti validasi schema. |
| 6 | Input tidak valid: akses lintas role | Login mahasiswa, lalu akses endpoint admin | API mengembalikan 403 | Test `test_admin_forbidden_for_student` pass | **LULUS** | RBAC backend terverifikasi. |
| 7 | Input valid: katalog kurikulum | Katalog sintetis semester 1–8, termasuk prasyarat dan semester berulang; request oleh mahasiswa | Hanya semester 1–8 dikembalikan dengan field katalog yang benar | Test `test_student_curriculum_is_read_only_and_limited_to_semesters_one_through_eight` pass | **LULUS** | Operasi write dengan POST juga ditolak. |
| 8 | Input valid/tidak valid: parser KHS | PDF, teks KHS, dan format OCR sintetis dengan metadata serta mata kuliah | Metadata dan semester diekstraksi; format/isi tidak valid ditolak | Semua test parser pada suite pass | **LULUS** | Parser memakai monkeypatch untuk komponen OCR pada test tertentu. |
| 9 | Input valid: upload beberapa halaman KHS gambar | Beberapa gambar sintetis diproses OCR; buat preview | Satu preview dapat dikoreksi dan belum tersimpan sampai konfirmasi | Test `test_multiple_khs_images_create_a_reviewable_preview` pass | **LULUS** | OCR nyata tidak dijalankan pada seluruh test; komponen dieksekusi dengan mock. |
| 10 | Alur valid: konfirmasi KHS dan rekomendasi | KHS sintetis dengan mata kuliah valid/tidak valid, konfirmasi, kemudian panggil rekomendasi | Hanya mata kuliah sesuai aturan yang direkomendasikan; KHS ditampilkan sebagai confirmed | Test `test_khs_preview_is_not_saved_until_confirmation_and_rules_filter_courses` pass | **LULUS** | Bukti rule/prasyarat dan kuota pada backend. |
| 11 | Input valid: minat dan similarity mahasiswa | Dua mahasiswa memiliki minat berbeda dan history serupa | Cocok dengan katalog kategori minat; similarity menghitung nama kode berbeda | Test interest dan student similarity pass | **LULUS** | Covered sebagai unit backend. |
| 12 | Input tidak valid: prasyarat belum terpenuhi | Mata kuliah memiliki prasyarat yang belum lulus | Mata kuliah ditolak dan alasan prasyarat ditampilkan | `test_prereq_met` dan route/workflow terkait pass | **LULUS** | Tidak ada rekaman UI browser. |
| 13 | Input tidak valid: SKS melebihi kuota | Mata kuliah/gabungan mata kuliah melampaui kuota hasil IPK | Proses menolak atau menandai kandidat tidak valid | Test `test_sks_limit` dan `test_sks_quota_uses_ipk_thresholds` pass | **LULUS** | Aturan backend terverifikasi. |
| 14 | Input tidak valid: konflik jadwal | Buat dua mata kuliah dengan jadwal bentrok jika jalur masih mendukung | Jadwal bentrok ditolak | Test jadwal pada suite pass | **LULUS** | Jalur mungkin lebih sebagai helper dan perlu audit penggunaan route aktual. |
| 15 | Konfirmasi ganda pengajuan KRS | Coba dua submission pending untuk mahasiswa yang sama pada database yang sama | Hanya satu StudyPlan pending tersimpan; request kedua ditolak atau dilaporkan konflik | Test `test_study_plan_index_allows_only_one_pending_plan_per_student` pass | **LULUS** | Proteksi database terverifikasi. |
| 16 | Alur review Dosen PA | Buat rencana sintetis; login dosen; setujui atau revision dengan catatan | Status dan reviewer/catatan tersimpan, lalu dapat dibaca kembali | Test `test_teacher_reviews_submitted_study_plan_with_guidance_note` pass | **LULUS** | Status approved terkunci dari perubahan. |
| 17 | Konfigurasi database PostgreSQL | URL PostgreSQL plain dan legacy scheme | URL dinormalisasi ke psycopg yang benar | Dua test konfigurasi PostgreSQL pass | **LULUS** | Unit configuration. |
| 18 | Konfigurasi admin bootstrap | Admin bootstrap sebagian dan cloud seed | Sistem menolak konfigurasi tidak lengkap atau membuat admin secara aman bila konfigurasi lengkap | Test bootstrap dan cloud seed pass | **LULUS** | Tidak membuka nilai rahasia. |
| 19 | Impor Excel/CSV katalog | Buku katalog sintetis berisi header Indonesia, prasyarat berulang, dan merge | Data dipetakan dan merged tanpa kehilangan prasyarat | Test course catalog pass | **LULUS** | Tidak diuji melalui browser upload. |
| 20 | Error API/backend | Akses endpoint admin dengan mahasiswa | 403; tidak ada data berhasil dibaca | Test RBAC pass | **LULUS** | Menyimulasikan API unauthorized. |
| 21 | Kondisi database gagal nyata | Matikan database atau arahkan koneksi ke database unavailable | API memberikan kegagalan tanpa menampilkan rahasia/data acak | Tidak ada test koneksi database yang secara eksplisit memutus database | **BELUM DIUJI** | Perlu test integration environment terisolasi sebelum dinyatakan lulus. |
| 22 | Kondisi API layanan upstream gagal | Nonaktifkan API eksternal Gemini | Sistem tetap berjalan dengan fallback lokal atau pesan aman | Implementasi fallback ada pada kode, tetapi tidak ada test eksternal terhubung | **BELUM DIUJI** | Tidak boleh dinyatakan lulus tanpa test failure nyata. |
| 23 | Uji ulang setelah perbaikan | Jalankan ulang seluruh suite setelah ada perubahan | Tidak ada regression pada fungsi terdampak | Tidak ada perbaikan aplikasi yang diperlukan oleh temuan saat ini; seluruh suite dijalankan sekali dan 34 pass | **LULUS** | Status ini hanya valid untuk suite backend saat pengujian ini. |
| 24 | Regresi frontend | Jalankan lint dan build production | Kode frontend lolos lint dan bundle production dapat dibuat | Lint dan build exit 0 | **LULUS** | Tidak membuktikan semua interaksi browser. |
| 25 | UI end-to-end login → KHS → recommendation → KRS → review | Jalankan browser nyata dengan akun sintetis | Navigasi dan penyimpanan tampilan end-to-end sesuai role | Tidak ada browser yang dibagikan/disediakan untuk automation | **BLOCKED** | Browser automation tidak tersedia dalam sesi saat pengujian. |
| 26 | Responsivitas UI | Buka tampilan desktop dan mobile pada browser | Layout tetap usable pada viewport berbeda | Tidak ada browser shared | **BLOCKED** | Tidak boleh diprediksi dari CSS/build. |
| 27 | Penanganan laporan PDF | Membuat/men-download laporan draft KRS | PDF dibuat dan dapat dibuka | Tidak ada route/button/generator PDF ditemukan | **GAGAL** | Gap requirement, bukan bug runtime. |
| 28 | Fitur pencatatan bug/proses QA WBS | Verifikasi bahwa bug log dan hasil UAT proyek tersedia | Artefak proyek tersedia dan dapat ditelusuri | Artefak QA baru dibuat sebagai laporan pengujian | **LULUS** | Ini merupakan kelengkapan artefak pengujian, bukan fitur aplikasi. |

## Ringkasan Jumlah Status

- LULUS: 22.
- BLOCKED: 3.
- BELUM DIUJI: 2.
- GAGAL: 1.

Catatan: row 28 mengukur kelengkapan artefak QA, bukan fungsi aplikasi.

## Bug dan Temuan yang Terbukti

1. Workspace tidak memiliki fungsi WarungPintar, sehingga pengujian semua fitur warung diblokir.
2. Unduhan laporan PDF belum ditemukan.
3. Tidak ada evidence otomatis responsivitas/UI E2E.
4. Gemini fallback belum memiliki test kegagalan nyata.
5. Database outage belum diuji pada koneksi terisolasi.

Tidak ada bug fungsional CourseRecom yang direproduksi dan diulang sebagai kegagalan pada suite backend yang dijalankan.

## Kesimpulan Kesiapan Demonstrasi

- Alur backend kritis CourseRecom memiliki evidence test yang kuat dan suite 34 test lulus.
- Autentikasi, RBAC, KHS, katalog, rekomendasi, pengajuan KRS, review dosen, dan proteksi rencana pending telah diuji pada backend.
- Frontend lint dan production build lulus.
- Fitur tidak siap dinyatakan siap demonstrasi secara penuh untuk WarungPintar karena implementasi WarungPintar tidak ada.
- Kursus/course rekomendasi dapat dipertimbangkan untuk demo berdasarkan test backend, dengan catatan UI E2E dan PDF belum terverifikasi.
- Jangan menyatakan aplikasi 100% bebas bug; browser E2E, database outage, API upstream failure, dan integrasi PDF belum terbukti.
