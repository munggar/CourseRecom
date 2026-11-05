# Hasil Pengujian

## Lingkup Bukti

Pengujian backend dijalankan pada 3 November 2026 dengan data sintetis dan TestClient. Tidak ada akses atau penulisan secret dalam laporan.

## Bukti Perintah

```text
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

Hasil aktual:

```text
34 passed, 162 warnings
```

```text
cd frontend
npm run lint
```

Hasil: exit code 0.

```text
cd frontend
npm run build
```

Hasil: exit code 0 dan bundle production berhasil dibuat.

## Status yang Digunakan

- `LULUS`
- `GAGAL`
- `BLOCKED`
- `BELUM DIUJI`

## Tabel Hasil

| No. | Fitur/skenario | Data atau langkah uji | Hasil yang diharapkan | Hasil aktual | Status |
|---|---|---|---|---|---|
| 1 | Login dan akses role | Login mahasiswa sintetis lalu minta identitas sendiri | Akses mahasiswa berhasil; endpoint admin ditolak dengan 403 | Test RBAC dan login pada suite backend pass | **LULUS** |
| 2 | Registrasi input valid | POST NIM sintetis baru dan password valid; request mengirim role lain | Akun baru dibuat sebagai mahasiswa dan dapat login | Test registrasi pass; role dipaksa mahasiswa | **LULUS** |
| 3 | Registrasi input tidak valid | Password pendek | API menolak dengan 422 | Test schema pass | **LULUS** |
| 4 | KHS preview sebelum konfirmasi | Unggah data sintetis lalu panggil preview | Preview tersedia; StudentRecord tidak tersimpan sebelum konfirmasi | Workflow test pass | **LULUS** |
| 5 | Konfirmasi KHS valid | Konfirmasi metadata dan mata kuliah sintetis | Riwayat KHS tersimpan sebagai confirmed dan aktif | Workflow test pass | **LULUS** |
| 6 | Prasyarat tidak terpenuhi | Ajukan mata kuliah dengan prasyarat belum lulus | Backend menolak sebagai rekomendasi tidak valid | Test rekomendasi/validation pass | **LULUS** |
| 7 | Kuota SKS melebihi batas | Kombinasikan mata kuliah yang totalnya lebih tinggi dari kuota | Backend menolak atau menandai tidak valid | Test SKS pass | **LULUS** |
| 8 | Pengajuan KRS valid | Mahasiswa dengan KHS dan kuota valid mengirim kode mata kuliah valid | StudyPlan `pending` tersimpan dan data JSON dapat dibaca | Workflow backend test pass | **LULUS** |
| 9 | Double submit/dua pending | Kirim dua pengajuan pending untuk mahasiswa yang sama | Satu `pending`; pengajuan lain ditolak 409 atau integrity conflict | Partial unique index dan test database pass | **LULUS** |
| 10 | Review Dosen PA | Dosen menyetujui rencana dan menambahkan catatan revisi pada skenario terpisah | Status, catatan, dan reviewer tersimpan | Test review dosen pass | **LULUS** |
| 11 | Akses approved terkunci | Ubah rencana yang sudah `approved` | Backend menolak dengan 409 | Test review Dosen PA pass | **LULUS** |
| 12 | Impor katalog valid | Impor XLSX/CSV sintetis berisi prasyarat dan semester berulang | Catalog berhasil dipetakan dan digabung | Test course catalog pass | **LULUS** |
| 13 | API lintas role | Mahasiswa mengakses endpoint admin | 403 | Test RBAC pass | **LULUS** |
| 14 | Frontend lint/build | Jalankan lint dan build production | Tidak ada error lint; bundle production tersusun | Keduanya exit code 0 pada pemeriksaan aktual | **LULUS** |
| 15 | Database unavailable | Matikan database pada environment terisolasi dan panggil endpoint | Error ditangani; koneksi gagal tanpa bocornya detail rahasia | Skenario belum dijalankan pada proses aktual | **BELUM DIUJI** |
| 16 | API eksternal gagal | Matikan/mock layanan Gemini menjadi timeout/error | Rekomendasi utama tetap berjalan dengan fallback aman atau pesan error terkontrol | Tidak ada test failure nyata pada layanan upstream | **BELUM DIUJI** |
| 17 | UI end-to-end browser | Login → KHS → recommendation → submit → review pada browser nyata | Tampilan dan database sinkron pada setiap role | Browser tidak dibagikan dan automation belum tersedia | **BLOCKED** |
| 18 | Unduh laporan PDF | Klik tombol unduh pada draft/rekomendasi | File PDF valid dapat dibuka | Tidak ditemukan route, tombol, atau generator PDF pada repository | **GAGAL** |

## Kesimpulan Pengujian

- Tidak ada test backend yang gagal pada suite aktual.
- Frontend tidak memiliki test komponen/E2E yang dieksekusi pada sesi ini.
- Status `GAGAL` untuk PDF merupakan gap implementasi yang terbukti melalui pencarian repository dan bukan hasil runtime yang beruntung.
- Status aplikasi tidak boleh dinyatakan 100% bebas bug.
