# Panduan Demonstrasi

## Prasyarat

Jalankan dari workspace project CourseRecom.

Backend:

```powershell
cd .\backend
..\ .venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend:

```powershell
cd .\frontend
npm run dev
```

Sesuaikan environment lokal tanpa menyalin atau menampilkan isi file rahasia.

## Data Sintetis untuk Demonstrasi

Gunakan hanya akun dan data test yang sudah disediakan atau buat dengan nama NIM sintetis, misalnya:

- `MHS-DEMO-001`
- `DOSEN-DEMO-001`
- Mata kuliah: kode sintetis yang berasal dari dataset test atau katalog demo

Jangan menampilkan password, token, API key, secret, atau NIM mahasiswa nyata pada tangkapan layar.

## Alur Demonstrasi Utama

1. Buka aplikasi dan tampilkan halaman awal.
2. Login sebagai mahasiswa sintetis.
3. Buka profil dan tampilkan minat, semester, IPK, serta kuota sintetis.
4. Buka KHS dan unggah PDF/gambar sintetis yang telah disiapkan.
5. Periksa preview dan ubah nilai hanya jika data sintetis memerlukan koreksi.
6. Konfirmasi KHS dan tunggu status berhasil.
7. Buka rekomendasi.
8. Perlihatkan score dan minimal satu alasan.
9. Tambahkan mata kuliah valid ke Draft KRS.
10. Pastikan tombol dan total SKS menampilkan hasil yang benar.
11. Ajukan KRS dan buka kembali status `pending`.
12. Logout tanpa menampilkan token.
13. Login sebagai dosen sintetis.
14. Buka rencana mahasiswa.
15. Berikan catatan revisi atau setujui.
16. Tampilkan hasil status dan catatan yang tersimpan.

## Validasi yang Wajib Ditunjukkan

- Password kurang dari aturan backend ditolak.
- Mata kuliah prasyarat belum terpenuhi ditandai sebagai ditolak.
- Total SKS melebihi kuota ditolak.
- Pengajuan dua pending dicegah.
- Mahasiswa tidak dapat mengakses aksi dosen/admin.
- Laporan UI setelah refresh tetap menampilkan status final yang tersimpan.

## Hasil yang Harus Terlihat

- Halaman awal dan identitas akun demo.
- Feedback sukses atau error yang jelas.
- Score/alasan rekomendasi.
- Draft KRS dengan total SKS.
- Status `pending` pada mahasiswa.
- Status `approved` atau `revision`, catatan dosen, dan pembaruan setelah refresh.

## Batas Demonstrasi

Sesi ini tidak mengambil screenshot UI nyata karena tidak ada browser dibagikan pada automation. File daftar screenshot berisi nama dan instruksi screenshot manual.
