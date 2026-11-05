# Daftar Bukti Screenshot

## Aturan Pengambilan

Ambil screenshot dari aplikasi yang benar-benar berjalan. Jangan memakai mockup, desain statis, atau foto editor sebagai bukti.

- Sembunyikan password, token, API key, dan secret.
- Gunakan data sintetis.
- Jangan menyertakan kredensial akun nyata.
- Screenshot terminal dapat menutupi informasi environment dan secret.
- Setelah screenshot tersedia, letakkan file pada folder `docs/BUKTI_CODING_DAN_PENGUJIAN/screenshots/`.

## Daftar Screenshot Minimum

| No. | Nama file | Bagian aplikasi/terminal | Yang harus ditampilkan | Tujuan |
|---|---|---|---|---|
| 1 | `01-tampilan-awal.png` | Halaman awal aplikasi yang berjalan | Header aplikasi, pilihan login/register, identitas CourseRecom | Membuktikan aplikasi dapat dibuka |
| 2 | `02-dashboard-mahasiswa.png` | Dashboard mahasiswa sintetis | Identitas sintetis, semester/IPK/SKS, status, menu fitur | Membuktikan halaman fitur role mahasiswa |
| 3 | `03-input-khs.png` | Halaman upload KHS | File sintetis dipilih dan UI menampilkan nama file/status | Membuktikan proses memasukkan KHS |
| 4 | `04-proses-preview-khs.png` | Saat upload/preview dijalankan | Loading atau hasil preview; data sintetis terhitung | Membuktikan KHS diproses |
| 5 | `05-rekomendasi-valid.png` | Halaman rekomendasi | Daftar mata kuliah, score, alasan, dan tombol tambah | Membuktikan rekomendasi dihasilkan |
| 6 | `06-draft-krs.png` | Draft KRS mahasiswa | Mata kuliah dipilih, jumlah SKS, kuota, dan tombol ajukan | Membuktikan proses penyusunan KRS |
| 7 | `07-submit-success.png` | Setelah pengajuan KRS | Pesan berhasil dan status `pending` | Membuktikan penyimpanan berhasil dari UI |
| 8 | `08-review-dosen.png` | Halaman dosen PA | Rencana mahasiswa, catatan, tombol approve/revision | Membuktikan proses review tersedia |
| 9 | `09-review-success.png` | Setelah dosen melakukan aksi | Status dan catatan sukses tersimpan, muncul setelah refresh | Membuktikan output akhir review |
| 10 | `10-validasi-input-kosong.png` | Form yang wajib diisi | Pesan field kosong/wajib diisi | Membuktikan validasi input |
| 11 | `11-validasi-sks.png` | Draft dengan total melebihi kuota sintetis | Pesan validasi kuota dan tombol tidak mengirim data | Membuktikan aturan SKS |
| 12 | `12-double-submit.png` | Dua kali mengirim rencana pending | Pesan konflik atau tombol tetap disabled | Membuktikan double-submit dicegah |
| 13 | `13-bug-sebelum-perbaikan.png` | Jika bug double submit dapat direproduksi secara UI | Kondisi sebelum perbaikan beserta timestamp/request | Bukti bug bila tersedia; wajib hanya jika benar-benar direkam |
| 14 | `14-pengujian-ulang.png` | Setelah perbaikan | Kondisi berhasil mencegah duplikasi dan pesan yang benar | Bukti pengujian ulang |
| 15 | `15-pytest-result.png` | Terminal backend | Ringkasan `34 passed` tanpa path rahasia | Bukti suite backend aktual |
| 16 | `16-frontend-lint-build.png` | Terminal frontend | `npm run lint` dan `npm run build` berhasil | Bukti frontend build aktual |
| 17 | `17-rbac-denied.png` | Mahasiswa mengakses aksi dosen/admin | Respons 403 atau pesan akses ditolak | Bukti hak akses |

## Status Pengambilan

Saat paket ini dibuat, screenshot belum tersedia secara faktual karena tidak ada browser dibagikan pada sesi ini. File tidak boleh dibuat sebagai tangkapan layar palsu atau statis.
