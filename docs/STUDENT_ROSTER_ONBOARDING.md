# Onboarding 100 mahasiswa CourseRecom

## Tujuan dan batasan

Fitur ini menyiapkan pendaftaran mandiri untuk mahasiswa yang benar-benar terdaftar di program studi. Sistem **tidak** membuat akun mahasiswa secara otomatis dari data yang belum diverifikasi. Admin mengimpor roster resmi, membuat kode undangan sekali pakai, lalu setiap mahasiswa membuat kata sandinya sendiri.

Data demo dan data sintetis pada pengujian CI hanya berada di database sementara dan tidak boleh dipakai sebagai data mahasiswa nyata.

## Format roster

Unduh `Template CSV` dari menu Admin Prodi → Pendaftaran Mahasiswa. Kolom wajib:

| Kolom | Aturan |
|---|---|
| NIM | Harus sama persis dengan data akademik kampus; simpan sebagai teks agar angka nol di depan tidak hilang |
| Nama Lengkap | Nama resmi sesuai data akademik |
| Program Studi | Salah satu program studi FTII yang dikenali CourseRecom |
| Angkatan | Empat digit tahun masuk dan tidak melebihi awal tahun ajaran aktif |

File menggunakan CSV UTF-8, maksimum 2 MB dan 2.000 baris per unggahan. NIM ganda, prodi tak dikenal, angkatan tidak valid, dan konflik dengan akun yang sudah ada akan ditolak. Impor berjalan dalam satu transaksi: bila ada kesalahan, seluruh batch dibatalkan, bukan sebagian.

Roster minimum untuk target dosen adalah 100 entri. Dashboard menunjukkan jumlah roster, jumlah akun yang selesai mendaftar, yang masih menunggu, dan ringkasan per prodi. Angka roster 100/100 **belum berarti 100 akun sudah dibuat**; setiap mahasiswa tetap harus mendaftar sendiri.

## Alur Admin

1. Pastikan file roster diperoleh dari sumber resmi fakultas/prodi dan penggunaannya untuk pendaftaran CourseRecom telah diizinkan.
2. Masuk sebagai Admin Prodi → Pendaftaran Mahasiswa.
3. Unduh template, isi roster resmi, periksa NIM/prodi/angkatan, lalu unggah CSV.
4. Pastikan ringkasan impor sesuai jumlah mahasiswa sasaran dan target minimal 100.
5. Tekan `Buat & unduh kode pendaftaran`. Sistem membuat kode acak per mahasiswa yang belum terdaftar. Kode berlaku 7 hari, hanya hash yang disimpan dalam database, dan dihapus setelah berhasil digunakan.
6. File unduhan mengandung identitas dan kode rahasia. Simpan di perangkat kampus yang terlindungi; distribusikan setiap kode **secara pribadi** kepada mahasiswa yang cocok. Jangan kirim seluruh file ke grup publik atau mengunggahnya ke repositori.
7. Jika file kode hilang atau masa berlakunya habis, Admin dapat membuat kode baru. Kode sebelumnya menjadi tidak berlaku.

## Alur Mahasiswa

1. Buka halaman CourseRecom dan pilih Daftar akun mahasiswa.
2. Masukkan NIM, nama lengkap, program studi, angkatan, kode pendaftaran, dan buat password pribadi minimal 8 karakter.
3. Nama, prodi, dan angkatan harus cocok dengan roster. Kode berlaku sekali pakai; NIM yang sudah digunakan tidak dapat didaftarkan lagi.
4. Login, buka profil/minat, lalu unggah KHS resmi yang lengkap.
5. Periksa hasil pembacaan KHS dan konfirmasi hanya jika sesuai dokumen.
6. Admin Prodi menetapkan Dosen PA. Tanpa Dosen PA dan KHS terkonfirmasi, mahasiswa belum dapat mengajukan KRS.
7. Setelah Dosen PA ditetapkan, mahasiswa menggunakan rekomendasi sebagai bahan pertimbangan, menyusun kelas/jadwal, dan mengajukan KRS. Dosen PA meninjau dan menyetujui atau meminta revisi.

## Penugasan Dosen PA dan kesiapan operasional

Setelah akun terbentuk, Admin harus menetapkan Dosen PA yang benar kepada setiap mahasiswa. Jangan mengasumsikan satu dosen membimbing semua 100 mahasiswa. Cocokkan pembagian dengan keputusan resmi prodi dan kapasitas bimbingan dosen. Dashboard CourseRecom menyediakan daftar mahasiswa untuk penetapan dosen PA.

Sebelum uji coba produksi:
- Konfirmasi 100+ baris roster terhadap sumber akademik resmi.
- Siapkan akun Admin dan Dosen PA individual dengan password kuat; jangan membagikan akun demo.
- Tetapkan Dosen PA kepada mahasiswa sesuai SK/daftar bimbingan.
- Verifikasi periode KRS, tahun ajaran aktif, kurikulum, prasyarat, jadwal, ruang, dosen pengampu, serta kapasitas kelas.
- Minta mahasiswa mengunggah KHS masing-masing. Jangan memasukkan KHS milik orang lain.
- Uji satu siklus KRS dengan mahasiswa dan Dosen PA yang bersedia sebelum pembukaan massal.
- Pastikan backup database, pemantauan error, kebijakan retensi dokumen, dan saluran bantuan kampus sudah tersedia.

## Keamanan dan privasi

- Endpoint impor roster, ringkasan roster, dan pembuatan kode hanya dapat dipakai Admin Prodi.
- Browser production memakai cookie HttpOnly; JWT tidak disimpan di localStorage.
- Kode undangan tidak disimpan dalam bentuk teks biasa, kedaluwarsa, dan sekali pakai.
- Audit log mencatat batch impor/pembuatan kode/pendaftaran tanpa menyimpan password atau kode undangan.
- File roster dan file kode mengandung data pribadi. Terapkan minimisasi akses, distribusi pribadi, dan penghapusan sesuai kebijakan kampus.
- Perubahan pada roster yang sudah terhubung ke akun tidak boleh menimpa identitas akun secara diam-diam; konflik harus ditinjau Admin.

## Yang bukan dilakukan sistem

CourseRecom tidak memverifikasi identitas melalui sistem SIAKAD/SSO kampus secara langsung dalam implementasi ini. Keabsahan roster bergantung pada sumber resmi yang diberikan Admin. Untuk integrasi identitas otomatis, diperlukan API/SSO resmi dan otorisasi dari UHAMKA.
