export const GUIDE_SECTIONS = [
  {
    role: 'Semua Akun',
    title: 'Masuk, navigasi, dan keamanan akun',
    intro: 'Mulai dari halaman login, gunakan peran yang sesuai dengan akun, lalu kenali menu yang tersedia sesuai kewenangan.',
    steps: [
      'Pilih Mahasiswa, Dosen PA, atau Admin Prodi pada halaman masuk. Mahasiswa dapat masuk dengan akun yang dibuat sendiri atau akun yang dibuatkan Admin Prodi.',
      'Mahasiswa dapat mendaftar manual tanpa kode pendaftaran. Admin Prodi juga dapat mengimpor roster Excel/CSV; bila NIM sudah memiliki akun manual dan identitasnya cocok, sistem menautkan akun tersebut tanpa membuat duplikat atau mengganti password.',
      'Menu Dashboard menampilkan ringkasan sesuai peran. Sidebar di desktop atau menu hamburger di ponsel berpindah halaman; menu Panduan selalu tersedia.',
      'Buka Edit Profil untuk memperbarui nama, username, email, nomor telepon, dan password. Perubahan password meminta password saat ini.',
      'Gunakan Keluar untuk mengakhiri sesi. Jangan membagikan password atau membiarkan akun tetap terbuka di perangkat umum.',
      'Reset password mandiri tidak tersedia pada halaman login. Hubungi Admin Prodi/pengelola aplikasi melalui prosedur kampus bila tidak dapat mengakses akun.'
    ]
  },
  {
    role: 'Mahasiswa',
    title: 'Persiapan data akademik dan profil minat',
    intro: 'Pastikan identitas akademik dan KHS lengkap sebelum meminta rekomendasi semester berikutnya.',
    steps: [
      'Periksa Dashboard dan Edit Profil. Program studi serta angkatan berasal dari data akademik akun dan tidak dapat diubah bebas melalui profil.',
      'Buka Minat & Profil, pilih bidang minat yang tersedia untuk program studi, kemudian Simpan Minat. Pilihan minat menjadi salah satu sinyal rekomendasi.',
      'Buka Kurikulum untuk melihat daftar mata kuliah, SKS, semester yang ditawarkan, kategori, prasyarat, keterangan, dan jadwal umum.',
      'Pada Upload KHS, unggah satu PDF lengkap atau maksimal 10 foto halaman KHS (JPG, PNG, WEBP, TIFF, atau BMP; total maksimal 20 MB).',
      'Periksa pratinjau hasil pembacaan. Koreksi identitas, mata kuliah, SKS, grade dan nilai angka; pastikan setiap IPS semester wajib terisi. IPK dihitung otomatis dari rata-rata IPS.',
      'Pilih Konfirmasi & Simpan hanya setelah data sesuai dokumen resmi. Dokumen yang belum dikonfirmasi masih dapat dilanjutkan atau dibuang dari halaman Upload KHS.',
      'Buka Riwayat KHS untuk memeriksa dokumen terkonfirmasi. Nilai angka dan IPS yang keliru dapat dikoreksi; IPK mengikuti perhitungan rata-rata IPS.'
    ]
  },
  {
    role: 'Mahasiswa',
    title: 'Rekomendasi, kelas paralel, dan pengajuan KRS',
    intro: 'Gunakan rekomendasi sebagai bahan pertimbangan, lalu susun KRS sesuai aturan akademik, jadwal, dan kuota kelas.',
    steps: [
      'Setelah KHS dikonfirmasi, buka Rekomendasi MK. Sistem menggabungkan riwayat akademik, kemiripan mahasiswa, minat, prasyarat, dan katalog kurikulum. Jika data pembanding terbatas, sistem menggunakan content-based fallback.',
      'Mata kuliah wajib ditambahkan otomatis ke Draft KRS dan tidak dapat dihapus. Tinjau rekomendasi pilihan, alasan, faktor skor, serta daftar mata kuliah yang tidak direkomendasikan.',
      'Tambahkan mata kuliah pilihan ke draft. Periksa total SKS terhadap kuota berdasarkan IPK: 24 SKS untuk IPK ≥ 3,35; 22 SKS untuk IPK ≥ 3,00 dan di bawah 3,35; selain itu 20 SKS.',
      'Untuk mata kuliah yang memiliki kelas paralel, pilih kelas yang dibuka prodi. Perhatikan nama kelas, dosen, hari, jam, ruang, serta sisa kursi. Kelas penuh tidak dapat dipilih.',
      'Pastikan tidak ada bentrok waktu antar mata kuliah. Pemeriksaan dilakukan kembali oleh server saat KRS dikirim sehingga perubahan kuota atau jadwal tidak dapat dilewati hanya dengan mengubah tampilan.',
      'Tekan Ajukan ke Dosen PA. Pengajuan hanya dapat dikirim saat periode KRS aktif, KHS sudah siap, Dosen PA telah ditetapkan, dan tidak ada pengajuan pending lain.',
      'Pantau status KRS. Jika diminta revisi, baca catatan dosen dan mata kuliah yang ditandai; perbaiki draft lalu ajukan ulang. KRS yang disetujui akan terkunci.',
      'Setelah disetujui, unduh PDF KRS Resmi dan gunakan QR code pada dokumen untuk memeriksa keaslian dokumen.',
      'Untuk mengubah KRS yang telah disetujui, ajukan KPRS saat periode KPRS dibuka. Isi kode mata kuliah yang diinginkan dan alasan minimal 10 karakter; perubahan menunggu keputusan Dosen PA.'
    ]
  },
  {
    role: 'Dosen PA',
    title: 'Bimbingan dan pemeriksaan KRS mahasiswa',
    intro: 'Dosen PA memproses mahasiswa bimbingan yang ditetapkan Admin Prodi; data mahasiswa di luar daftar bimbingan tidak dapat diakses untuk review.',
    steps: [
      'Masuk dengan peran Dosen PA. Akun Dosen PA dibuat atau dikelola Admin Prodi; gunakan username/NIP dan password yang diberikan.',
      'Buka Bimbingan Mahasiswa untuk melihat daftar mahasiswa bimbingan beserta ringkasan data akademik dan aktivitas pengajuan.',
      'Buka pengajuan KRS berstatus menunggu. Periksa identitas, semester, daftar mata kuliah, SKS, kelas paralel, dosen pengampu, jadwal, dan informasi akademik yang tersedia.',
      'Pilih Setujui bila rencana studi valid. Server akan memvalidasi ulang kurikulum, prasyarat, batas SKS, jadwal, kelas yang masih dibuka, dan kapasitas sebelum persetujuan disimpan.',
      'Pilih Minta Revisi bila ada mata kuliah yang harus diperbaiki. Tulis alasan yang jelas minimal 10 karakter dan tandai satu atau lebih mata kuliah pilihan yang perlu direvisi. Mata kuliah wajib tidak dapat ditolak.',
      'Mahasiswa akan melihat alasan revisi per mata kuliah dan dapat memperbaiki serta mengajukan ulang. Riwayat keputusan tetap tercatat untuk transparansi bimbingan.',
      'Pada bagian Pengajuan KPRS, bandingkan daftar sebelum dan sesudah. Isi catatan keputusan, lalu Setujui, Minta Revisi, atau Tolak. Keputusan revisi/penolakan harus menyertakan alasan yang memadai.',
      'Gunakan status dan riwayat pada halaman bimbingan untuk memantau hasil. Dosen PA tidak mengubah katalog, kuota kelas, atau penetapan Dosen PA.'
    ]
  },
  {
    role: 'Admin Prodi',    title: 'Dashboard, akun, dan penetapan Dosen PA',
    intro: 'Admin mengelola data operasional program studi dan menjadi pengendali konfigurasi akademik.',
    steps: [
      'Masuk sebagai Admin Prodi. Dashboard menampilkan ringkasan mahasiswa, KHS terkonfirmasi, dosen PA, distribusi katalog, serta data mahasiswa.',
      'Pada Dashboard, tetapkan atau ubah Dosen PA per mahasiswa. Perubahan dapat disertai alasan dan masuk ke Riwayat Dosen PA.',
      'Buka Daftar Akun Dosen PA untuk mendaftarkan, mengubah, atau menghapus akun dosen. Penghapusan akun melepaskan relasi bimbingan tanpa menghapus rekam jejak audit.',
      'Gunakan Riwayat Dosen PA untuk menelusuri dosen sebelumnya, dosen baru, admin yang melakukan perubahan, tanggal, dan alasan penetapan.',
      'Pada Manajemen Data, tambah, edit, atau nonaktifkan mata kuliah; kelola kode, nama, SKS, semester tersedia, kategori, prasyarat, keterangan, jadwal umum, dan kuota.',
      'Impor katalog melalui CSV atau Excel. Periksa isi berkas sebelum mengimpor karena berkas tertentu dapat menggantikan katalog aktif; lakukan pencadangan data sumber terlebih dahulu.',
      'Pada bagian Periode dan Batas Akademik, atur tahun ajaran, awal/akhir periode KRS, deadline pengisian, periode KPRS, dan aturan kuota SKS berdasarkan IPS.',
      'Gunakan bagian Override KRS hanya untuk koreksi administratif yang beralasan. Setiap override dicatat dan tidak menggantikan proses review normal tanpa alasan.'
    ]
  },
  {
    role: 'Admin Prodi',
    title: 'Kelas paralel, jadwal, kapasitas, dan pelaporan',
    intro: 'Kelola kelas per mata kuliah dan semester agar pilihan mahasiswa, jadwal, dosen, ruangan, serta sisa kursi konsisten.',
    steps: [
      'Buka menu Kelas & Jadwal. Pilih mata kuliah aktif, isi nama kelas paralel, dosen pengampu, ruang, hari, jam mulai/selesai, kapasitas, dan semester.',
      'Simpan kelas untuk menerbitkan pilihan pada alur KRS mahasiswa. Kelas dapat diedit atau ditutup; penutupan ditolak saat masih ada peserta/reservasi. Kapasitas tidak dapat diturunkan di bawah kursi yang telah terpakai.',
      'Sistem memeriksa bentrok ruang dan dosen pada interval waktu yang tumpang tindih, termasuk lintas semester. Selesaikan bentrok sebelum kelas dibuka.',
      'Kelas yang sudah dibuka ditampilkan pada Draft KRS beserta dosen, ruang, waktu, dan kursi tersisa. Kuota dihitung per kelas paralel, bukan hanya berdasarkan jumlah mahasiswa pada mata kuliah.',
      'Buka Riwayat Aktivitas pada Manajemen Data untuk menelusuri perubahan katalog, pengaturan, dan aktivitas administratif. Audit log menyimpan metadata perubahan, bukan isi berkas KHS/KRS.',
      'Gunakan laporan mahasiswa tanpa KRS dan peserta per mata kuliah untuk pemantauan. Bagian model menyediakan pelatihan/evaluasi; jalankan Latih/Evaluasi Ulang Model hanya setelah dataset cukup dan tinjau metriknya.',
      'Precision@5 dan Recall@5 yang belum tersedia berarti model belum memiliki evaluasi tersimpan yang memadai; jangan menafsirkan skor rekomendasi sebagai probabilitas lulus.'
    ]
  }
];