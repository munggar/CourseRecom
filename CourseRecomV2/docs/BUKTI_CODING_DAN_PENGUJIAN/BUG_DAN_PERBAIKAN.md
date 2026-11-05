# Bug dan Perbaikan

## Catatan Status

Pada pengujian suite backend aktual, tidak ada kegagalan yang dapat direproduksi pada implementasi CourseRecom yang diuji. Oleh karena itu tidak ada bug runtime yang berhasil diperbaiki dalam sesi ini. Temuan berikut adalah gap atau kondisi yang masih memerlukan bukti tambahan.

| ID | Deskripsi | Lokasi | Prioritas | Penyebab | Langkah reproduksi | Tindakan | Hasil pengujian ulang |
|---|---|---|---|---|---|---|---|
| BUG-WP-001 | Fitur inti WarungPintar tidak tersedia pada workspace | Root workspace dan source frontend/backend | Critical | Workspace berisi CourseRecom dan tidak mempunyai domain warung | Cari istilah kasir, produk, stok, penjualan; tidak ada hasil pada source backend | Buka workspace WarungPintar yang benar sebelum pengujian feature warung | **BLOCKED**; belum ada implementasi untuk diuji ulang |
| GAP-001 | PDF draft/rekomendasi belum tersedia | `frontend/src/App.jsx`; route `backend/app/api/routes/*.py` | High | Tidak ada generator atau endpoint download PDF | Buka fitur draft dan cari tombol/route unduh PDF; tidak ditemukan | Persyaratan perlu dipenuhi atau dikonfirmasi sebagai di luar scope tugas; tambahkan test download yang aman | Belum dilakukan perbaikan pada kode; suite backend tetap 34 pass |
| GAP-002 | Database outage belum diuji | `backend/app/database.py` | High | Tidak ada skenario terisolasi yang memutus database pada sesi ini | Konfigurasikan database unavailable lalu panggil endpoint protected | Tambah test koneksi gagal dan verifikasi response tidak mengungkap detail rahasia | **BELUM DIUJI** |
| GAP-003 | Failure Gemini belum memiliki bukti nyata | `backend/app/ai_explainer.py` | Medium | Integrasi eksternal tidak dipanggil sebagai jalur utama dan belum dimock | Set layanan upstream ke timeout/error lalu jalankan rekomendasi | Mock error upstream dan verifikasi fallback/penanganan error | **BELUM DIUJI** |
| GAP-004 | Browser E2E dan responsivitas belum dibuktikan | `frontend/src/App.jsx`; `frontend/src/App.css` | High | Browser belum dibagikan dan repository belum mempunyai test browser terkonfigurasi | Jalankan alur UI desktop/mobile; tidak dapat dieksekusi dalam sesi ini | Tambahkan/test dengan Playwright pada viewport sintetis | **BLOCKED/ BELUM DIUJI** |

## Verifikasi Perbaikan Existing Double Submit

Partial unique index dan penanganan `IntegrityError` adalah perbaikan yang sudah ada sebelum paket bukti ini disiapkan.

Lokasi:

- `backend/app/models.py`
- `backend/app/api/routes/mahasiswa.py`
- `frontend/src/App.jsx`
- `backend/tests/test_database_config.py`

Pengujian ulang:

```text
34 passed, 162 warnings
```

Test khusus partial unique index pada suite database lulus. Tidak ada bukti screenshot sebelum/perbaikan pada browser UI; bukti saat ini adalah hasil test database dan source.

## Tidak Ada Klaim 100% Bebas Bug

Dokumen ini tidak menyatakan aplikasi bebas bug. Kondisi database, layanan eksternal, browser desktop/mobile, dan PDF masih memerlukan bukti manual atau automated test tambahan.
