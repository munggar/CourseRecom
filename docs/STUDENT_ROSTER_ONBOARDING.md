# Pendaftaran manual dan impor akun mahasiswa CourseRecom

## Tujuan

CourseRecom mendukung dua jalur pembuatan akun mahasiswa:

1. **Pendaftaran manual oleh mahasiswa** dari halaman login. Mahasiswa mengisi identitas akademik dan membuat password sendiri. Tidak ada field atau kode pendaftaran resmi.
2. **Impor data oleh Admin Prodi** menggunakan Excel atau CSV. Sistem langsung membuat akun untuk NIM yang belum memiliki akun. Untuk mahasiswa yang sudah mendaftar manual, sistem mencocokkan data lalu menautkan akun yang sudah ada ke roster.

Kedua jalur tersebut menggunakan akun mahasiswa yang sama. Tidak boleh ada akun ganda untuk NIM yang sama.

## Pendaftaran manual mahasiswa

1. Buka aplikasi CourseRecom, pilih **Daftar akun mahasiswa** pada halaman login.
2. Isi NIM, nama lengkap, username (opsional), program studi, bidang minat, angkatan, password, dan konfirmasi password.
3. Field kode pendaftaran tidak digunakan dan tidak diminta.
4. Angkatan harus berupa empat digit angka serta tidak boleh melebihi tahun awal pada tahun ajaran aktif.
5. Sistem memvalidasi program studi dan bidang minat, memastikan NIM/username belum digunakan, lalu membuat akun dengan peran `mahasiswa`.
6. Setelah berhasil, masuk menggunakan NIM atau username dan password yang dibuat.
7. Pastikan data identitas sesuai data akademik kampus. Jika ada kesalahan identitas, hubungi Admin Prodi untuk pemeriksaan dan penyesuaian data akademik.

Pendaftaran mandiri tidak membuat akun dosen PA atau admin. Role akun ditetapkan oleh server menjadi `mahasiswa`, bukan dari input pengguna.

## Format file impor Admin

Admin dapat mengunduh **Template Excel** dari menu Admin Prodi → **Impor & Akun Mahasiswa**. Sistem menerima file `.xlsx` atau `.csv` UTF-8, maksimal 2 MB dan 2.000 baris per unggahan.

Kolom wajib:

| Kolom | Aturan |
|---|---|
| NIM | NIM resmi kampus. Atur sebagai teks di Excel agar angka nol di depan tidak hilang |
| Nama Lengkap | Nama resmi sesuai data akademik |
| Program Studi | Salah satu program studi FTII yang dikenali CourseRecom |
| Angkatan | Empat digit tahun masuk dan tidak melebihi awal tahun ajaran aktif |

Sistem memvalidasi NIM duplikat dalam file, nama, program studi, dan angkatan. Konflik identitas dengan akun yang sudah ada ditolak agar data akun tidak ditimpa diam-diam. Impor berjalan dalam satu transaksi; jika satu baris gagal, seluruh batch dibatalkan.

## Alur Admin Prodi

1. Dapatkan file mahasiswa dari sumber resmi fakultas/program studi dan pastikan penggunaannya untuk CourseRecom telah diizinkan.
2. Masuk sebagai Admin Prodi → **Impor & Akun Mahasiswa**.
3. Unduh template Excel, isi NIM, Nama Lengkap, Program Studi, dan Angkatan, kemudian periksa seluruh baris.
4. Unggah file `.xlsx` atau `.csv` dan pilih **Validasi & buat akun mahasiswa**.
5. Untuk NIM yang belum memiliki akun, sistem membuat akun dengan peran `mahasiswa`, username awal berupa NIM (atau alternatif bila username tersebut sudah dipakai), serta password awal acak.
6. Untuk NIM yang sudah memiliki akun dari pendaftaran manual, sistem memeriksa kesesuaian nama, program studi, dan angkatan. Jika cocok, roster ditautkan ke akun yang sudah ada. Password, username, dan data akademik akun yang sudah ada tidak dibuat ulang atau di-reset.
7. Jika identitas tidak cocok atau NIM dipakai akun non-mahasiswa, sistem menolak seluruh batch dan meminta Admin memeriksa datanya.
8. Setelah impor berhasil, Admin dapat mengunduh file kredensial awal yang hanya berisi akun baru yang dibuat oleh batch tersebut. Akun manual yang sudah ada tidak memiliki password baru untuk dibagikan.
9. Simpan file kredensial di perangkat admin yang terlindungi. Bagikan hanya kredensial milik mahasiswa terkait melalui kanal pribadi kampus. Jangan kirim seluruh file ke grup publik atau mengunggahnya ke repositori.

Password awal akun yang dibuat Admin hanya dikembalikan pada respons impor dan disajikan tanpa cache. Password disimpan di database dalam bentuk hash. Impor ulang tidak menampilkan kembali password lama, tidak mereset password, dan tidak membuat akun duplikat.

## Jika mahasiswa daftar manual sebelum data diimpor

Contoh alur:

1. Mahasiswa mendaftar manual dengan NIM `2403045007` dan mengatur password sendiri.
2. Admin kemudian mengimpor roster dengan NIM, nama, program studi, dan angkatan mahasiswa tersebut.
3. CourseRecom menemukan akun berdasarkan NIM dan memeriksa kesesuaian nama, program studi, serta angkatan.
4. Jika cocok, entri roster ditautkan ke akun tersebut. Jumlah akun baru yang dibuat tetap nol untuk baris itu, tidak ada file password baru, dan mahasiswa tetap masuk menggunakan password yang sebelumnya dibuat.
5. Jika tidak cocok, batch impor ditolak agar Admin dapat memeriksa sumber datanya.

## Target akun dan penugasan Dosen PA

Dashboard roster menampilkan total entri, jumlah akun yang sudah dibuat/ditautkan, jumlah yang belum memiliki akun, dan ringkasan per program studi. Target 100 akun dinilai dari akun mahasiswa aktif yang sudah terhubung dengan roster, bukan sekadar jumlah baris dalam file.

Setelah akun tersedia, Admin harus menetapkan Dosen PA sesuai keputusan resmi program studi. Cocokkan pembagian dengan daftar resmi dan kapasitas bimbingan masing-masing dosen.

## Pengujian sebelum operasional

- Uji pendaftaran manual dengan NIM baru, username default NIM, dan username khusus.
- Uji NIM duplikat, username duplikat, password pendek, angkatan bukan empat digit, dan angkatan melebihi tahun ajaran aktif.
- Uji impor Excel dan CSV dengan NIM yang belum memiliki akun.
- Uji impor roster untuk akun yang sudah mendaftar manual dan cocokkan bahwa tidak ada akun kedua serta password tidak berubah.
- Uji penolakan ketika nama, program studi, atau angkatan tidak sesuai dengan akun yang sudah ada.
- Tetapkan Dosen PA sesuai SK/daftar bimbingan.
- Verifikasi periode KRS, tahun ajaran aktif, kurikulum, prasyarat, jadwal, ruang, dosen pengampu, serta kapasitas kelas.
- Minta mahasiswa mengunggah KHS masing-masing. Jangan memasukkan KHS milik orang lain.
- Pastikan backup database, pemantauan error, kebijakan retensi dokumen, dan saluran bantuan kampus sudah tersedia.

## Keamanan dan privasi

- Endpoint impor roster, ringkasan roster, dan template hanya dapat digunakan Admin Prodi.
- Pendaftaran manual hanya dapat membuat role `mahasiswa`; mahasiswa tidak dapat menetapkan role dosen atau admin melalui payload.
- Tidak ada kode pendaftaran/undangan yang diminta oleh halaman pendaftaran atau API registrasi.
- Password mahasiswa disimpan dalam bentuk hash. Password awal akun baru hanya dikembalikan kepada Admin yang melakukan impor dan tidak disimpan dalam bentuk teks biasa.
- Impor menggunakan transaksi dan menolak konflik identitas agar data akun tidak tertimpa tanpa pemeriksaan.
- Audit log mencatat aktivitas pendaftaran/impor tanpa menyimpan password.
- File roster dan file kredensial berisi data pribadi. Batasi akses, distribusikan secara pribadi, dan hapus salinan sesuai kebijakan kampus.

## Batasan integrasi

CourseRecom belum terhubung langsung ke SIAKAD/SSO UHAMKA. Pendaftaran manual memvalidasi format dan keunikan NIM, tetapi tidak melakukan verifikasi otomatis terhadap sistem akademik kampus. Admin perlu mencocokkan roster dengan sumber resmi fakultas/program studi. Integrasi identitas otomatis memerlukan API/SSO resmi dan otorisasi dari UHAMKA.
