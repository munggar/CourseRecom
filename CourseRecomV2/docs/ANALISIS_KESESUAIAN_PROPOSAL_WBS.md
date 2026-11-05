# Analisis Kesesuaian Proposal dan WBS

## 1. Temuan Identitas dan Sumber Analisis

Dokumen yang tersedia adalah:

- `Kelompok2_CourseRecom_TugasPertemuan5 (1).pdf`
- Judul dokumen: **Scope Statement dan Work Breakdown Structure (WBS) - CourseRecom**

Dokumen tersebut konsisten dengan kode aplikasi aktual CourseRecom. Tidak ditemukan proposal atau WBS WarungPintar dalam workspace.

Dengan demikian, tabel berikut tidak menghubungkan fitur warung secara spekulatif. Keadaan aktual WarungPintar tidak dapat dinilai dari workspace ini, sedangkan kesesuaian yang dapat dibuktikan adalah antara proposal/WBS CourseRecom dan kode CourseRecom.

Sumber bukti:

- Proposal/WBS: PDF kelompok.
- Implementasi frontend: `frontend/src/App.jsx`.
- API: `backend/app/api/routes/auth.py`, `mahasiswa.py`, `dosen.py`, dan `admin.py`.
- Model: `backend/app/models.py`.
- Model rekomendasi: `backend/app/services/recommendation.py`.
- Parser dan katalog: `backend/app/services/khs_parser.py`, `backend/app/services/course_catalog.py`.
- Pengujian backend: `backend/tests/`.

## 2. Matriks Kesesuaian Proposal dan WBS

| No. | Fitur Proposal/WBS | Implementasi Aktual | Kondisi | Bukti File Kode | Catatan |
|---|---|---|---|---|---|
| 1 | Aplikasi web responsif untuk mahasiswa, Dosen PA, dan admin berbasis login peran | UI React memiliki tiga role dan navigasi berbasis role. Backend memakai dependency `require_roles`. | **Selesai tetapi belum terverifikasi** untuk responsivitas penuh | `frontend/src/App.jsx`; `backend/app/deps.py`; `backend/app/api/routes/auth.py` | RBAC backend memiliki test. Responsivitas visual dan seluruh peran belum diuji otomatis dengan browser. |
| 2 | Autentikasi login per peran | JWT login dan endpoint `/api/auth/me`; role dibaca dari database pada backend. | **Selesai dan terintegrasi** | `backend/app/api/routes/auth.py`; `backend/app/deps.py`; `backend/app/models.py`; `backend/tests/test_api_rbac.py` | Ada pemilihan role pada UI, tetapi backend mengabaikannya dan memakai role akun database. Ini lebih aman secara akses, meskipun bisa membingungkan UI. |
| 3 | Profil akademik mahasiswa: IPK, SKS, semester, minat | User menyimpan semester/IPK/SKS dan minat; endpoint profil mahasiswa tersedia. | **Selesai dan terintegrasi** | `backend/app/models.py`; `backend/app/api/routes/mahasiswa.py`; `frontend/src/App.jsx` | Konsistensi nilai profil setelah KHS perlu diperiksa pada seluruh alur perubahan KHS. |
| 4 | Mengumpulkan, anonimisasi, dan membersihkan data nilai | Aplikasi memakai data lokal, parser KHS, dan StudentRecord; tidak ada bukti alur anonimisasi eksplisit atau data pipeline dokumen ini. | **Belum diimplementasikan** sebagai proses data tertulis | `backend/app/services/khs_parser.py`; `backend/app/models.py` | Pembersihan parser ada, tetapi requirement WBS 3.1 tentang dataset, dokumentasi, dan anonimisasi belum terbukti sebagai pekerjaan terpisah. |
| 5 | Model rekomendasi content-based + collaborative filtering | Rekomendasi memakai skor minat, akademik, kurikulum, pola mata kuliah, dan kemiripan mahasiswa. Training similarity model terimplementasi. | **Selesai tetapi belum terverifikasi** terhadap Precision@5 target proposal | `backend/app/services/recommendation.py`; `backend/app/models.py` | Precision@5 dihitung dalam training similarity. Tidak ada bukti dataset independen yang memenuhi target ≥0,70 di proposal. |
| 6 | Model baseline dan final | Terdapat versi model similarity dan endpoint training; tidak ada identifikasi eksplisit baseline dibandingkan dengan final pada pipeline atau UI. | **Implementasi parsial** | `backend/app/services/recommendation.py`; `backend/app/api/routes/admin.py` | Versi model tersimpan, tetapi tidak terbukti adanya eksperimen baseline/final dan laporan pembanding. |
| 7 | Validasi prasyarat mata kuliah | Backend memeriksa kode prasyarat yang sudah lulus dan aturan tambahan teks prasyarat. | **Selesai dan terintegrasi** | `backend/app/services/recommendation.py`; `backend/app/services/validation.py`; `backend/tests/test_validation.py` | Validasi ganda frontend dan backend tersedia. Data prasyarat pada kode tetap perlu kualitas katalog yang benar. |
| 8 | Validasi batas SKS | Kuota SKS dihitung dari akademik dan diuji saat rekomendasi/pengajuan KRS. | **Selesai dan terintegrasi** | `backend/app/services/validation.py`; `backend/app/api/routes/mahasiswa.py`; `backend/tests/test_validation.py`; `backend/tests/test_khs_workflow.py` | Batas dapat bergantung pada data profil dan rule semester. |
| 9 | Skor kecocokan dan penjelasan rekomendasi | Hasil rekomendasi berisi score, faktor, reasons, rejected, dan reason_block. | **Selesai dan terintegrasi** | `backend/app/services/recommendation.py`; `frontend/src/App.jsx` | AI explainer Gemini belum menjadi jalur utama. Penjelasan rule-based sudah aktif dan terlihat di UI. |
| 10 | Modul mahasiswa: tampil rekomendasi | Halaman rekomendasi mengambil API, menampilkan skor dan alasan, serta memberi kandidat ditolak. | **Selesai tetapi belum terverifikasi** end-to-end browser | `frontend/src/App.jsx`; `backend/app/api/routes/mahasiswa.py`; backend/test alur rekomendasi | Backend terintegrasi. Tidak ada test frontend otomatis untuk rendering dan interaksi browser. |
| 11 | Draft KRS mahasiswa | Draft disimpan state React dan `localStorage`, memiliki tambah/hapus dan validasi kuota. | **Selesai tetapi belum terverifikasi** lintas browser/account | `frontend/src/App.jsx` | Draft belum disimpan sebagai entitas backend. Backend menyimpan draft final sebagai StudyPlan saat diajukan. |
| 12 | Pengajuan draft KRS ke Dosen PA | Endpoint menyimpan StudyPlan pending dengan JSON mata kuliah dan total SKS. | **Selesai dan terintegrasi** | `backend/app/api/routes/mahasiswa.py`; `backend/app/models.py`; `backend/tests/test_khs_workflow.py` | Partial unique index dan penanganan konflik menjaga satu rencana pending. Frontend mencegah double-submit instance React. |
| 13 | Unduh laporan PDF | Tidak ditemukan generator PDF, endpoint download, atau tombol unduh untuk draft/rekomendasi. PDF hanya digunakan sebagai input KHS. | **Belum diimplementasikan** | `frontend/src/App.jsx`; seluruh `backend/app/api/routes/*.py` | Ini adalah gap acceptance criterion yang eksplisit: proposal mewajibkan PDF dapat diunduh. |
| 14 | Dashboard Dosen PA | Backend menyediakan mahasiswa bimbingan dan list rencana studi; frontend menampilkan ringkasan dashboard. | **Selesai tetapi belum terverifikasi** end-to-end | `backend/app/api/routes/dosen.py`; `frontend/src/App.jsx`; `backend/tests/test_api_rbac.py` | Backend dosen melihat semua mahasiswa/rencana, belum assignment dosen-mahasiswa individual. |
| 15 | Dosen PA memberi catatan dan persetujuan | Endpoint review mengubah status dan menyimpan advisor note serta reviewer id. | **Selesai dan terintegrasi** | `backend/app/api/routes/dosen.py`; `backend/app/models.py`; `backend/tests/test_khs_workflow.py` | Status approved terkunci dari perubahan. Catatan revisi tergantung payload backend. |
| 16 | Pantauan semua mahasiswa bimbingan dengan ≤3 klik | Dashboard tersedia, tetapi tidak ada bukti pengujian waktu klik dan tidak ada assignment PA nyata ke mahasiswa. | **Implementasi parsial** | `frontend/src/App.jsx`; `backend/app/api/routes/dosen.py` | Backend menyajikan seluruh mahasiswa, bukan hanya mahasiswa bimbingan dosen tersebut. |
| 17 | Impor data nilai/kurikulum CSV atau Excel oleh admin | CRUD kursus tersedia dan impor Excel/CSV kursus terimplementasi. Tidak ada impor nilai historis mahasiswa di UI API admin. | **Implementasi parsial** | `backend/app/api/routes/admin.py`; `backend/app/services/course_catalog.py`; `backend/tests/test_course_catalog.py` | Requirement katalog benar-benar terisi. Impor nilai dan dataset historis belum ada sebagai alur terpisah. |
| 18 | Kelola mata kuliah dan prasyarat | Admin dapat membuat, mengubah, menonaktifkan, dan mengimpor katalog. | **Selesai dan terintegrasi** | `backend/app/api/routes/admin.py`; `backend/app/models.py`; `backend/tests/test_course_catalog.py` | Soft delete dipakai, sehingga data katalog lama tidak dihapus fisik. |
| 19 | Dashboard dan manajemen data admin | Dashboard admin menampilkan mahasiswa/dosen dan menghapus akun mahasiswa beserta data terkait. | **Selesai dan terintegrasi** | `backend/app/api/routes/admin.py`; `frontend/src/App.jsx` | Belum ada CRUD akun dosen pada antarmuka. |
| 20 | Report precision model dan evaluasi | Endpoint evaluasi dan versi model tersedia; training menghitung precision@5 dan recall@5. | **Selesai tetapi belum terverifikasi** terhadap target ≥0,70 pada data uji representatif | `backend/app/services/recommendation.py`; `backend/app/api/routes/admin.py` | Evaluasi backend ada, tetapi belum terbukti adalah data uji independen atau memenuhi target acceptance. |
| 21 | Pengujian keamanan akses/data | Terdapat test RBAC dan autentikasi. Tidak ada laporan audit kriptografi, anonymisasi, atau penetration/security test terpisah. | **Implementasi parsial** | `backend/tests/test_api_rbac.py`; `backend/app/deps.py`; `backend/app/models.py` | Password hash dan token dicek pada kode, namun data rahasia tidak diaudit. |
| 22 | Pengujian fungsional, pencatatan bug, dan perbaikan | 34 test backend dilaporkan lulus pada audit sebelumnya; frontend belum memiliki test komponen/browser automation. | **Selesai tetapi belum terverifikasi** | `backend/tests/`; `frontend/package.json` | Tidak ada bukti report bug formal atau E2E frontend di repository saat ini. |
| 23 | UAT mahasiswa dan Dosen PA | Tidak ditemukan hasil UAT tersimpan atau testscript stakeholder. | **Belum diimplementasikan** sebagai bukti | Tidak ditemukan file/bukti repository | Implementasi dapat siap, tetapi acceptance UAT ≥80% belum terbukti. |
| 24 | Panduan pengguna | Halaman Tentang/Panduan tersedia sebagai konten frontend. Tidak ada dokumentasi file aplikasi atau pelatihan terpisah. | **Selesai tetapi belum terverifikasi** | `frontend/src/App.jsx` | Ada panduan UI, belum terbukti sesuai kebutuhan stakeholder dan dapat dipelajari pengguna. |
| 25 | Deployment ke hosting dan serah terima | Docker Compose dan konfigurasi cloud tersedia. Tidak ada bukti deployment aktif atau alamat layanan. | **Implementasi parsial** | `docker-compose.yml`; `docker-compose.cloud.yml`; `env.cloud.example` | Paket deployment ada, status online aktual belum dapat diverifikasi dari workspace. |
| 26 | WBS pengendalian progres, risiko, biaya, dan change log | Tidak ada module/change log aplikasi untuk kebutuhan manajemen proyek. Dokumen analisis bisa menjadi artefak, tetapi bukan implementasi sistem. | **Belum diimplementasikan** sebagai bagian aplikasi | Tidak ditemukan | Ini adalah deliverable manajemen proyek, bukan fungsi pengguna aplikasi; harus ada sebagai dokumentasi proyek terpisah. |

## 3. Validasi Integrasi Backend dan Database

### Terhubung penuh frontend-backend-database

- Login dan identitas.
- Profil akademik/minat.
- Katalog kurikulum.
- CRUD/import katalog admin.
- KHS parse, draft pending, konfirmasi, riwayat record.
- Pengajuan rencana studi dan review dosen.
- Training/evaluasi versi model.

### Terhubung frontend/backend, tetapi data draft tidak bersifat backend-first

- Draft KRS sebelum pengajuan.
- Draft siswa disimpan di `localStorage` dan dapat cross-account jika browser tidak dibersihkan.

### Belum tersedia atau tidak terbukti terintegrasi

- Unduh laporan PDF.
- Impor nilai historis mahasiswa secara terpisah.
- Anonimisasi data sebagai workflow dokumentasi.
- Hasil UAT sebagai artefak terverifikasi.
- Assignment dosen-mahasiswa individual.
- Deployment online terverifikasi.

## 4. Analisis Status Fitur

### Fitur inti yang sudah selesai dan terintegrasi

1. Login dan otorisasi role.
2. Profil mahasiswa dan minat.
3. Kurikulum dan validasi katalog.
4. Upload/KHS dan konfirmasi riwayat.
5. Rekomendasi dengan validasi prasyarat/SKS.
6. Pengajuan rencana studi.
7. Persetujuan/revisi Dosen PA.
8. Manajemen katalog admin.

### Fitur prioritas pemilik kebutuhan aktual

Dalam konteks CourseRecom, stakeholder utama yang analog dengan "pemilik warung" proposal adalah:

- Ketua Program Studi sebagai sponsor/pemilik kebijakan.
- Mahasiswa sebagai pengguna utama.
- Dosen PA sebagai pengambil keputusan.

Prioritas manfaat yang paling tinggi adalah:

1. Rekomendasi yang bebas dari pelanggaran prasyarat/SKS.
2. Penyusunan draft KRS yang transparan dan dapat diajukan.
3. Review dan persetujuan Dosen PA.
4. Kelola kurikulum dan prasyarat secara terpusat.
5. Akurasi/penjelasan rekomendasi.
6. PDF laporan draft KRS sebagai deliverable yang dijanjikan.

## 5. Fitur yang Paling Realistis untuk Fokus Coding dan Pengujian

Rekomendasi fitur utama adalah **alur Draft KRS sampai review dan persetujuan Dosen PA**.

Alasan pemilihannya:

- Fitur tercantum langsung dalam Scope Statement dan WBS 4.2 serta 4.3.
- Backend, database, UI, dan proteksi double-submit sudah memiliki dasar implementasi.
- Memberikan manfaat nyata bagi mahasiswa dan Dosen PA.
- Data transaksional dapat diuji dengan database.
- Dapat diuji sebagai alur end-to-end tanpa menambah capability di luar scope:
  - login mahasiswa;
  - mengambil profil/KHS;
  - memilih mata kuliah;
  - validasi SKS dan duplikasi;
  - submit StudyPlan;
  - login dosen;
  - melihat rencana;
  - approve atau revision;
  - verifikasi perubahan status dan catatan pada database.
- Tidak memiliki ketergantungan eksternal terhadap Gemini, OCR, atau PDF baru.

Fitur pengganti yang juga layak tetapi lebih besar adalah unduh laporan PDF, karena diperlukan proposal tetapi belum memiliki dasar implementasi. Ini membutuhkan implementasi baru, sehingga bertentangan dengan aturan “tidak menambah fitur baru” untuk tugas pengujian berbasis kode yang ada.

## 6. Ruang Lingkup Teknis Fitur Draft KRS

### Frontend yang harus diperiksa

- state draft dan `localStorage` pada `frontend/src/App.jsx`;
- loading dan disable submit saat pengiriman ganda;
- penambahan/penghapusan mata kuliah;
- validasi total SKS;
- status rencana;
- halaman review Dosen PA.

### Backend yang harus diperiksa

- endpoint rekomendasi mahasiswa;
- endpoint list/submit StudyPlan;
- endpoint list/review Dosen PA;
- authorization mahasiswa dan dosen;
- `IntegrityError` untuk status pending duplikat;
- schema dan status yang diterima review.

### Database yang harus diperiksa

- tabel `StudyPlan`;
- foreign key mahasiswa dan reviewer;
- partial unique index satu `pending` per mahasiswa;
- `courses_json`;
- status `pending`, `approved`, dan `revision`;
- `advisor_note`;
- timestamp.

### Pengujian yang realistis

- mahasiswa valid dapat membuat draft;
- mahasiswa tidak dapat mengirim mata kuliah duplikat;
- total SKS tidak boleh melampaui kuota;
- double-click atau dua request tidak membuat dua pending aktif;
- dosen dapat menyetujui rencana;
- dosen dapat memberi revisi dengan catatan;
- mahasiswa lain/role lain tidak dapat membaca atau mengubah rencana tidak sah;
- approved tidak dapat diubah;
- status dan catatan tersimpan di database serta muncul kembali pada reload;
- data rencana tidak bocor antarakun.

Pengujian dapat mencakup frontend lint/build, API integration pytest, dan browser automation minimal. Tidak perlu menambahkan durasi waktu maupun estimasi biaya, sesuai ruang lingkup analisis teknis.

## 7. Risiko Kesesuaian dan Gap Acceptance

1. Proposal mewajibkan laporan PDF; implementasi belum menemukannya.
2. Proposal menargetkan Precision@5 ≥0,70; backend menghitung metrik, tetapi belum ada bukti data uji independen memenuhi ambang itu.
3. Proposal mengharuskan Rekomendasi menampilkan skor dan minimal satu alasan; implementasi memang menampilkan keduanya.
4. Proposal mengharuskan 100% rekomendasi lolos prasyarat/SKS; frontend menandai validasi, backend juga memblokir submit yang tidak valid. Belum ada bukti suite meliputi seluruh jenis prasyarat.
5. Proposal mengharuskan Dosen PA melihat 100% mahasiswa bimbingan dalam ≤3 klik; backend saat ini menyediakan semua mahasiswa, bukan assignment individual, dan click target belum diuji.
6. Proposal mengharuskan UAT ≥80%; tidak ada bukti UAT tersimpan.
7. Proposal mengharuskan responsif; frontend belum memiliki pengujian browser responsif.
8. Proposal mengharuskan data anonymized/encrypted; parser dan database tidak memberikan bukti lengkap terhadap semua requirement privasi.
9. Proposal menyebut analisis collaborative filtering; implementasi memadukannya dengan similarity Jaccard/rule weights, tetapi tidak ada bukti baseline dan akurasi yang memadai.

## 8. Kesimpulan

Workspace tidak memuat WarungPintar; kode dan dokumen yang ada adalah CourseRecom. Dari perspective proposal/WBS CourseRecom, fondasi sudah cukup kuat untuk autentikasi, rekomendasi, draft dan review KRS, katalog, serta administrasi. Gap utama adalah PDF, bukti UAT, Precision@5 pada dataset representatif, assignment dosen-mahasiswa individual, serta bukti testing frontend/E2E.

Tidak ada proof implementasi fitur warung seperti kasir, transaksi penjualan, stok, produk, pelanggan, pemasok, QRIS, atau laporan penjualan dalam workspace ini.

### Rekomendasi Fitur Utama

Fokus tugas Coding dan Pengujian Aplikasi sebaiknya adalah **alokasi rekomendasi ke Draft KRS, pengajuan sebagai StudyPlan, dan review Dosen PA**.

Alasan kebutuhan pengguna:

- Mahasiswa perlu mengeksekusi rekomendasi menjadi rencana yang valid.
- Pemilik kebijakan akademik/Dosen PA perlu memeriksa, menyetujui, atau meminta revisi.
- Fitur ini menghubungkan keputusan mahasiswa, data katalog, aturan akademik, database, dan otorisasi.
- Dasar implementasi sudah ada, sehingga tugas dapat memperbaiki dan membuktikan alur yang sudah di-scope daripada membangun fungsi baru.
