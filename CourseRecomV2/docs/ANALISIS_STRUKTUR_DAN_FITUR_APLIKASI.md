# Analisis Struktur dan Fitur Aplikasi

## Ruang Lingkup dan Temuan Identitas

Workspace yang diperiksa **bukan aplikasi WarungPintar**. Identitas yang terbukti dari kode, konfigurasi, README, judul UI, dan nama API adalah **CourseRecom**, yaitu aplikasi rekomendasi mata kuliah untuk mahasiswa menggunakan riwayat KHS.

Tidak ada implementasi kasir, inventori, penjualan, QRIS, pelanggan, pemasok, laporan warung, atau zakat perdagangan dalam workspace ini. Dokumen ini tidak menebak bahwa fitur-fitur tersebut ada di commit lain atau branch lain karena tidak ada metadata Git yang tersedia pada workspace.

Audit ini dilakukan dari implementasi kode. Tidak menguji setiap interaksi UI dengan browser, dan tidak membuka atau menuliskan isi konfigurasi rahasia.

## A. Identitas dan Teknologi

### Identitas

- Nama aplikasi: CourseRecom
- Jenis aplikasi: aplikasi web rekomendasi mata kuliah berbasis KHS
- Pengguna: mahasiswa, dosen PA, dan admin prodi
- Monorepo sederhana dengan frontend dan backend terpisah

### Frontend

- React 19
- Vite 8
- JavaScript ES modules
- React DOM
- Lucide React untuk ikon
- CSS khusus pada `frontend/src/App.css` dan `frontend/src/index.css`
- State lokal React menggunakan `useState`, `useEffect`, `useCallback`, dan `useRef`
- Penyimpanan browser: token dan draft KRS pada `localStorage`
- Tidak ada router library; navigasi dilakukan melalui state `view`

### Backend

- Python
- FastAPI
- Uvicorn
- SQLAlchemy 2
- Pydantic dan Pydantic Settings
- JWT melalui python-jose
- Hash password melalui passlib/bcrypt
- Mulai dipenuhi oleh Python 3.12 pada Docker
- Test framework: pytest, httpx/TestClient

### Database dan Deploy

- SQLite untuk pengembangan lokal
- PostgreSQL 16 untuk deployment Docker
- SQLAlchemy `create_all` dan pengecekan penambahan kolom pada startup
- Alembic tersedia, tetapi kode utama membuat/memperbaiki skema melalui `ensure_schema()`
- Docker Compose untuk PostgreSQL, backend, dan frontend
- Docker Compose cloud tersedia sebagai konfigurasi tambahan

### Teknologi dokumen dan OCR

- pypdf untuk PDF berbasis teks
- pdf2image/Poppler untuk merender PDF scan
- pytesseract untuk OCR
- Tesseract bahasa Indonesia dan Inggris
- Pillow untuk pemrosesan gambar
- openpyxl untuk impor/ekspor katalog Excel

## B. Struktur Direktori

```text
.
├── backend/
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── api/routes/
│   │   │   ├── admin.py
│   │   │   ├── auth.py
│   │   │   ├── dosen.py
│   │   │   └── mahasiswa.py
│   │   ├── data/
│   │   │   └── seed_data.py
│   │   ├── services/
│   │   │   ├── course_catalog.py
│   │   │   ├── khs_parser.py
│   │   │   ├── recommendation.py
│   │   │   └── validation.py
│   │   ├── ai_explainer.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── deps.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── seed.py
│   └── tests/
├── frontend/
│   ├── public/
│   └── src/
│       ├── assets/
│       ├── App.jsx
│       ├── App.css
│       ├── index.css
│       └── main.jsx
├── KHS FULL.pdf
├── Prasyarat_Mata_Kuliah_STI_UHAMKA_Updated oke.xlsx
├── docker-compose.yml
├── docker-compose.cloud.yml
├── README.md
└── courserecom.db
```

Direktori dependency dan output lokal juga ada, antara lain `.venv`, `frontend/node_modules`, `frontend/dist`, dan cache pytest. Direktorinya tidak menjadi bagian fungsi sumber.

## C. Daftar Halaman Aplikasi

Navigasi tidak berbasis URL route browser. Semua halaman memakai state `view` pada `App.jsx`.

### Halaman umum/auth

- Masuk
- Daftar mahasiswa

### Halaman mahasiswa

1. Dashboard
2. Kurikulum
3. Upload KHS
4. Riwayat KHS
5. Rekomendasi Mata Kuliah
6. Minat & Profil
7. Tentang
8. Panduan

### Halaman dosen PA

1. Dashboard Dosen PA
2. Bimbingan Mahasiswa
3. Tentang/Panduan

### Halaman admin prodi

1. Dashboard Admin Prodi
2. Manajemen Data
3. Tentang/Panduan

Menu dibentuk berdasarkan role pada frontend. Backend tetap melakukan otorisasi role terpisah untuk endpoint sensitif.

## D–E. Fitur dan Fungsi pada Setiap Halaman

### Masuk

- Form NIM/username dan password.
- Pilihan role hanya pada UI; login backend mengabaikan pilihan role dan menentukan role dari akun database.
- Pemulihan sesi dari token pada `localStorage` melalui `GET /api/auth/me`.
- Tombol daftar mahasiswa membuka formulir registrasi.
- Tombol keluar menghapus token dan state aplikasi.

Status implementasi: terimplementasi dan didukung test API RBAC/autentikasi.

### Daftar mahasiswa

- Input NIM, nama lengkap, password, dan konfirmasi password.
- Frontend menolak password berbeda dari konfirmasi.
- Backend membuat akun role `mahasiswa`, hash password, semester awal 1, SKS lulus 0, dan kuota awal.
- Backend menolak NIM duplikat.

Status implementasi: terimplementasi.

### Dashboard mahasiswa

- Menampilkan identitas dan profil akademik.
- Menampilkan status KHS, semester, IPK, SKS lulus/sisa, dan minat.
- Menampilkan status rencana studi terbaru.
- Menampilkan rekomendasi ringkas.
- Tombol ke unggah KHS bila belum dikonfirmasi.
- Menampilkan ringkasan draft KRS.
- Menentukan tombol rekomendasi berdasarkan status KHS.

### Kurikulum

- Mengambil katalog aktif dari backend.
- Mengelompokkan mata kuliah per semester 1–8.
- Menampilkan kode, nama, SKS, kategori, prasyarat, keterangan, hari, dan waktu.
- Halaman read-only bagi mahasiswa.

### Upload dan koreksi KHS

- Memilih satu PDF atau hingga sepuluh gambar.
- Frontend membatasi jumlah file; backend memvalidasi format dan ukuran.
- Backend membuat pratinjau dan menyimpannya sebagai dokumen berstatus `pending`.
- Pratinjau dapat diedit:
  - NIM, nama, program studi, IPK;
  - nomor dan IP semester;
  - kode, nama, SKS, nilai angka, grade, dan semester mata kuliah;
  - menambah/menghapus mata kuliah dan menambah semester.
- Tombol konfirmasi menyimpan history sebagai `confirmed`.
- Tombol batalkan menghapus pratinjau pending.
- Mengunggah kembali atau menukar file dilakukan setelah pratinjau ada.

Status implementasi: terimplementasi. Parser dan alur preview/konfirmasi memiliki test backend.

### Riwayat KHS

- Menampilkan dokumen KHS berstatus `confirmed`.
- Menampilkan semester, IP semester, kode, nama, SKS, nilai angka, dan grade.
- Tombol mengarahkan ke unggah KHS terbaru.

### Rekomendasi mata kuliah

- Menampilkan kandidat yang lolos aturan prasyarat dan akademik.
- Menampilkan skor, faktor penilaian, alasan, prasyarat, kategori, dan deskripsi.
- Menambahkan mata kuliah valid ke draft KRS lokal.
- Melarang duplikasi dan pengambilan melebihi kuota SKS frontend.
- Menampilkan mata kuliah ditolak beserta alasan.
- Menampilkan mata kuliah wajib diulang pada Semester Antara.
- Draft dapat dihapus satu per satu atau dikosongkan.
- Tombol mengajukan rencana studi ke dosen PA.

Status implementasi: terimplementasi dan dilindungi test backend untuk validasi rekomendasi, kuota, duplikasi, dan status rencana.

### Minat & Profil

- Checkbox untuk Manajemen Sistem Informasi dan Kecerdasan Bisnis.
- Mendukung satu atau kedua minat.
- Mengirim string minat yang dinormalisasi ke backend.

### Dashboard dosen PA

- Menampilkan jumlah mahasiswa, KHS terkonfirmasi, rencana menunggu, dan rencana disetujui.
- Menampilkan rencana terbaru.
- Menampilkan daftar mahasiswa dan status KHS/minat.
- Menampilkan grafik sederhana sebaran peminatan.
- Tombol masuk ke halaman bimbingan.

### Bimbingan Mahasiswa

- Menampilkan semua rencana studi beserta mahasiswa dan mata kuliah.
- Menyetujui rencana.
- Meminta revisi dengan catatan wajib.
- Status disetujui terkunci di backend.

### Dashboard admin

- Menampilkan jumlah mahasiswa, KHS terkonfirmasi, dan dosen PA.
- Menampilkan tabel mahasiswa beserta status KHS.
- Menghapus akun mahasiswa beserta data KHS dan rencana studi melalui konfirmasi browser.
- Menampilkan daftar dosen PA.

### Manajemen Data admin

- Impor katalog Excel/CSV.
- Latih/evaluasi ulang model.
- Tambah mata kuliah.
- Ubah mata kuliah.
- Nonaktifkan mata kuliah (soft delete) dengan konfirmasi browser.
- Menampilkan katalog aktif beserta prasyarat dan jadwal.

### Tentang dan Panduan

- Konten informasional statis.
- Tidak ada interaksi backend.

## F. Alur Kerja Utama

### Alur autentikasi

```text
Pengguna membuka aplikasi
→ Memilih daftar atau masuk
→ Frontend mengirim kredensial ke /api/auth/*
→ Backend memverifikasi password/hash atau membuat akun
→ Backend mengeluarkan JWT
→ Frontend menyimpan token
→ GET /api/auth/me memulihkan profil
→ Navigasi disesuaikan role
```

### Alur KHS

```text
Mahasiswa memilih PDF/gambar
→ Frontend memvalidasi jumlah file
→ Backend memvalidasi format dan 20 MB
→ Parser PDF/OCR menghasilkan metadata, semester, dan mata kuliah
→ Data disimpan sebagai dokumen pending
→ Mahasiswa koreksi pratinjau
→ Backend memvalidasi field dan semester
→ Riwayat lama diganti active history
→ StudentRecord dibuat
→ Profil akademik dan kuota diperbarui
→ Dashboard dan rekomendasi dimuat ulang
```

### Alur rekomendasi

```text
Mahasiswa memiliki KHS confirmed
→ Backend mengumpulkan StudentRecord dan katalog
→ Menentukan semester target
→ Menghitung IPK/SKS/prasyarat, pola peer, minat, dan katalog
→ Kandidat valid dan ditolak dipisahkan
→ Mata kuliah gagal diprioritaskan untuk Semester Antara
→ Frontend menampilkan skor dan alasan
```

Skor gabungan memakai lima faktor konfigurasi: mahasiswa serupa, riwayat akademik, minat, kurikulum, dan pola mata kuliah.

### Alur draft dan pengajuan KRS

```text
Mahasiswa memilih rekomendasi
→ Frontend menyimpan draft ke state dan localStorage
→ Frontend memvalidasi duplikasi dan batas SKS
→ POST /api/mahasiswa/rencana-studi
→ Backend menghitung ulang rekomendasi dan kuota
→ StudyPlan disimpan berstatus pending
→ Dosen PA melihat rencana
→ Dosen menyetujui atau meminta revisi
```

Database juga mengunci maksimal satu `pending` per mahasiswa melalui indeks parsial. Frontend melakukan penguncian pengiriman ganda pada instance React.

## G. Hubungan Frontend, Backend, API, dan Database

Frontend menaruh semua pemanggilan API pada helper `apiRequest()` di `frontend/src/App.jsx`.

- Menambahkan `Content-Type: application/json`, kecuali `FormData`.
- Menambahkan bearer token dari `localStorage` bila ada.
- Membaca dan memparse JSON.
- Meneruskan pesan `detail` atau `message` dari API sebagai error.

Tabel API utama:

| Area | Endpoint | Fungsi |
|---|---|---|
| Auth | `/api/auth/register`, `/api/auth/login`, `/api/auth/me` | Daftar, login, sesi |
| Mahasiswa | `/api/mahasiswa/kurikulum` | Katalog aktif |
| Mahasiswa | `/api/mahasiswa/khs/*` | Preview, konfirmasi, daftar, hapus KHS |
| Mahasiswa | `/api/mahasiswa/profil` | Lihat/ubah minat |
| Mahasiswa | `/api/mahasiswa/rekomendasi`, `/api/rekomendasi` | Hasil rekomendasi |
| Mahasiswa | `/api/mahasiswa/rencana-studi` | Daftar/kirim KRS |
| Dosen | `/api/dosen/mahasiswa`, `/api/dosen/rencana-studi*` | Data bimbingan dan review |
| Admin | `/api/admin/dashboard`, `/api/admin/students/*` | Ringkasan dan hapus mahasiswa |
| Admin | `/api/admin/courses*`, `/api/admin/import-data` | CRUD/import katalog |
| Admin | `/api/admin/model/*`, `/api/admin/evaluasi` | Training dan evaluasi model |
| Health | `/api/health` | Status aplikasi |

## H. Model Database dan Relasi

### `users`

- `id`
- `nim`, unik
- `full_name`
- `role`
- `email`, opsional
- `password_hash`
- `is_active`
- `semester`
- `ipk`
- `sks_lulus`
- `sks_sisa`
- `kuota_sks`
- `interests`

Kolom `nim` dipakai sebagai subject JWT. Relasi ke `student_records`.

### `courses`

- `id`
- `code`, unik
- `name`
- `sks`
- `semester`
- `available_semesters`
- `category`
- `description`
- `prerequisite_text`
- `day`
- `time`
- `prerequisite_codes`
- `is_active`

`is_active=false` adalah soft delete. Kode akademik direferensikan secara tekstual oleh `prerequisite_codes`, bukan foreign-key.

### `student_records`

- `id`
- `student_id`
- `course_code`
- `grade`
- `semester`
- `course_name`
- `sks`
- `numeric_grade`
- `grade_point`
- `is_passed`
- Foreign key ke `users.id`

Memuat riwayat semua mata kuliah KHS yang dikonfirmasi.

### `khs_documents`

- `id`
- `student_id`
- `filename`
- `sha256`
- `status`: `pending`, `confirmed`, atau `superseded`
- `parsed_data` berupa JSON terserial
- `created_at`

Foreign key ke `users.id`, namun tidak didefinisikan cascade database.

### `study_plans`

- `id`
- `student_id`
- `semester`
- `courses_json` berupa JSON terserial
- `status`
- `advisor_note`
- `reviewer_id`
- `created_at`
- `updated_at`

`student_id` dan `reviewer_id` adalah foreign key ke `users.id`. Paling banyak satu `pending` per mahasiswa dijamin indeks parsial pada SQLite/PostgreSQL.

### `recommendation_cache`

- `id`
- `student_id`
- `course_code`
- `score`
- `reasons`

Model tersedia tetapi audit kode tidak menemukan jalur aktif yang menulis atau membacanya pada endpoint saat ini.

### `recommendation_model_versions`

- `id`
- `version`
- `method`
- `dataset_size`
- `metrics` JSON
- `trained_at`

Digunakan untuk menyimpan versi dan metrik hasil training.

### Relasi dan penyimpanan terserial

- `student_records` memiliki relasi ORM ke `users`.
- Mata kuliah pada `study_plans` disimpan JSON, bukan tabel child atau tabel relasi.
- Data hasil parser KHS disimpan JSON pada `khs_documents`.
- Prasyarat antar mata kuliah disimpan sebagai kode teks di kolom katalog.

## I. Integrasi Eksternal

### Terintegrasi secara nyata

- PostgreSQL
- Docker Hub image PostgreSQL
- Tesseract OCR dan Poppler melalui OS/container backend
- Penyimpanan filesystem/database lokal untuk dokumen metadata dan file SQLite
- Supabase/PostgreSQL cloud sebagai opsi deployment

### Integrasi kode tersedia tetapi tidak terbukti dipanggil

- Google Gemini API melalui `backend/app/ai_explainer.py`
- `generate_explanation()` tidak ditemukan dipanggil dari service rekomendasi atau route.
- Jika API key tidak ada, kode menghasilkan penjelasan fallback lokal.

Tidak ditemukan integrasi pembayaran, gateway, email/SMS, QRIS, vendor warung, atau layanan autentikasi eksternal.

## J. Fitur yang Sudah Berfungsi Berdasarkan Bukti

Status berikut dibedakan berdasarkan implementasi dan hasil test:

### Terimplementasi dan teruji backend

- Registrasi/login/JWT dan pemisahan role.
- RBAC route mahasiswa, dosen, dan admin.
- Preview dan konfirmasi KHS sintetis.
- Parser KHS teks/gambar.
- Filter dan aturan rekomendasi.
- Validasi kuota SKS.
- Pengajuan dan penguncian rencana studi pending.
- Index duplikasi pengajuan pending.
- Review dosen PA.
- CRUD mata kuliah dan soft delete.
- Impor katalog Excel/CSV.
- Validasi database dan threshold kuota.

### Terimplementasi tetapi belum ada test E2E/frontend otomatis

- Navigasi seluruh halaman React.
- Interaksi tombol tambah/hapus draft.
- Toast/loading.
- Navigasi responsif mobile.
- Form koreksi KHS.
- Refresh status rencana.
- UI dashboard admin/dosen/mahasiswa.
- Impor file dari browser.

### Hasil verifikasi terakhir

- Suite backend penuh: 34 test lulus pada audit terakhir.
- Frontend lint: lulus.
- Frontend production build: lulus.
- Tidak ada browser E2E yang dibuktikan dari repository.

## K. Fitur Belum Selesai atau Bermasalah

### Ketidaksesuaian workspace

- Aplikasi yang tersedia adalah CourseRecom, bukan WarungPintar.
- Dokumentasi prompt WarungPintar tidak cocok dengan kode dan halaman aktual.

### Fungsi yang belum terintegrasi

- AI explainer Gemini memiliki implementasi tetapi tidak dipanggil.
- `RecommendationCache` memiliki model tetapi tidak terlihat dipakai aktif.
- Evaluasi model memiliki API dan struktur data, tetapi UI admin tidak menampilkan evaluasi versi secara terpisah.

### Konten placeholder

- Halaman Tentang menyebut deskripsi inti, tetapi beberapa isi masih bersifat placeholder.
- Page title dan README adalah CourseRecom.

### Potensi proses manual

- Manajemen akun dosen tidak memiliki endpoint/frontend CRUD di halaman admin saat ini.
- Admin hanya dapat melihat dosen PA; tidak ada tombol tambah atau edit dosen yang terimplementasi.

## L. Potensi Bug dan Risiko Teknis

1. **Pemilihan role pada login menipu**

   Pilihan role dikirim tidak sama sekali ke backend. Backend mengambil role dari akun. Pemilihan "Admin" lalu memasukkan akun mahasiswa tetap akan masuk sebagai mahasiswa.

2. **Draft KRS hanya lokal browser**

   Draft disimpan di `localStorage` dan tidak dikunci per akun. Setelah logout/login akun lain pada browser yang sama, kode saat ini tidak secara jelas menghapus `courseRecomDraft`; risiko draft antar-akun.

3. **State draft tidak diverifikasi saat program rekomendasi berubah**

   Draft disimpan lokal dan hanya divalidasi saat submit. Perubahan KHS/katalog dapat membuat draft lama tetap ada hingga submit.

4. **Konfigurasi indeks duplikat untuk database lama**

   Indeks partial dibuat oleh model dan `ensure_schema()`. Jika database lama sudah memiliki beberapa `pending` untuk mahasiswa yang sama, startup dapat gagal saat membuat indeks unik.

5. **Paket indeks PostgreSQL**

   `ensure_schema()` selalu menjalankan SQL SQLite/PostgreSQL tertentu dan harus dipastikan kompatibel dengan seluruh versi deployment PostgreSQL yang didukung.

6. **JSON tersimpan sebagai TEXT**

   KHS dan rencana studi disimpan sebagai JSON string tanpa validasi database struktural. Data rusak dapat membuat endpoint gagal saat `json.loads`.

7. **Penghapusan user manual**

   Penghapusan mahasiswa menghapus beberapa tabel relasional tetapi tidak menghapus semua kemungkinan referensi yang tidak ditangani oleh model.

8. **Transaksi tidak atomik pada beberapa alur**

   Konfirmasi KHS melakukan beberapa penghapusan dan insert sebelum satu commit. SQLAlchemy biasanya rollback pada exception, tetapi error HTTP atau pemrosesan koneksi perlu dipastikan konsisten.

9. **Parsing PDF/OCR sensitif**

   OCR dapat menghasilkan hasil salah. Validasi frontend dan backend ada, tetapi kualitas bergantung pada mesin, bahasa, resolusi, dan format KHS.

10. **Frontend monolitik**

    Seluruh UI, API calls, state, dan rendering berada pada satu `App.jsx` sekitar 1900 baris. Risiko regresi tinggi saat perubahan fitur.

11. **Tidak ada routing URL**

    Refresh atau link langsung tidak membuka halaman tertentu; halaman ditentukan state awal `dashboard`.

12. **Pencegahan race belum lengkap**

    Lock frontend mencegah double-click pada instance React. Lock database baru mencegah konflik lintas sesi/client. Tombol submit juga dinonaktifkan saat status frontend pending.

13. **Token JWT di `localStorage` rentan XSS**

    XSS pada frontend dapat mengambil token. Tidak ada mekanisme session cookie HTTP-only pada arsitektur ini.

14. **Data demo dan secret default**

    Project menampilkan akun demo untuk development. Secret default harus tidak dipakai di produksi. Audit tidak membaca isi `.env`.

15. **Status revision**

    Student dapat mengajukan rencana baru karena endpoint hanya memblokir pending dan frontend juga hanya memblokir pending; review sebelumnya pada dasarnya tetap tersimpan. Perubahan semester dan beberapa rencana revision perlu diperjelas aturan bisnis jika satu draft aktif diharapkan.

16. **Dosen dapat meninjau semua mahasiswa**

    Tidak ada model relasi dosen-mahasiswa atau assignment PA pada backend. `dosen` dapat melihat semua rencana.

17. **Tidak ada test frontend otomatis**

    Build/lint dapat lolos meskipun interaksi button/modal bermasalah saat runtime.

## M. File Penting per Fitur

### Autentikasi

- `frontend/src/App.jsx`
- `backend/app/api/routes/auth.py`
- `backend/app/deps.py`
- `backend/app/schemas.py`
- `backend/app/models.py`

### Navigasi dan dashboard

- `frontend/src/App.jsx`
- `frontend/src/App.css`
- `frontend/src/index.css`

### KHS dan OCR

- `frontend/src/App.jsx`
- `backend/app/api/routes/mahasiswa.py`
- `backend/app/services/khs_parser.py`
- `backend/app/schemas.py`
- `backend/tests/test_khs_workflow.py`
- `backend/tests/test_khs_parser.py`

### Kurikulum

- `frontend/src/App.jsx`
- `backend/app/api/routes/mahasiswa.py`
- `backend/app/models.py`
- `backend/app/services/course_catalog.py`
- `backend/tests/test_course_catalog.py`

### Rekomendasi

- `frontend/src/App.jsx`
- `backend/app/services/recommendation.py`
- `backend/app/api/routes/mahasiswa.py`
- `backend/app/services/validation.py`
- `backend/app/ai_explainer.py`
- `backend/tests/test_khs_workflow.py`
- `backend/tests/test_validation.py`

### Draft dan review KRS

- `frontend/src/App.jsx`
- `backend/app/api/routes/mahasiswa.py`
- `backend/app/api/routes/dosen.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/tests/test_khs_workflow.py`
- `backend/tests/test_api_rbac.py`

### Admin dan impor katalog

- `frontend/src/App.jsx`
- `backend/app/api/routes/admin.py`
- `backend/app/services/course_catalog.py`
- `backend/app/models.py`
- `backend/tests/test_course_catalog.py`
- `backend/tests/test_api_rbac.py`

### Database dan startup

- `backend/app/database.py`
- `backend/app/models.py`
- `backend/app/main.py`
- `backend/app/seed.py`
- `backend/app/data/seed_data.py`

### Konfigurasi dan deployment

- `backend/app/config.py`
- `backend/requirements.txt`
- `frontend/package.json`
- `docker-compose.yml`
- `docker-compose.cloud.yml`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `README.md`

## Keterbatasan Audit

- Tidak ada repository Git pada workspace, sehingga perbedaan perubahan belum tersimpan tidak dapat diaudit.
- Browser tidak dibagikan untuk audit visual atau browser automation.
- Tidak ada deployment aktif yang diaudit pada server eksternal.
- Isi file rahasia tidak dibaca.
- Aplikasi WarungPintar tidak ada pada workspace terbuka.
- Tidak ada bukti otomatis bahwa seluruh tombol UI berhasil di browser.
- Integrasi Gemini tidak dapat dinilai sampai API/key dan response deployment tersedia.
