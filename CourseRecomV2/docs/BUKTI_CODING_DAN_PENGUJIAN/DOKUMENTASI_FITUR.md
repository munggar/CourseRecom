# Dokumentasi Fitur Utama

## Peringatan Identitas dan Bukti

Workspace yang tersedia adalah aplikasi CourseRecom, bukan aplikasi WarungPintar. Fitur utama yang dibuktikan oleh repository dan pengujian adalah **Rekomendasi Mata Kuliah dan Pengajuan Draft KRS sampai Review Dosen PA**. Dokumen ini tidak mengklaim bahwa fitur warung kasir, stok, atau penjualan telah ada apabila tidak ditemukan implementasinya.

## Identitas Fitur

- Nama fitur: Alur rekomendasi mata kuliah dan draft KRS
- Pengguna utama: mahasiswa
- Pengguna reviewer: Dosen Pembimbing Akademik
- Stakeholder tambahan: Admin Prodi dan Ketua Prodi
- Ruang lingkup: login → KHS → rekomendasi → draft KRS → pengajuan → review dosen
- Sumber proposal/WBS: CourseRecom Scope Statement dan WBS Paket 3.0, 3.3, 4.2, dan 4.3.

## Alasan Pemilihan

Fitur dipilih karena:

1. Langsung mendukung kebutuhan mahasiswa memilih mata kuliah yang sesuai kemampuan dan minat.
2. Mendukung tugas dosen PA memantau dan menyetujui rencana studi tanpa memeriksa seluruh data secara manual.
3. Memiliki dasar implementasi frontend, API, model database, dan pengujian backend.
4. Dapat diuji end-to-end pada backend dengan data sintetis tanpa integrasi layanan eksternal baru.
5. Menyediakan alur yang dapat memperbaiki risiko prasyarat, batas SKS, serta double submission.

## User Story

### Mahasiswa

Sebagai mahasiswa, saya ingin mendapatkan rekomendasi mata kuliah yang sesuai dengan KHS, minat, dan kuota SKS, sehingga saya dapat menyusun draft KRS yang dapat diajukan kepada dosen PA.

### Dosen PA

Sebagai dosen PA, saya ingin melihat rencana studi mahasiswa beserta mata kuliah dan statusnya, sehingga saya dapat menyetujui atau meminta revisi dengan catatan.

### Admin

Sebagai admin Prodi, saya ingin mengelola katalog mata kuliah dan prasyarat, sehingga rekomendasi mahasiswa berdasarkan kurikulum yang benar.

## Acceptance Criteria

- Mahasiswa dapat login dan memuat profil akademik.
- Mahasiswa dapat mengunggah dan mengonfirmasi KHS.
- Sistem menampilkan skor dan alasan untuk kandidat rekomendasi.
- Mata kuliah yang melanggar prasyarat atau kuota tidak dapat diajukan.
- Mahasiswa dapat memilih mata kuliah valid ke draft KRS.
- Mahasiswa tidak dapat membuat dua rencana `pending` secara bersamaan.
- Sistem menyimpan KRS sebagai `StudyPlan` pada database.
- Dosen PA dapat melihat rencana.
- Dosen PA dapat menyetujui atau memberi revisi beserta catatan.
- Status yang sudah disetujui tidak dapat diubah kembali.
- Pihak lain tidak dapat mengakses data atau tindakan di luar perannya.

## Input

| Area | Input sintetis |
|---|---|
| Autentikasi | NIM dan password demo di lingkungan lokal |
| Profil | Semester, IPK, SKS, serta pilihan minat |
| KHS | PDF atau gambar sintetis, atau payload parsed sintetis pada test |
| Draft KRS | Daftar kode mata kuliah valid dan total SKS dalam kuota |
| Review dosen | Status `approved` atau `revision` dan catatan revisi |
| Admin katalog | Data mata kuliah, SKS, semester, kategori, prasyarat, dan jadwal |

Contoh nilai sintetis hanya boleh digunakan sebagai data pengujian. Jangan memasukkan kredensial nyata atau password akun produksi ke screenshot atau dokumentasi.

## Proses

1. Frontend memulihkan atau menerima JWT.
2. Backend memverifikasi identitas dan role.
3. Mahasiswa mengunggah/mengonfirmasi KHS.
4. Backend membaca riwayat akademik dan profil.
5. Engine rekomendasi menghitung faktor skor, prasyarat, kuota, dan kandidat ditolak.
6. Frontend menyimpan draft lokal dan memvalidasi duplikasi serta total SKS.
7. Backend memvalidasi ulang kode yang dikirim dan kuota.
8. Backend menyimpan `StudyPlan` berstatus `pending`.
9. Database memastikan satu rencana pending untuk mahasiswa.
10. Dosen PA mengambil daftar rencana dan memperbarui status/catatan.
11. Frontend memperbarui tampilan status mahasiswa dan dosen.

## Penyimpanan

| Jenis Data | Lokasi Penyimpanan |
|---|---|
| Akun dan profil | Tabel `users` |
| KHS terkonfirmasi | `khs_documents` dan `student_records` |
| Katalog dan prasyarat | `courses` |
| Draft sebelum diajukan | `localStorage` browser |
| Draft final dan status | Tabel `study_plans` |
| Versi dan evaluasi model | `recommendation_model_versions` |

`localStorage` tidak menggantikan penyimpanan database final. Data final CourseRecom disimpan backend pada `study_plans`.

## Output

- Daftar rekomendasi valid beserta skor.
- Daftar kandidat ditolak beserta alasan.
- Ringkasan profil akademik dan kuota.
- Status draft di browser.
- Study plan tersimpan dengan status `pending`.
- Status `approved` atau `revision`.
- Catatan Dosen PA.

## Lokasi Implementasi Utama

- UI dan state frontend: `frontend/src/App.jsx`.
- API mahasiswa: `backend/app/api/routes/mahasiswa.py`.
- API dosen: `backend/app/api/routes/dosen.py`.
- Engine rekomendasi: `backend/app/services/recommendation.py`.
- Validasi: `backend/app/services/validation.py`.
- Model database: `backend/app/models.py`.
- Test backend: `backend/tests/test_khs_workflow.py`, `test_validation.py`, `test_api_rbac.py`, dan `test_database_config.py`.
