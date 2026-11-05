# CourseRecomV2 - Laporan Rekonsiliasi Audit Terbaru

Tanggal audit: 2026-11-05

## Ringkasan

Laporan ini memakai daftar resmi `BUG-01` sampai `BUG-32`; arti definisi tidak diubah. Temuan tambahan lama dipisahkan menjadi `NEW-01` sampai `NEW-04`.

Laporan lama tidak dipakai sebagai bukti bahwa suatu bug sudah fixed. Pengujian browser tidak tersedia, sehingga UI belum dinyatakan sebagai E2E.

## BUG resmi

| ID | Definisi resmi | Status | Bukti |
|---|---|---|---|
| BUG-01 | Penghapusan mahasiswa dan penanganan foreign key. | FIXED | `test_admin_dashboard_lists_students_and_advisors_and_only_admin_can_delete_students`. |
| BUG-02 | Risiko penyimpanan JWT di localStorage. | NOT FIXED | Frontend masih menyimpan JWT di localStorage; belum ada HttpOnly cookie. |
| BUG-03 | Draft KRS bocor antar-akun. | PARTIALLY FIXED | Draft di-prefix NIM dan dibersihkan saat logout; belum ada browser test lintas akun. |
| BUG-04 | Otorisasi dan kepemilikan data saat perubahan data. | FIXED | Test RBAC/ownership pada `test_api_rbac.py`. |
| BUG-05 | Validasi KPRS belum menyeluruh. | FIXED | Submit dan review KPRS pada `test_kprs_workflow.py`. |
| BUG-06 | Validasi KRS dan KPRS tidak konsisten. | FIXED | Jalur backend memakai validator akademik bersama. |
| BUG-07 | Validasi konfigurasi batas SKS. | FIXED | `test_academic.py`; batas SKS diuji server-side. |
| BUG-08 | Manipulasi grade_point dari frontend. | FIXED | Nilai grade_point berasal KHS/server; `test_khs_parser.py`, `test_khs_workflow.py`. |
| BUG-09 | Admin override melewati validasi. | FIXED | `test_admin_override_can_unlock_and_replace_courses`. |
| BUG-10 | Pemeriksaan bentrok berdasarkan interval waktu. | FIXED | `test_schedule_conflict`. |
| BUG-11 | Bentrok dosen dan ruangan. | FIXED | Validasi backend jadwal dosen dan ruang pada layanan akademik. |
| BUG-12 | Bentrok jadwal mahasiswa. | FIXED | Validasi jadwal mahasiswa pada jalur akademik/KPRS. |
| BUG-13 | Race condition kapasitas mata kuliah. | FIXED | Lock dan transaction kapasitas pada jalur backend. |
| BUG-14 | Ketidakkonsistenan datetime naive dan aware. | FIXED | Normalisasi pada `app/services/time_utils.py`; suite backend lulus. |
| BUG-15 | Risiko penghapusan StudentRecord saat konfirmasi KHS. | FIXED | Workflow KHS mempertahankan StudentRecord dan diuji API/database. |
| BUG-16 | Payload konfirmasi KHS tidak sesuai hasil preview. | FIXED | `test_khs_workflow.py`. |
| BUG-17 | Deduplikasi riwayat pengulangan mata kuliah. | FIXED | `test_khs_parser.py`, `test_khs_workflow.py`. |
| BUG-18 | Penyimpanan dan pengunduhan beberapa dokumen KHS. | FIXED | Workflow penyimpanan dan endpoint download KHS. |
| BUG-19 | Perhitungan IPK dan IPS. | FIXED | `test_academic.py`, `test_khs_workflow.py`. |
| BUG-20 | Penggunaan katalog mata kuliah statis. | FIXED | `test_course_catalog_integrity.py`. |
| BUG-21 | Variabel `now` tidak didefinisikan pada submit KPRS. | FIXED | Submit KPRS di `test_kprs_workflow.py` lulus. |
| BUG-22 | Parsing periode KPRS sebelum validasi keberadaan periode. | FIXED | Endpoint KPRS memvalidasi periode sebelum parsing. |
| BUG-23 | Alur KPRS belum tersambung ke frontend dosen. | PARTIALLY FIXED | API dosen tersedia; UI browser belum teruji. |
| BUG-24 | PDF KRS lama setelah isi KRS berubah. | FIXED | `test_old_official_krs_is_rejected_after_plan_changes`. |
| BUG-25 | QR verification tidak memeriksa versi dokumen secara benar. | FIXED | Token QR berisi SHA-256; verifikasi menolak hash lama. |
| BUG-26 | Blob URL dicabut terlalu cepat. | PARTIALLY FIXED | Penghapusan ditunda 1000 ms; belum ada browser test lintas browser. |
| BUG-27 | Ketidakkonsistenan form registrasi dan reset. | PARTIALLY FIXED | Registrasi/reset memiliki validasi backend, tetapi reset/browser belum teruji lengkap. |
| BUG-28 | Seed akun demo aktif secara default. | FIXED | `test_database_config.py`; seed dibatasi development/testing. |
| BUG-29 | Kredensial demo terlihat pada halaman login. | FIXED | UI disembunyikan production dan backend login demo diblokir. |
| BUG-30 | Secret production tidak aman atau menggunakan nilai default. | FIXED | `test_database_config.py`; startup menolak secret kosong/default dan membedakan QR/JWT. |
| BUG-31 | Fallback alamat API ke localhost pada deployment. | FIXED | `test_verification_url_does_not_fallback_to_localhost_in_production`. |
| BUG-32 | Paket distribusi mengandung file sensitif atau tidak diperlukan. | FIXED | Backend/frontend `.dockerignore` ditambahkan dan ditinjau statis. |

## Temuan tambahan

| ID | Status | Bukti |
|---|---|---|
| NEW-01 | FIXED | Test perubahan password, username, logout, login ulang, dan isolasi akun pada `test_security_completion.py`. |
| NEW-02 | PARTIALLY FIXED | Endpoint admin/history dan UI tersedia; route admin E2E belum tersedia. |
| NEW-03 | FIXED | Migration, model, schema, API, persistence dan validasi pada test profil. |
| NEW-04 | FIXED | UI membatasi kredensial demo berdasarkan environment; production seed/login dibatasi. |

## Fitur utama

- `FITUR-LOGIN`: Role dapat dipilih di frontend dan diverifikasi backend. PARTIALLY FIXED; kombinasi role/mutasi request memerlukan browser/manual.
- `FITUR-KRS`: Student cancel/change/add/reason/initial proposed serta advisor review tersedia di API. PARTIALLY FIXED sampai E2E/manual.
- `FITUR-PROFIL`: Student, advisor, dan admin memiliki profil, phone, password update di backend/frontend. PARTIALLY FIXED untuk browser lintas role.
- `FITUR-ADVISOR`: Assignment/reassignment/history dan advisor roster tersedia. PARTIALLY FIXED untuk browser dan pembuktian akses lintas dosen.

## File diperiksa/diubah

- Backend: `app/config.py`, `app/deps.py`, `app/api/routes/auth.py`, `app/api/routes/admin.py`, `app/api/routes/dosen.py`, `app/api/routes/mahasiswa.py`, `app/services/official_krs.py`, migration `alembic/versions/20261105_02_phone_token.py`.
- Frontend: `frontend/src/App.jsx`.
- Packaging: backend dan frontend `.dockerignore`.
- Test: `test_security_completion.py`, `test_advisor_history.py`, `test_database_config.py`, `test_official_krs.py`, `test_profile_regressions.py`, `test_kprs_workflow.py`, serta suite akademik/KHS/API.

## Hasil pengujian aktual

- `python -m compileall -q app`: berhasil.
- `python -m pytest -q`: 71 passed dalam 28.13 detik.
- `npm run lint`: berhasil.
- `npm run build`: berhasil, 1896 module ditransformasikan dan `dist` terbentuk.
- `python -m json.tool AUDIT_REPORT_FINAL.json`: perlu dijalankan untuk memverifikasi laporan JSON.

## Pengujian database

Migration `20261105_02_phone_token.py` diuji pada SQLite. Migration menambah `phone_number` dan `token_version`, dengan default/backfill aman. Migrasi PostgreSQL nyata belum dijalankan pada sesi ini.

## Browser/E2E dan manual

Tidak ada Playwright atau browser automation yang tersedia. Manual diperlukan untuk login ketiga role, draft lintas akun, KPRS mahasiswa/dosen, profil, advisor assignment/history, dan lifecycle Blob download/PDF.

## Risiko tersisa

- JWT tetap disimpan di localStorage (BUG-02); risiko XSS perlu mitigasi cookie HttpOnly atau keputusan arsitektur lain.
- Browser E2E belum tersedia dan status UI sebagian bersifat API/static review.
- Deployment PostgreSQL serta public HTTPS/API URL perlu diverifikasi pada environment hosting sebenarnya.
- Kebijakan jumlah perubahan KPRS, revisi dosen, dan tenggat waktu akademik memerlukan keputusan akademik.
