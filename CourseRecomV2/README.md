# CourseRecom

CourseRecom membantu mahasiswa menyusun rencana mata kuliah semester berikutnya dari riwayat KHS. Rekomendasi menggunakan gabungan minat, nilai akademik, pola pengambilan mata kuliah mahasiswa serupa, dan kurikulum; rule engine memblokir kandidat yang melanggar prasyarat, pengulangan mata kuliah yang sudah lulus, atau kuota SKS.

## Menjalankan dan deploy

### Deployment Render dari repository root

Repository menyertakan `Dockerfile`, `Dockerfile.frontend`, dan `render.yaml` pada root agar aplikasi dapat dipilih meskipun kode proyek berada di folder `CourseRecomV2`.

- Service backend: Dockerfile `Dockerfile`.
- Service frontend: Dockerfile `Dockerfile.frontend`.
- Jangan set Root Directory ke `CourseRecomV2` untuk Dockerfile root.

Untuk frontend production, isi `VITE_API_BASE_URL` dan `API_PROXY_TARGET` dengan URL backend HTTPS berakhiran `/api` bila API dan frontend memakai domain berbeda.

Jalankan stack lokal dengan Docker:

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend dan API docs: http://localhost:8000/docs
- PostgreSQL lokal Docker: localhost:5432

Salin `.env.example` ke `.env` untuk development lokal. Akun demo hanya di-seed pada environment `development`/`testing`; jangan gunakan konfigurasi development di production. Deployment publik wajib memakai `ENVIRONMENT=production`, `SEED_DEMO_USERS=false`, `VITE_ENVIRONMENT=production`, `JWT_SECRET` dan `QR_VERIFICATION_SECRET` acak yang berbeda (masing-masing minimal 32 karakter), serta `PUBLIC_API_BASE_URL` HTTPS publik berakhiran `/api`. Atur `FRONTEND_URL` ke origin frontend dan `VITE_API_BASE_URL` ke URL API publik yang sama. URL API frontend dan label environment dimasukkan saat image frontend dibangun, jadi ubah keduanya lalu jalankan ulang `docker compose build frontend`.

Pengaturan utama:

```env
JWT_SECRET=replace-with-a-long-random-secret
QR_VERIFICATION_SECRET=replace-with-a-different-long-random-secret
POSTGRES_PASSWORD=replace-with-a-strong-database-password
FRONTEND_URL=https://course.example.edu
PUBLIC_API_BASE_URL=https://api.example.edu/api
VITE_API_BASE_URL=https://api.example.edu/api
RECOMMENDATION_WEIGHTS={"similar_students":0.30,"academic_history":0.25,"interest":0.20,"curriculum":0.15,"course_pattern":0.10}
PASSING_GRADES=A,A-,B+,B,B-,C+,C,C-
TOTAL_CURRICULUM_SKS=144
```

Secara default, Docker Compose menggunakan PostgreSQL lokal dalam container. Saat backend dijalankan langsung di luar Docker, `DATABASE_URL` dapat memakai SQLite untuk pengembangan lokal.

### PostgreSQL cloud gratis (Supabase)

Aplikasi menggunakan SQLAlchemy dan PostgreSQL; Supabase dapat dipakai sebagai database cloud tanpa mengubah model atau endpoint. Kredensial database hanya dipasang pada backend—jangan masukkan `DATABASE_URL` ke frontend atau commit ke repository.

1. Buat proyek PostgreSQL di [Supabase](https://supabase.com/dashboard). Salin connection string dari **Connect**. Untuk backend hosting yang hanya mendukung IPv4, pilih **Session pooler**; gunakan detail host, port, dan user yang diberikan dashboard. Supabase Free menyediakan database 500 MB dan dapat menjeda proyek setelah satu minggu tanpa aktivitas, jadi periksa batas terbaru sebelum penggunaan produksi.
2. Salin `env.cloud.example` menjadi `env.cloud`, lalu isi `DATABASE_URL` dengan connection string proyek. Format `postgresql://` Supabase didukung dan otomatis diarahkan ke driver psycopg yang sudah dipasang. Gunakan koneksi TLS (`sslmode=require`) dan URL-encode karakter khusus pada password.
3. Isi `JWT_SECRET` dengan nilai acak yang kuat, `FRONTEND_URL` dengan origin frontend, serta `VITE_API_BASE_URL` dengan URL backend berakhiran `/api`. Untuk menjalankan container aplikasi memakai database Supabase:

   ```powershell
   Copy-Item env.cloud.example env.cloud
   # Edit env.cloud dengan kredensial dan URL deployment Anda.
   docker compose --env-file env.cloud -f docker-compose.cloud.yml up --build
   ```

   Konfigurasi cloud ini tidak membuat container database lokal. Deploy API dan frontend ke penyedia hosting yang dipilih dengan environment variable yang sama; `VITE_API_BASE_URL` harus ditetapkan saat image frontend dibangun.
4. `env.cloud.example` memakai `ENVIRONMENT=production` dan `SEED_DEMO_USERS=false`, sehingga akun demo/password publik tidak dibuat dan login dengan kredensial demo bawaan ditolak. Isi `PUBLIC_API_BASE_URL` dengan URL API HTTPS publik berakhiran `/api`; URL ini yang ditanamkan ke QR, bukan hostname internal Docker. Saat database masih kosong, `BOOTSTRAP_ADMIN_NIM`, `BOOTSTRAP_ADMIN_NAME`, dan `BOOTSTRAP_ADMIN_PASSWORD` membuat satu akun admin awal. Simpan password itu sebagai secret hosting dan hapus/nonaktifkan nilainya sesudah admin berhasil dibuat. Katalog mata kuliah awal tetap di-seed otomatis.

Backend menjalankan migrasi Alembic saat startup. Migrasi mempertahankan histori yang ada dan berhenti dengan diagnostik jika menemukan foreign key orphan atau beberapa KRS pending yang melanggar constraint unik; perbaiki/backup database sebelum retry, jangan hapus histori untuk memaksa migrasi. Baseline migration tidak menyediakan downgrade otomatis. Uji dan backup setiap database lama sebelum production deployment; data dari PostgreSQL/SQLite lain tidak otomatis dipindahkan.

Supabase Free saat ini mencantumkan batas 500 MB dan jeda setelah satu minggu tidak aktif: [harga/paket Supabase](https://supabase.com/pricing). Petunjuk connection string dan pilihan koneksi IPv4/IPv6 ada di [dokumentasi koneksi database Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).

## Akun demo

- Mahasiswa: `2203001` / `password123`
- Dosen PA: `pa001` / `password123`
- Admin Prodi: `admin` / `password123`

Mahasiswa baru dapat mendaftar dari halaman masuk menggunakan NIM, nama lengkap, dan password minimal 8 karakter. Pendaftaran publik hanya membuat akun dengan peran mahasiswa; akun dosen PA dan admin tetap dikelola oleh administrator.

## Alur KHS mahasiswa

1. Mahasiswa masuk dan memilih **Upload KHS**.
2. Unggah satu PDF lengkap atau maksimal 10 foto halaman KHS berformat JPG, PNG, WEBP, TIFF, atau BMP (total maksimal 20 MB). Backend memeriksa format dan ukuran, mengekstrak teks atau menjalankan OCR lokal, lalu membentuk pratinjau per semester.
3. Periksa/koreksi NIM, nama, program studi, IPK, IP semester, kode/nama mata kuliah, SKS, nilai, dan grade. Data yang belum terdeteksi dapat dilengkapi; mata kuliah atau semester juga dapat ditambahkan.
4. Pilih konfirmasi untuk menyimpan. Sebelum konfirmasi, isi hasil ekstraksi hanya berstatus `pending` dan belum masuk ke riwayat akademik. Konfirmasi berikutnya mengganti riwayat aktif dengan KHS lengkap terbaru.
5. Semester terakhir diambil dari semester tertinggi yang berisi mata kuliah; target rekomendasi adalah semester berikutnya.

Parser mendukung PDF KHS dengan teks yang dapat dipilih, termasuk format `Semester N` dan laporan **Histori Nilai Mahasiswa UHAMKA** dengan baris nomor, kode, nama mata kuliah, SKS, nilai, serta kelompok semester `Gasal`/`Genap`. Semester pada laporan tersebut ditentukan dari penanda tahun akademik; kode mata kuliah numerik dan nilai OCR seperti `Cc` yang merepresentasikan `C` juga ditangani. PDF scan dan gambar diproses oleh Tesseract lokal dengan bahasa Indonesia/Inggris. OCR gambar mencoba beberapa segmentasi tabel/teks dengan praproses kontras dan ketajaman, lalu memilih hasil dengan baris mata kuliah yang paling dikenali. Gambar dibatasi maksimal 12 megapiksel per halaman. Foto sebaiknya tegak, tajam, tidak terpotong, dan menampilkan seluruh tabel dengan pencahayaan rata. Template dokumen kampus dan kualitas foto dapat berbeda; karena itu hasilnya harus selalu ditinjau, dan dokumen yang tidak dapat dikenali akan ditolak dengan petunjuk untuk mengambil ulang foto, bukan disimpan sebagai riwayat yang seolah valid. Berkas asli tidak disimpan; aplikasi menyimpan hash dokumen, hasil ekstraksi, dan riwayat akademik yang dikonfirmasi.

## Rekomendasi dan aturan akademik

- Mata kuliah kandidat berasal dari katalog aktif yang dikelola admin. Semester yang sama pada beberapa periode tetap didukung untuk mata kuliah pilihan.
- Rule engine menetapkan grade A, B, C, dan D sebagai lulus; grade di bawah D tidak lulus. Prasyarat diselesaikan berdasarkan riwayat grade, termasuk normalisasi kode yang memiliki nol ganda. Mata kuliah yang belum lulus ditampilkan sebagai wajib diulang pada Semester Antara setelah semester genap, bukan sebagai rekomendasi semester reguler.
- Batas pengambilan per semester mengikuti IPK: IPK ≥ 3,35 mendapat maksimum 24 SKS; IPK ≥ 3,00 dan < 3,35 maksimum 22 SKS; IPK < 3,00 maksimum 20 SKS. Jika IPK belum tersedia, batas konservatif 20 SKS diterapkan. Aturan ini divalidasi pada rekomendasi dan saat pengajuan KRS ke dosen PA.
- IPK menggunakan satu percobaan terbaru per mata kuliah, termasuk jika nilai terbaru gagal; SKS lulus dihitung sekali per mata kuliah jika pernah lulus. Draft, pengajuan, persetujuan, serta perubahan KPRS divalidasi ulang terhadap prasyarat, semester, duplikasi, batas SKS, nilai lulus terdahulu, dan kapasitas. Pengajuan KPRS pending mereservasi kursi untuk mata kuliah tambahan; mahasiswa dapat membatalkan pengajuan pending.
- Prasyarat, kategori, dan keterangan dari katalog ditampilkan pada rekomendasi mahasiswa.
- Halaman Minat & Profil hanya menyediakan peminatan Manajemen Sistem Informasi dan Kecerdasan Bisnis. Peminatan dicocokkan dengan kategori peminatan terkait pada katalog dan memengaruhi skor rekomendasi; format minat lama yang relevan tetap dikenali.
- Dashboard Dosen PA menampilkan akun mahasiswa dari database beserta status KHS dan sebaran dua peminatan yang dihitung dari profil terdaftar; tidak ada tombol halaman terpisah atau statistik demo.
- Mahasiswa dapat mengajukan mata kuliah rekomendasi valid dari draft KRS ke dosen PA. Halaman **Bimbingan Mahasiswa** memuat semua pengajuan, alasan rekomendasi, prasyarat dan profil mahasiswa; dosen dapat menambahkan catatan serta menyetujui atau meminta revisi. Status/catatan review tersimpan dan dapat dilihat mahasiswa.
- KRS yang telah disetujui terkunci untuk semester tersebut. Frontend menonaktifkan perubahan draft dan backend menolak pengajuan ulang; validasi server juga menolak jumlah SKS di atas batas berdasarkan IPK.
- Navigasi utama menggunakan ikon SVG Lucide, navbar tetap di atas, dan notifikasi interaktif tampil sebagai toast. Menu navigasi pada layar sempit memakai dropdown yang dapat ditutup dengan klik di luar atau Escape.
- Content-based score mempertimbangkan minat, performa pada mata kuliah prasyarat (atau IPK bila tidak tersedia), dan relevansi kurikulum. Collaborative score menggunakan pola mata kuliah semester target dari maksimal 20 mahasiswa lain dengan riwayat dan grade yang paling mirip.
- Bila belum ada cohort historis yang cocok, skor kolaboratif menjadi nol dan UI menyatakan bahwa data mahasiswa serupa belum tersedia. Sistem tidak mengarang jumlah mahasiswa serupa.
- Bobot di `RECOMMENDATION_WEIGHTS` dinormalisasi dan dapat diatur. Kebijakan grade lulus di `PASSING_GRADES` dapat disesuaikan dengan aturan akademik kampus.
- Admin dapat mengubah, menambah, dan menonaktifkan semua data mata kuliah. Impor Excel (`.xlsx`) mendukung kolom `semester`, `kode_mk`, `nama_mk`, `kategori`, `sks`, `Mata Kuliah Prasyarat`, dan `Keterangan / Catatan`; impor Excel mengganti katalog aktif secara keseluruhan. Kode berulang digabung dan seluruh semester penawarannya tetap disimpan. Impor CSV tetap mendukung format lama dan memperbarui katalog tanpa mengganti baris yang tidak ada di CSV. Admin juga dapat membangun versi model; riwayat versi menyimpan jumlah record dan metrik Precision@5/Recall@5 hasil evaluasi transisi semester yang tersedia. Jika data belum cukup, metrik dilaporkan `null` dengan status `insufficient_history`.
- LLM tidak menentukan skor atau validitas akademik dan tidak dibutuhkan untuk menjalankan sistem. Alasan yang ditampilkan berasal dari faktor model dan rule engine.

### Format CSV kurikulum

Kolom wajib: `code,name,sks,semester,category`. Kolom opsional: `description,day,time,prerequisite_codes`. Beberapa kode prasyarat dapat dipisahkan dengan koma. Excel dapat memakai header Indonesia yang disebutkan di atas; teks nama mata kuliah prasyarat dicocokkan ke kode kurikulum saat impor.

## Endpoint utama

Semua endpoint selain health dan login memerlukan token Bearer. Endpoint mahasiswa hanya tersedia untuk peran mahasiswa; endpoint pengelolaan model/katalog memerlukan admin.

| Method | Path | Fungsi |
|---|---|---|
| `POST` | `/api/auth/login` | Login |
| `POST` | `/api/auth/register` | Mendaftarkan akun mahasiswa |
| `GET` | `/api/auth/me` | Pengguna aktif |
| `POST` | `/api/mahasiswa/khs/preview` | Unggah satu PDF atau beberapa gambar dan simpan pratinjau sementara |
| `GET` | `/api/mahasiswa/khs` | Status dan hasil ekstraksi dokumen milik mahasiswa |
| `POST` | `/api/mahasiswa/khs/{id}/confirm` | Validasi koreksi dan konfirmasi riwayat |
| `GET` | `/api/mahasiswa/profil` | Profil akademik dari KHS yang dikonfirmasi |
| `PUT` | `/api/mahasiswa/profil` | Memperbarui minat |
| `GET` | `/api/mahasiswa/rekomendasi` | Profil, rekomendasi valid, kandidat ditolak, faktor dan model |
| `GET` | `/api/admin/courses` | Katalog kurikulum |
| `POST` | `/api/admin/courses` | Menambah mata kuliah |
| `PUT` | `/api/admin/courses/{code}` | Mengubah data mata kuliah |
| `DELETE` | `/api/admin/courses/{code}` | Menonaktifkan mata kuliah |
| `POST` | `/api/admin/import-data` | Impor katalog Excel atau CSV |
| `POST` | `/api/admin/model/train` | Membuat versi dan mengevaluasi model similarity |
| `GET` | `/api/admin/model/versions` | Riwayat versi model |
| `GET` | `/api/admin/evaluasi` | Metrik evaluasi versi terbaru |

Endpoint kompatibilitas `GET /api/rekomendasi` tetap tersedia dan hanya mengembalikan kandidat yang lolos rule engine.

## Pengembangan tanpa Docker

Backend memerlukan Python 3.12+, Poppler, Tesseract, serta paket Python di `backend/requirements.txt` untuk OCR. Tanpa executable OCR, PDF teks tetap dapat dibaca, tetapi PDF scan memerlukan instalasi tersebut.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```powershell
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Saat startup, migrasi Alembic meng-upgrade schema dan menambahkan struktur yang belum ada dengan mempertahankan data historis. Untuk deployment dengan PostgreSQL, backup database sebelum upgrade dan uji pada salinan database versi lama terlebih dahulu. Tes SQLite tersedia di `backend/tests`; pengujian PostgreSQL dan deployment Docker harus dijalankan pada environment yang tersedia.
