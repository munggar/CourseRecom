# Hasil Pemeriksaan Teknis CourseRecom

**Tanggal pemeriksaan:** 10 November 2026  
**Cakupan:** endpoint dan akses peran, database, dokumen, OCR, Gemini, startup, persistence, serta tes backend.

## Ringkasan

| Area | Hasil | Catatan utama |
|---|---|---|
| Endpoint API dan role access control | Terpasang; pemeriksaan statis selesai | Semua route admin dibatasi untuk admin; route dosen dan mahasiswa memakai guard peran. Tes tidak menguji setiap kombinasi route/peran. |
| PostgreSQL dan kompatibilitas koneksi | Konfigurasi tersedia; koneksi nyata belum diverifikasi | Driver psycopg tersedia dan URL PostgreSQL dinormalisasi. Docker daemon tidak tersedia; tes migrasi menggunakan SQLite. |
| Penyimpanan PDF, KHS, dan KRS resmi | Tersimpan di database | Konten disimpan sebagai BLOB; bukan di filesystem atau object storage. |
| Poppler dan Tesseract | Ada pada image backend Docker | Binary tersebut tidak ditemukan pada host lokal yang diperiksa, sehingga OCR scan belum dapat dijalankan langsung dari host. |
| Gemini | Opsional | Tanpa API key, penjelasan menggunakan fallback lokal. |
| Startup dan health check | Migrasi/seed berjalan saat startup; health endpoint tersedia | `/api/health` tidak memeriksa koneksi database setelah aplikasi berjalan. |
| Persistence container | Disiapkan | Compose lokal menggunakan volume PostgreSQL; deployment cloud mengandalkan database eksternal yang persisten. |
| Tes alur dan migrasi | **72 lulus, 1 gagal** | Kegagalan pada tes workflow KPRS; tes migrasi dan tes KHS/KRS resmi yang dijalankan lulus. |

## Rincian

### 1. Endpoint API dan role access control

Pemeriksaan statis pada empat router menemukan **64 endpoint**:

- **Admin (27):** seluruh route `/admin/...` mensyaratkan role `admin`.
- **Dosen (6):** lima route mensyaratkan role `dosen`; `GET /dosen/mahasiswa` mengizinkan `dosen` dan `admin`.
- **Mahasiswa (25):** route mahasiswa mensyaratkan role `mahasiswa`, kecuali dua route verifikasi KRS resmi yang memang publik dan divalidasi dengan token verifikasi.
- **Auth (6):** registrasi dan login bersifat publik; profil, `/auth/me`, dan logout memerlukan pengguna terautentikasi.
- Health check `/api/health` juga publik.

`get_current_user` memvalidasi JWT, status akun, role saat ini, serta versi token. Endpoint dokumen/KRS mahasiswa memfilter kepemilikan dokumen/rencana; tes RBAC menguji penolakan akses lintas mahasiswa. Tes juga memeriksa akses mahasiswa terhadap route admin. Cakupan tersebut memberi bukti atas pola kontrol akses, tetapi **bukan** pengujian positif/negatif lengkap untuk setiap endpoint dan semua kombinasi role.

Referensi: [routes](../backend/app/api/routes), [deps.py](../backend/app/deps.py), [test_api_rbac.py](../backend/tests/test_api_rbac.py).

### 2. PostgreSQL dan kompatibilitas koneksi

- Dependency `psycopg[binary]` dipasang untuk koneksi PostgreSQL.
- URL `postgres://` dan `postgresql://` dinormalisasi ke driver `postgresql+psycopg`.
- Docker Compose lokal menjalankan PostgreSQL 16; contoh konfigurasi cloud mendukung PostgreSQL eksternal, termasuk Supabase dan opsi TLS `sslmode=require`.
- Backend menggunakan SQLite secara default untuk pengembangan lokal, dan secara khusus mengalihkan hostname Docker `db` ke SQLite bila backend dijalankan langsung di host.
- Unit test memeriksa normalisasi URL PostgreSQL, tetapi migrasi dan seluruh workflow pada suite ini diuji dengan SQLite, bukan server PostgreSQL.

**Belum diverifikasi:** koneksi langsung ke PostgreSQL, TLS/SSL provider, serta migrasi pada PostgreSQL nyata. Percobaan Docker tidak dapat dilanjutkan karena Docker daemon/engine tidak aktif pada mesin pemeriksaan.

Referensi: [requirements.txt](../backend/requirements.txt), [database.py](../backend/app/database.py), [config.py](../backend/app/config.py), [docker-compose.yml](../docker-compose.yml), [docker-compose.cloud.yml](../docker-compose.cloud.yml), [test_database_config.py](../backend/tests/test_database_config.py), [test_migrations.py](../backend/tests/test_migrations.py).

### 3. Penyimpanan dokumen PDF, KHS, dan KRS resmi

- File KHS yang diunggah, data hasil parsing, dan status konfirmasi disimpan pada tabel `khs_documents`; batas unggahan KHS adalah 20 MB.
- Dokumen KRS yang diunggah disimpan pada tabel `krs_documents`; batas unggahan KRS adalah 10 MB.
- PDF KRS resmi beserta token verifikasi, hash, dan waktu penerbitan disimpan pada tabel `official_krs_documents`.
- Kolom konten dokumen menggunakan BLOB database (`LargeBinary`), sehingga dokumen mengikuti persistence dan backup database. Tidak ditemukan konfigurasi object storage atau media volume terpisah.
- URL verifikasi QR memakai token bertanda tangan; tes memeriksa token tamper dan penolakan dokumen KRS resmi yang sudah tidak sesuai dengan rencana studi terbaru.

**Implikasi operasional:** ukuran database bertambah seiring unggahan dokumen. Atur kapasitas, retensi, dan backup untuk database; pastikan provider database tidak menghapus data saat container aplikasi diganti.

Referensi: [models.py](../backend/app/models.py), [mahasiswa.py](../backend/app/api/routes/mahasiswa.py), [official_krs.py](../backend/app/services/official_krs.py), [test_official_krs.py](../backend/tests/test_official_krs.py).

### 4. Dependency OCR: Poppler dan Tesseract

Image backend Docker menginstal `poppler-utils`, `tesseract-ocr`, dan `tesseract-ocr-ind`. Parser memanggil Poppler untuk mengubah halaman PDF menjadi gambar dan Tesseract dengan bahasa `ind+eng` untuk OCR.

Pada host lokal yang diperiksa, modul Python `pdf2image` dan `pytesseract` tersedia, tetapi executable `pdftoppm`, `pdftocairo`, dan `tesseract` tidak ditemukan pada PATH. Karena itu:

- OCR **tersedia dalam image Docker** berdasarkan definisi Dockerfile.
- OCR untuk PDF scan/gambar **belum siap pada eksekusi langsung di host ini** sampai binary Poppler dan Tesseract, termasuk data bahasa Indonesia dan Inggris, dipasang dan dapat ditemukan oleh proses.
- Tes parser yang dijalankan menggunakan mock untuk jalur OCR; tes tersebut tidak membuktikan keberhasilan OCR end-to-end dengan executable sistem.

PDF yang teksnya dapat dipilih dapat diekstrak tanpa OCR; PDF scan dan gambar membutuhkan dependency sistem tersebut.

Referensi: [backend Dockerfile](../backend/Dockerfile), [root Dockerfile](../../Dockerfile), [khs_parser.py](../backend/app/services/khs_parser.py), [test_khs_parser.py](../backend/tests/test_khs_parser.py).

### 5. Kebutuhan API Gemini

`GEMINI_API_KEY` tidak wajib untuk menjalankan backend. Jika tidak diisi, aplikasi menghasilkan penjelasan fallback lokal; jika tersedia, backend memanggil Gemini menggunakan model dari `GEMINI_MODEL` (default `gemini-2.0-flash-lite`).

Dengan demikian, Gemini hanya diperlukan untuk penjelasan rekomendasi berbasis layanan eksternal. Tanpa key atau ketika layanan tidak tersedia, fitur penjelasan tetap memberi fallback, tetapi hasilnya bukan keluaran Gemini. Ketersediaan jaringan, kuota, dan validitas key tidak diuji dalam pemeriksaan ini.

Referensi: [ai_explainer.py](../backend/app/ai_explainer.py), [config.py](../backend/app/config.py), [env.cloud.example](../env.cloud.example).

### 6. Startup backend, konfigurasi environment, dan health check

- FastAPI menjalankan migrasi Alembic hingga `head`, lalu seed katalog/akun yang diizinkan, pada startup aplikasi.
- Docker Compose lokal menunggu health check PostgreSQL (`pg_isready`) sebelum memulai backend.
- Konfigurasi production memvalidasi secret JWT/QR, seed akun demo, dan URL HTTPS publik untuk verifikasi KRS.
- Render diarahkan ke `/api/health`.
- Endpoint health mengembalikan status statis aplikasi. Ia tidak melakukan query database, sehingga **tidak cukup untuk mendeteksi koneksi database yang terputus setelah startup**. Kegagalan migrasi saat startup memang menghalangi startup, tetapi health check berjalan tidak membuktikan database tetap sehat.

**Saran:** tambahkan readiness check yang menguji koneksi database secara ringan bila platform perlu membedakan aplikasi hidup dari database siap.

Referensi: [main.py](../backend/app/main.py), [config.py](../backend/app/config.py), [database.py](../backend/app/database.py), [docker-compose.yml](../docker-compose.yml), [render.yaml](../../render.yaml).

### 7. Persistence database saat container restart

- Compose lokal menyimpan data PostgreSQL pada named volume `pgdata`, sehingga restart/recreate container biasa tidak menghapus database.
- Konfigurasi cloud tidak menjalankan container database; persistence disediakan oleh database PostgreSQL eksternal.
- Dokumen ikut tersimpan di database yang sama. Tidak ada filesystem dokumen aplikasi yang perlu dipertahankan secara terpisah.
- Menghapus volume database secara eksplisit, misalnya dengan `docker compose down -v`, tetap akan menghapus data lokal. Backup tetap diperlukan.

### 8. Hasil tes alur mahasiswa, dosen, admin, dan migrasi

Perintah yang dijalankan:

```text
cd CourseRecomV2/backend
python -m pytest -q
```

Hasil:

```text
72 passed, 1 failed
```

Kegagalan:

- `tests/test_kprs_workflow.py::test_kprs_revalidates_reserves_capacity_and_releases_cancelled_seats`
- Pengajuan KPRS pertama diharapkan sukses (`201`), tetapi API menolak dengan `422`: `Mata kuliah wajib harus tetap ada di KRS: <kode mata kuliah>`.
- Validator KRS memang mengharuskan seluruh mata kuliah yang ditandai wajib dalam rekomendasi tetap dipilih. Pesan kegagalan menunjukkan course awal dalam fixture tes dianggap wajib, sedangkan alur tes mencoba menggantinya.
- Ini merupakan konflik antara fixture/ekspektasi tes dengan aturan wajib yang aktif; hasil ini belum cukup untuk menyimpulkan apakah aturan produk atau ekspektasi tes yang perlu diubah. Perlu diputuskan apakah KPRS boleh menghapus mata kuliah wajib.

Tes migrasi yang tersedia memeriksa migrasi fresh yang dapat diulang, pelestarian histori legacy, constraint, dan diagnostik orphan pada SQLite. Tes KHS, dokumen KRS, KRS resmi, RBAC, dan sebagian alur dosen/admin juga ada. Namun, karena satu tes workflow gagal dan database PostgreSQL tidak tersedia, alur lengkap setelah migrasi pada PostgreSQL nyata **belum dapat dinyatakan lulus**.

Referensi: [test_kprs_workflow.py](../backend/tests/test_kprs_workflow.py), [academic.py](../backend/app/services/academic.py), [test_migrations.py](../backend/tests/test_migrations.py), [test_khs_workflow.py](../backend/tests/test_khs_workflow.py), [test_api_rbac.py](../backend/tests/test_api_rbac.py).

## Tindak lanjut yang disarankan

1. Putuskan aturan KPRS untuk penggantian mata kuliah wajib; selaraskan aturan atau fixture dan tambahkan tes regresi.
2. Jalankan migrasi dan smoke test dengan PostgreSQL sungguhan sebelum deployment.
3. Uji jalur OCR end-to-end pada image backend Docker dengan PDF scan dan gambar, termasuk bahasa `ind+eng`.
4. Pertimbangkan readiness endpoint database dan pastikan backup/retensi database mencakup dokumen.
