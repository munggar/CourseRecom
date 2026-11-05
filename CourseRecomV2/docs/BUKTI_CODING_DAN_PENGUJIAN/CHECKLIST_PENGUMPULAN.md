# Checklist Pengumpulan

## Status Penyediaan

| No. | Persyaratan dosen | Bukti saat ini | Status | Bahan manual yang perlu ditambahkan |
|---|---|---|---|---|
| 1 | Dokumentasi identitas dan alasan pemilihan fitur | `DOKUMENTASI_FITUR.md` | **TERSEDIA** | Tidak ada, kecuali judul mata kuliah/kelas menurut format dosen |
| 2 | User story dan acceptance criteria | `DOKUMENTASI_FITUR.md` | **TERSEDIA** | Sesuaikan nama kelompok bila diperlukan |
| 3 | Input, proses, penyimpanan, dan output fitur | `DOKUMENTASI_FITUR.md` | **TERSEDIA** | Screenshot data sintetis untuk bukti visual |
| 4 | Bukti pengujian minimal lima skenario | `HASIL_PENGUJIAN.md` | **TERSEDIA** | Tambahkan screenshot UI jika ingin bukti visual |
| 5 | Alur utama valid | Hasil workflow backend pada suite pytest | **TERSEDIA SEBAGIAN** | Browser E2E: login → KHS → recommendation → submit → review |
| 6 | Input valid | Test registrasi, KHS, katalog, KRS | **TERSEDIA** | Screenshot form yang valid |
| 7 | Input kosong/tidak valid | Test password dan validasi backend | **TERSEDIA SEBAGIAN** | Screenshot pesan UI kosong dan format tidak valid |
| 8 | Kondisi error/recovery | RBAC, approved lock, duplicate submit | **TERSEDIA SEBAGIAN** | Simulasi database/API downstream gagal |
| 9 | Uji ulang setelah perbaikan | Suite backend `34 passed` | **TERSEDIA SEBAGIAN** | Screenshot pengujian ulang UI bila bug UI direproduksi |
| 10 | Daftar bug dan langkah reproduksi | `BUG_DAN_PERBAIKAN.md` | **TERSEDIA** | Tambahkan bukti sebelum/perbaikan bila bug UI benar-benar direkam |
| 11 | Penyebab dan tindakan perbaikan | `BUG_DAN_PERBAIKAN.md` | **TERSEDIA** | Bukti diff/commit hanya jika bug benar-benar ditemukan |
| 12 | Panduan menjalankan aplikasi | `PANDUAN_DEMONSTRASI.md` | **TERSEDIA** | Sesuaikan alamat port lokal dan akun demo lingkungan |
| 13 | Data sintetis demonstrasi | `PANDUAN_DEMONSTRASI.md` | **TERSEDIA** | Buat file data sintetis tanpa kredensial nyata |
| 14 | Daftar screenshot minimal | `DAFTAR_BUKTI_SCREENSHOT.md` | **TERSEDIA** | Ambil seluruh screenshot yang tercantum |
| 15 | Potongan kode utama | `POTONGAN_KODE_UTAMA.md` | **TERSEDIA** | Tidak perlu seluruh source code |
| 16 | Bukti test backend | Perintah dan hasil test tercatat | **TERSEDIA** | Screenshot terminal tanpa secret |
| 17 | Bukti lint/build frontend | Perintah dan hasil tercatat | **TERSEDIA** | Screenshot terminal lint/build |
| 18 | Screenshot bug sebelum/perbaikan | Belum tersedia, dan tidak ada bug UI yang direkam | **PERLU VERIFIKASI MANUAL** | Ambil hanya jika bug berhasil direproduksi pada aplikasi |
| 19 | Bukti aplikasi warung benar-benar dijalankan | Tidak tersedia pada workspace | **BLOCKED** | Wajib buka workspace WarungPintar yang sesuai atau lampirkan implementation yang benar |
| 20 | Fitur sesuai kebutuhan pemilik warung | Tidak dapat dibuktikan pada workspace CourseRecom | **BLOCKED** | Cocokkan dengan implementasi WarungPintar yang nyata dan proposal/WBS milik kelompok |

## Berkas Sudah Dibuat

- `DOKUMENTASI_FITUR.md`
- `HASIL_PENGUJIAN.md`
- `BUG_DAN_PERBAIKAN.md`
- `PANDUAN_DEMONSTRASI.md`
- `DAFTAR_BUKTI_SCREENSHOT.md`
- `POTONGAN_KODE_UTAMA.md`

## Item yang Belum Dapat Dipenuhi Oleh AI

- Membuka aplikasi WarungPintar yang tidak ada pada workspace.
- Mengambil screenshot browser yang nyata tanpa browser dibagikan.
- Membuktikan user acceptance dengan pengguna nyata.
- Membuktikan service external/ database failure tanpa environment terisolasi.
- Menetapkan laporan aplikasi sebagai 100% bebas bug.

## Urutan Pengumpulan

1. Jalankan backend dan frontend di workspace.
2. Gunakan data sintetis dan hindari data produksi.
3. Ambil screenshot sesuai `DAFTAR_BUKTI_SCREENSHOT.md`.
4. Jalankan ulang pytest, frontend lint, dan frontend build.
5. Simpan screenshot di `screenshots/`.
6. Perbarui status manual pada checklist.
7. Pastikan tidak ada token, password, atau secret pada screenshot.
8. Ekspor atau zip folder bukti untuk pengumpulan.
