# Impor data dan pembuatan akun mahasiswa CourseRecom

## Tujuan dan batasan

Akun mahasiswa dibuat oleh Admin Prodi melalui impor daftar mahasiswa yang bersumber dari data resmi fakultas/program studi. Tidak ada pendaftaran mandiri mahasiswa dan tidak ada kode pendaftaran/undangan. Impor hanya dilakukan oleh akun dengan peran Admin.

Data demo dan data sintetis pada pengujian CI hanya berada di database sementara dan tidak boleh dipakai sebagai data mahasiswa nyata.

## Format file roster

Admin masuk ke CourseRecom → **Impor & Akun Mahasiswa**, lalu mengunduh template Excel. Format yang diterima adalah Excel \`.xlsx\` atau CSV UTF-8, maksimum 2 MB dan 2.000 baris per unggahan.

Kolom wajib:

| Kolom | Aturan |
|---|---|
| NIM | Harus sama persis dengan data akademik kampus; pada Excel, atur kolom sebagai teks agar angka nol di depan tidak hilang |
| Nama Lengkap | Nama resmi sesuai data akademik |
| Program Studi | Salah satu program studi FTII yang dikenali CourseRecom |
| Angkatan | Empat digit tahun masuk dan tidak melebihi awal tahun ajaran aktif |

NIM ganda, prodi tak dikenal, angkatan tidak valid, atau konflik dengan identitas akun yang sudah ada akan ditolak. Impor berlangsung dalam satu transaksi: jika ada satu data bermasalah, seluruh batch dibatalkan. Data yang sudah memiliki akun akan ditautkan/diakui sebagai akun terdaftar dan password yang sudah ada tidak diubah.

## Alur Admin

1. Pastikan file roster diperoleh dari sumber resmi fakultas/prodi dan penggunaannya untuk CourseRecom telah diizinkan.
2. Masuk sebagai Admin Prodi → **Impor & Akun Mahasiswa**.
3. Unduh template Excel, isi NIM, nama lengkap, program studi, dan angkatan, kemudian periksa kembali setiap baris.
4. Unggah file \`.xlsx\` atau \`.csv\` dan konfirmasi proses impor.
5. Untuk setiap NIM baru, sistem membuat akun dengan peran \`mahasiswa\`, username awal menggunakan NIM, serta password awal acak. Akun langsung aktif dan ditautkan ke roster.
6. Setelah impor berhasil, unduh file kredensial awal dari halaman admin. File tersebut memuat NIM, nama, username, dan password awal untuk akun yang baru dibuat pada batch itu.
7. Simpan file kredensial di perangkat admin yang terlindungi dan distribusikan setiap kredensial secara pribadi kepada mahasiswa yang bersangkutan. Jangan kirim seluruh file ke grup publik atau mengunggahnya ke repositori.
8. Minta mahasiswa mengganti password awal setelah pertama kali masuk. Password awal tidak disimpan dalam bentuk teks biasa di database dan tidak dapat diambil kembali setelah respons impor/halaman admin ditutup. Jika file kredensial hilang, admin perlu mengikuti prosedur reset password yang tersedia; impor ulang tidak akan mengubah password akun yang sudah ada.

Jumlah akun yang berhasil dibuat, akun yang sudah tersedia, dan entri roster ditampilkan pada ringkasan halaman admin. Target minimal 100 akun dinilai dari akun yang sudah dibuat, bukan sekadar jumlah baris roster.

## Alur Mahasiswa

1. Mahasiswa menerima username/NIM dan password awal secara pribadi dari Admin Prodi.
2. Masuk ke CourseRecom menggunakan kredensial yang diberikan.
3. Ganti password awal melalui pengaturan akun, lalu buka profil/minat untuk memeriksa bidang minat.
4. Unggah KHS resmi yang lengkap, periksa hasil pembacaan KHS, dan konfirmasi hanya jika sesuai dokumen.
5. Admin Prodi menetapkan Dosen PA. Tanpa Dosen PA dan KHS terkonfirmasi, mahasiswa belum dapat mengajukan KRS.
6. Setelah Dosen PA ditetapkan, mahasiswa menggunakan rekomendasi sebagai bahan pertimbangan, menyusun kelas/jadwal, dan mengajukan KRS. Dosen PA meninjau dan menyetujui atau meminta revisi.

Endpoint pendaftaran mandiri \`/api/auth/register\` dinonaktifkan dan mengembalikan HTTP 403. Endpoint pembuatan kode undangan lama juga dinonaktifkan; proses impor Excel/CSV adalah satu-satunya jalur provisioning akun mahasiswa pada sistem ini.

## Penugasan Dosen PA dan kesiapan operasional

Setelah akun terbentuk, Admin harus menetapkan Dosen PA yang benar kepada setiap mahasiswa. Jangan mengasumsikan satu dosen membimbing semua 100 mahasiswa. Cocokkan pembagian dengan keputusan resmi prodi dan kapasitas bimbingan dosen. Dashboard CourseRecom menyediakan daftar mahasiswa untuk penetapan dosen PA.

Sebelum uji coba produksi:
- Konfirmasi seluruh baris roster terhadap sumber akademik resmi.
- Siapkan akun Admin dan Dosen PA individual dengan password kuat; jangan membagikan akun demo.
- Tetapkan Dosen PA kepada mahasiswa sesuai SK/daftar bimbingan.
- Verifikasi periode KRS, tahun ajaran aktif, kurikulum, prasyarat, jadwal, ruang, dosen pengampu, serta kapasitas kelas.
- Minta mahasiswa mengunggah KHS masing-masing. Jangan memasukkan KHS milik orang lain.
- Uji satu siklus KRS dengan mahasiswa dan Dosen PA yang bersedia sebelum pembukaan massal.
- Pastikan backup database, pemantauan error, kebijakan retensi dokumen, dan saluran bantuan kampus sudah tersedia.

## Keamanan dan privasi

- Endpoint template, impor roster, dan ringkasan roster hanya dapat digunakan Admin Prodi.
- Password mahasiswa disimpan dalam bentuk hash; password awal acak hanya dikembalikan pada respons impor untuk ditampilkan ke Admin satu kali.
- Audit log mencatat aktivitas impor dan jumlah akun yang dibuat tanpa menyimpan password.
- File roster dan file kredensial berisi data pribadi. Terapkan minimisasi akses, distribusi pribadi, dan penghapusan sesuai kebijakan kampus.
- Perubahan pada roster yang sudah terhubung ke akun tidak boleh menimpa identitas akun secara diam-diam; konflik harus ditinjau Admin.
- Jangan mengirim file kredensial ke repositori, grup publik, atau pihak yang tidak berkepentingan.

## Yang bukan dilakukan sistem

CourseRecom tidak memverifikasi identitas melalui sistem SIAKAD/SSO kampus secara langsung dalam implementasi ini. Keabsahan roster bergantung pada sumber resmi yang diberikan Admin. Untuk integrasi identitas otomatis, diperlukan API/SSO resmi dan otorisasi dari UHAMKA.
