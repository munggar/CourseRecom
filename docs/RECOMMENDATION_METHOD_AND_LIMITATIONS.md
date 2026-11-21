# Metode rekomendasi dan batasan interpretasi

CourseRecom adalah **sistem pendukung keputusan akademik (Decision Support System)**. Sistem membantu mahasiswa dan Dosen PA meninjau pilihan studi; sistem tidak menggantikan keputusan akademik manusia.

## Alur

1. **Rule Engine** memeriksa prasyarat, mata kuliah yang sudah lulus/perlu diulang, semester kurikulum, batas SKS, dan konflik jadwal/kelas.
2. **Hybrid recommendation** menggabungkan collaborative filtering berbasis kemiripan mahasiswa dan content-based signals dari data akademik, minat, prasyarat serta katalog kurikulum.
3. **Validasi server** dijalankan kembali saat draft KRS diajukan dan saat Dosen PA memberi keputusan. Skor rekomendasi tidak dapat melewati aturan akademik.

## Bobot faktor bawaan

| Faktor | Bobot bawaan |
|---|---:|
| Similar students | 30% |
| Academic history | 25% |
| Interest | 20% |
| Curriculum | 15% |
| Course pattern | 10% |

Bobot berasal dari konfigurasi `RECOMMENDATION_WEIGHTS` dan dinormalisasi oleh backend. Nilai di atas adalah default; konfigurasi deployment dapat mengubahnya.

## Rumus kemiripan collaborative filtering

Kemiripan antar histori mahasiswa dihitung dengan:

`similarity = 0.8 × Jaccard(course history) + 0.2 × grade agreement`

- Jaccard membandingkan irisan dan gabungan kode/nama mata kuliah yang berhasil dinormalisasi.
- Grade agreement menghitung proporsi nilai yang sama pada mata kuliah yang sama.
- Candidate peer dibatasi ke akun mahasiswa aktif, program studi yang sama jika tersedia, dan histori yang memiliki mata kuliah lulus pada semester target. Paling banyak 20 peer dengan skor tertinggi digunakan untuk voting mata kuliah.

Ini adalah metrik kemiripan heuristik yang ringan dan dapat dijelaskan, **bukan probabilitas kelulusan, bukan prediksi nilai, dan bukan bukti bahwa model telah terlatih pada dataset yang representatif**.

## Fallback dan evaluasi

Jika bukti peer yang memadai belum tersedia, sistem mengandalkan content-based signals dan menandai faktor yang belum memiliki bukti. Precision@5 dan Recall@5 hanya boleh ditampilkan bila hasil evaluasi tersimpan tersedia. Nilai kosong berarti belum ada evaluasi memadai; jangan mengubahnya menjadi 0% atau mengklaim kualitas model tanpa pengujian.

## Batasan yang masih berlaku

- Jaccard + kesepakatan nilai belum mempertimbangkan urutan mata kuliah, kedekatan semester, tingkat kesulitan, atau konteks capaian pembelajaran secara mendalam.
- Data peer yang sedikit, tidak seimbang antar program/angkatan, atau nilai historis yang tidak lengkap dapat mengurangi kualitas rekomendasi.
- Perubahan kurikulum dan aturan prodi perlu dijaga agar katalog, prasyarat, minat, dan semester tersedia tetap mutakhir.
- Evaluasi kualitas harus dilakukan per program studi dan periode akademik dengan baseline yang jelas, pembagian data yang mencegah kebocoran, serta metrik Precision@K/Recall@K. Jangan mengukur keberhasilan hanya dari skor internal algoritma.

## Prinsip penggunaan

Gunakan rekomendasi sebagai bahan diskusi dengan Dosen PA. Periksa alasan, prasyarat, kelas, jadwal dan kuota secara terpisah sebelum mengajukan KRS. Keputusan final mengikuti aturan akademik dan persetujuan pejabat yang berwenang.
