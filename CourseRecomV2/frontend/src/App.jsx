import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  BookOpenCheck,
  BrainCircuit,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Clock3,
  FileClock,
  FileUp,
  HelpCircle,
  History,
  Home,
  Info,
  LogOut,
  Menu,
  MapPin,
  PieChart,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  UserRound,
  Users,
  UsersRound,
  X,
} from 'lucide-react';

const CONFIGURED_API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '');
const NORMALIZED_API_BASE = /(?:^|\/)api$/i.test(CONFIGURED_API_BASE)
  ? CONFIGURED_API_BASE
  : `${CONFIGURED_API_BASE}/api`;
const API_BASE = NORMALIZED_API_BASE;
const IS_PRODUCTION_ENVIRONMENT = String(import.meta.env.VITE_ENVIRONMENT || '').toLowerCase() === 'production';
const INITIAL_YEAR = new Date().getFullYear();
const DEFAULT_ACADEMIC_YEAR = `${INITIAL_YEAR}/${INITIAL_YEAR + 1}`;

function calculateIpkFromSemesterIps(semesters, currentSemester) {
  const count = Number(currentSemester);
  if (!Number.isInteger(count) || count < 1) return null;
  const indexed = new Map((semesters || []).map((item) => [Number(item.semester), item.ip_semester]));
  const values = [];
  for (let semester = 1; semester <= count; semester += 1) {
    const raw = indexed.get(semester);
    if (raw === '' || raw === null || raw === undefined) return null;
    const value = Number(raw);
    if (!Number.isFinite(value) || value < 0 || value > 4) return null;
    values.push(value);
  }
  return Number((values.reduce((total, value) => total + value, 0) / values.length).toFixed(2));
}

function normalizeKhsPreview(preview) {
  const courses = Array.isArray(preview.courses)
    ? preview.courses
    : (preview.semesters || []).flatMap((semester) => semester.courses || []);
  const parsedCurrent = Number(preview.metadata?.current_semester);
  const currentSemester = Number.isInteger(parsedCurrent) && parsedCurrent >= 1 && parsedCurrent <= 14
    ? parsedCurrent
    : Math.max(1, ...(preview.semesters || []).map((item) => Number(item.semester) || 0));
  const bySemester = new Map((preview.semesters || []).map((item) => [Number(item.semester), item]));
  const semesters = Array.from({ length: currentSemester }, (_, index) => {
    const semester = index + 1;
    const existing = bySemester.get(semester);
    return existing
      ? { ...existing, semester, courses: courses.filter((course) => Number(course.semester) === semester) }
      : { semester, ip_semester: '', courses: [] };
  });
  return { ...preview, courses, semesters };
}

const EMPTY_RECOMMENDATIONS = {
  status: 'khs_required',
  profile: null,
  recommendations: [],
  mandatory_courses: [],
  rejected: [],
  semester_antara: [],
};
const INTEREST_OPTIONS = [
  'Manajemen Teknologi Informasi',
  'Kecerdasan Bisnis',
  'Software Engineer',
  'Manajer Proyek TI',
  'Data Scientist',
  'Analisis dan Rekayasa Jaringan',
  'Perancangan UI/UX',
  'Manufaktur',
  'Energi dan Konversi Energi',
  'Material',
  'Sistem Mekanikal',
  'Teknik Telekomunikasi',
  'Pengembangan Robotika',
  'Pemeliharaan Industri',
  'Manajemen Proyek Mekatronika',
];
const PROGRAM_INTERESTS = {
  'Sistem dan Teknologi Informasi': {
    kind: 'Peminatan resmi program studi',
    options: ['Manajemen Teknologi Informasi', 'Kecerdasan Bisnis'],
    note: 'Mengikuti peminatan pada laman resmi STI UHAMKA. Label Manajemen Sistem Informasi adalah data lama di CourseRecom.',
  },
  'Teknik Informatika': {
    kind: 'Arah minat berdasarkan profil lulusan',
    options: ['Software Engineer', 'Manajer Proyek TI', 'Data Scientist', 'Analisis dan Rekayasa Jaringan', 'Perancangan UI/UX'],
    note: 'Dirangkum dari profil lulusan dan CPL Prodi Teknik Informatika, bukan peminatan formal.',
  },
  'Teknik Mesin': {
    kind: 'Arah minat berdasarkan bidang keilmuan',
    options: ['Manufaktur', 'Energi dan Konversi Energi', 'Material', 'Sistem Mekanikal'],
    note: 'Mengacu pada bidang manufaktur, energi, material, dan mekanikal yang dipublikasikan Prodi Teknik Mesin, bukan peminatan formal.',
  },
  'Teknik Elektro': {
    kind: 'Spesialisasi bidang program studi',
    options: ['Teknik Telekomunikasi'],
    note: 'Laman resmi Teknik Elektro menyebut spesialisasi bidang Teknik Telekomunikasi.',
  },
  'Teknologi Rekayasa Mekatronika': {
    kind: 'Arah minat berdasarkan profil lulusan',
    options: ['Pengembangan Robotika', 'Pemeliharaan Industri', 'Manajemen Proyek Mekatronika'],
    note: 'Mengikuti tiga profil lulusan resmi TRM, bukan peminatan formal.',
  },
};
const canonicalProgramName = (value) => {
  const normalized = String(value || '').trim().toLowerCase().replace(/\s+/g, ' ');
  const aliases = {
    sti: 'Sistem dan Teknologi Informasi',
    'sistem informasi': 'Sistem dan Teknologi Informasi',
    'sistem dan teknologi informasi': 'Sistem dan Teknologi Informasi',
    ti: 'Teknik Informatika',
    'teknik informatika': 'Teknik Informatika',
    'teknik mesin': 'Teknik Mesin',
    'teknik elektro': 'Teknik Elektro',
    trm: 'Teknologi Rekayasa Mekatronika',
    'teknologi rekayasa mekatronika': 'Teknologi Rekayasa Mekatronika',
  };
  return aliases[normalized] || value || '';
};
const RECOMMENDATION_FACTOR_LABELS = {
  similar_students: 'Similar Students',
  academic_history: 'Academic History',
  interest: 'Interest',
  curriculum: 'Curriculum',
  course_pattern: 'Course Pattern',
};
const RECOMMENDATION_FACTOR_HINTS = {
  similar_students: 'Kecocokan riwayat mata kuliah dan nilai dengan mahasiswa lain yang memiliki histori paling mirip.',
  academic_history: 'Menggunakan nilai mata kuliah prasyarat yang sudah lulus, atau IPK pada KHS terbaru jika tidak ada prasyarat terukur.',
  interest: 'Mencocokkan topik dari nama, kategori, deskripsi, dan prasyarat mata kuliah dengan peminatan yang dipilih.',
  curriculum: 'Memastikan mata kuliah memang ditawarkan pada semester target menurut katalog kurikulum.',
  course_pattern: 'Proporsi mahasiswa pembanding yang mengambil mata kuliah tersebut pada semester target.',
};
const LEGACY_INTERESTS = {
  'manajemen sistem informasi': 'Manajemen Teknologi Informasi',
  'manajemen teknologi informasi': 'Manajemen Teknologi Informasi',
  'mti': 'Manajemen Teknologi Informasi',
  'manajemen & sistem informasi': 'Manajemen Teknologi Informasi',
  'peminatan manajemen si': 'Manajemen Teknologi Informasi',
  msi: 'Manajemen Teknologi Informasi',
  'kecerdasan bisnis': 'Kecerdasan Bisnis',
  'peminatan kecerdasan bisnis': 'Kecerdasan Bisnis',
  kb: 'Kecerdasan Bisnis',
  data: 'Kecerdasan Bisnis',
  'data science': 'Kecerdasan Bisnis',
  'ai/ml': 'Kecerdasan Bisnis',
  ai: 'Kecerdasan Bisnis',
  'artificial intelligence': 'Kecerdasan Bisnis',
};

function canonicalizeInterests(interests) {
  const selected = new Set(
    interests.split(',').map((interest) => (
      LEGACY_INTERESTS[interest.trim().toLowerCase()]
    )).filter(Boolean),
  );
  return INTEREST_OPTIONS.find((interest) => selected.has(interest)) || interests.trim();
}

function isMandatoryCourse(course) {
  const category = String(course.category || '');
  const description = String(course.description || '');
  return course.mandatory === true
    || /\bwajib\b/i.test(category)
    || /\bwajib(?:\s+semester\s+\d+)?\b/i.test(description);
}

function toastTypeFor(message) {
  const normalized = message.toLowerCase();
  if (/melebihi|tidak dapat|perlu revisi|belum tersedia/.test(normalized)) return 'warning';
  if (/gagal|tidak valid|tidak sama|error|tidak dapat diproses/.test(normalized)) return 'error';
  if (/berhasil|disetujui|tersimpan|diperbarui|dihapus/.test(normalized)) return 'success';
  return 'info';
}

function expireSessionOnUnauthorized(response, token) {
  if (response.status !== 401 || !token) return;
  localStorage.removeItem('courseRecomToken');
  window.dispatchEvent(new Event('courserecom:session-expired'));
}

function ToastItem({ toast, onDismiss }) {
  const [isLeaving, setIsLeaving] = useState(false);
  const Icon = toast.type === 'success'
    ? CheckCircle2
    : toast.type === 'error'
      ? AlertCircle
      : toast.type === 'warning' ? AlertCircle : Info;

  useEffect(() => {
    const beginExit = window.setTimeout(() => setIsLeaving(true), 4700);
    const remove = window.setTimeout(() => onDismiss(toast.id), 5000);
    return () => {
      window.clearTimeout(beginExit);
      window.clearTimeout(remove);
    };
  }, [onDismiss, toast.id]);

  return (
    <div className={`toast toast-${toast.type}${isLeaving ? ' toast-leaving' : ''}`} role={toast.type === 'error' ? 'alert' : 'status'}>
      <Icon size={20} aria-hidden="true" />
      <span>{toast.message}</span>
      <button
        type="button"
        className="toast-close"
        aria-label="Tutup notifikasi"
        onClick={() => {
          setIsLeaving(true);
          window.setTimeout(() => onDismiss(toast.id), 180);
        }}
      >
        <X size={18} aria-hidden="true" />
      </button>
    </div>
  );
}

async function apiRequest(path, options = {}) {
  const token = localStorage.getItem('courseRecomToken');
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (token) {
    headers.set('Authorization', 'Bearer ' + token);
  }

  const { suppressLoader = false, ...requestOptions } = options;
  if (!suppressLoader) window.dispatchEvent(new Event('courserecom:request-start'));
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...requestOptions,
      headers,
    });
    expireSessionOnUnauthorized(response, token);

    const contentType = response.headers.get('content-type') || '';
    const responseText = response.status === 204 ? '' : await response.text();
    const data = responseText
      ? contentType.includes('application/json')
        ? JSON.parse(responseText)
        : responseText
      : null;

    if (!response.ok) {
      const detail = data && typeof data === 'object' ? data.detail : null;
      const message = Array.isArray(detail)
        ? detail.map((issue) => {
          if (typeof issue === 'string') return issue;
          if (!issue || typeof issue !== 'object') return '';
          const field = Array.isArray(issue.loc) ? issue.loc.at(-1) : '';
          return [field, issue.msg].filter(Boolean).join(': ') || JSON.stringify(issue);
        }).filter(Boolean).join(' ')
        : detail && typeof detail === 'object'
          ? detail.msg || JSON.stringify(detail)
          : detail || (typeof data === 'object' && data !== null ? data.message : data) || 'Permintaan gagal';
      throw new Error(message);
    }

    return data;
  } finally {
    if (!suppressLoader) window.dispatchEvent(new Event('courserecom:request-end'));
  }
}

function AnimatedDonut({ title, value, percentage, subtitle, accent = 'teal' }) {
  const [animate, setAnimate] = useState(false);
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setAnimate(true));
    return () => window.cancelAnimationFrame(frame);
  }, [value, percentage]);
  const safePercentage = Math.max(0, Math.min(100, Number(percentage) || 0));
  return (
    <article className="admin-donut-card">
      <div className={`admin-donut admin-donut-${accent}`} style={{ '--donut-value': `${animate ? safePercentage : 0}%` }}>
        <div className="admin-donut-center">
          <strong>{value}</strong>
          <span>{title}</span>
        </div>
      </div>
      <div className="admin-donut-caption"><strong>{title}</strong><span>{subtitle}</span></div>
    </article>
  );
}

function SemesterCourseChart({ items = [] }) {
  const [animate, setAnimate] = useState(false);
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setAnimate(true));
    return () => window.cancelAnimationFrame(frame);
  }, [items]);
  const maxCount = Math.max(1, ...items.map((item) => Number(item.count) || 0));
  return (
    <section className="admin-chart-card">
      <div className="admin-chart-heading">
        <div><h3>Distribusi Mata Kuliah per Semester</h3><p className="muted">Jumlah mata kuliah aktif yang tersedia pada setiap semester</p></div>
      </div>
      {items.length ? (
        <div className="semester-chart" role="img" aria-label="Grafik jumlah mata kuliah semester satu sampai delapan">
          {items.map((item) => {
            const count = Number(item.count) || 0;
            const height = count ? Math.max(4, (count / maxCount) * 100) : 0;
            return (
              <div className="semester-chart-column" key={item.semester}>
                <strong>{count}</strong>
                <div className="semester-chart-track"><span style={{ height: `${animate ? height : 0}%` }} /></div>
                <span>Semester {item.semester}</span>
              </div>
            );
          })}
        </div>
      ) : <p className="muted">Data mata kuliah belum tersedia.</p>}
    </section>
  );
}


const GUIDE_SECTIONS = [
  {
    role: 'Semua Akun',
    title: 'Masuk, navigasi, dan keamanan akun',
    intro: 'Mulai dari halaman login, gunakan peran yang sesuai dengan akun, lalu kenali menu yang tersedia sesuai kewenangan.',
    steps: [
      'Pilih Mahasiswa, Dosen PA, atau Admin Prodi pada halaman masuk. Gunakan username/NIM dan password akun yang diberikan atau didaftarkan.',
      'Mahasiswa dapat membuat akun dari halaman Daftar dengan mengisi NIM, nama, program studi, bidang minat, angkatan, dan password. Tahun angkatan dibatasi oleh tahun ajaran aktif.',
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


function parallelScheduleConflict(courseEntries) {
  const schedules = [];
  for (const course of courseEntries) {
    if (!course.day || !course.start_time || !course.end_time) continue;
    const start = Number(course.start_time.slice(0, 2)) * 60 + Number(course.start_time.slice(3, 5));
    const end = Number(course.end_time.slice(0, 2)) * 60 + Number(course.end_time.slice(3, 5));
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) continue;
    for (const previous of schedules) {
      if (previous.day.trim().toLocaleLowerCase('id-ID') === course.day.trim().toLocaleLowerCase('id-ID')
        && start < previous.end && previous.start < end) {
        return { current: course.code, previous: previous.code };
      }
    }
    schedules.push({ code: course.code, day: course.day, start, end });
  }
  return null;
}

function GuideStep({ index, children }) {
  return (
    <li className="guide-step">
      <span className="guide-step-number">{String(index + 1).padStart(2, '0')}</span>
      <span>{children}</span>
    </li>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState('dashboard');
  const [authMode, setAuthMode] = useState('login');
  const [selectedRole, setSelectedRole] = useState('mahasiswa');
  const [form, setForm] = useState({ username: '', password: '' });
  const [registrationForm, setRegistrationForm] = useState({ nim: '', username: '', full_name: '', program_study: 'Sistem dan Teknologi Informasi', interests: 'Manajemen Teknologi Informasi', angkatan: '', password: '', passwordConfirmation: '' });
  const [profile, setProfile] = useState(null);
  const [programInterestCatalog, setProgramInterestCatalog] = useState(PROGRAM_INTERESTS);
  const [recommendationResult, setRecommendationResult] = useState(EMPTY_RECOMMENDATIONS);
  const recommendations = useMemo(
    () => recommendationResult.recommendations || [],
    [recommendationResult.recommendations],
  );
  const mandatoryRecommendations = useMemo(
    () => recommendationResult.mandatory_courses || recommendations.filter(isMandatoryCourse),
    [recommendationResult.mandatory_courses, recommendations],
  );
  const optionalRecommendations = useMemo(
    () => recommendations.filter((item) => !isMandatoryCourse(item)),
    [recommendations],
  );
  const rejectedRecommendations = recommendationResult.rejected || [];
  const [academicHistory, setAcademicHistory] = useState([]);
  const [curriculumCourses, setCurriculumCourses] = useState([]);
  const [curriculumLoaded, setCurriculumLoaded] = useState(false);
  const [curriculumError, setCurriculumError] = useState('');
  const [mentees, setMentees] = useState([]);
  const [adminAdvisors, setAdminAdvisors] = useState([]);
  const [lecturerDirectory, setLecturerDirectory] = useState([]);
  const [lecturerDirectoryDraft, setLecturerDirectoryDraft] = useState({});
  const [roomList, setRoomList] = useState([]);
  const [roomForm, setRoomForm] = useState({ code: '', capacity: '', room_type: 'Ruang kuliah', is_active: false, notes: '' });
  const [editingRoomCode, setEditingRoomCode] = useState('');
  const [roomBusy, setRoomBusy] = useState(false);
  const [scheduleSlots, setScheduleSlots] = useState([]);
  const [scheduleDuration, setScheduleDuration] = useState(0);
  const [scheduleSlotBusy, setScheduleSlotBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState('');
  const [adminAnalytics, setAdminAnalytics] = useState(null);
  const [lecturerForm, setLecturerForm] = useState({
    nip: '', full_name: '', username: '', email: '', password: '', passwordConfirmation: '',
  });
  const [lecturerFormVisible, setLecturerFormVisible] = useState(false);
  const [lecturerBusy, setLecturerBusy] = useState(false);
  const [editingLecturerNip, setEditingLecturerNip] = useState('');
  const [lecturerEditDraft, setLecturerEditDraft] = useState({});
  const [advisorDraft, setAdvisorDraft] = useState({});
  const [advisorBusyNim, setAdvisorBusyNim] = useState('');
  const [, setAdminSettings] = useState([]);
  const [adminAuditLogs, setAdminAuditLogs] = useState([]);
  const [advisorHistory, setAdvisorHistory] = useState([]);
  const [approvedPlans, setApprovedPlans] = useState([]);
  const [overrideReason, setOverrideReason] = useState({});
  const [overrideCourses, setOverrideCourses] = useState({});
  const [overrideClassSelections, setOverrideClassSelections] = useState({});
  const [settingDraft, setSettingDraft] = useState({
    active_academic_year: DEFAULT_ACADEMIC_YEAR,
    krs_period_start: '',
    krs_period_end: '',
    krs_fill_deadline: '',
    kprs_period_start: '',
    kprs_period_end: '',
    max_sks_by_ips: '{"3.35":24,"3.00":22,"default":20}',
  });
  const [accountBusyNim, setAccountBusyNim] = useState('');
  const [studyPlans, setStudyPlans] = useState([]);
  const [kprsRequests, setKprsRequests] = useState([]);
  const [menteeKprsRequests, setMenteeKprsRequests] = useState([]);
  const [kprsReviewNotes, setKprsReviewNotes] = useState({});
  const [kprsDraft, setKprsDraft] = useState({ planId: '', courses: '', reason: '' });
  const hasPendingStudentPlan = studyPlans.some((plan) => plan.status === 'pending');
  const [studyPlanBusy, setStudyPlanBusy] = useState(false);
  const studyPlanSubmissionRef = useRef(false);
  const [reviewNotes, setReviewNotes] = useState({});
  const [reviewRejectedCourses, setReviewRejectedCourses] = useState({});
  const [courseList, setCourseList] = useState([]);
  const [classList, setClassList] = useState([]);
  const [studentClasses, setStudentClasses] = useState([]);
  const [studentClassesLoaded, setStudentClassesLoaded] = useState(false);
  const [classBusy, setClassBusy] = useState(false);
  const [editingClassId, setEditingClassId] = useState(null);
  const [classForm, setClassForm] = useState({
    course_code: '', class_name: '', lecturer_id: '', room: '', day: 'Senin',
    start_time: '', end_time: '', capacity: 40, semester: '1', is_open: true,
  });
  const [guideSearch, setGuideSearch] = useState('');
  const [kprsClassSelections, setKprsClassSelections] = useState({});
  const [editingCourseCode, setEditingCourseCode] = useState('');
  const [courseBusyCode, setCourseBusyCode] = useState('');
  const [newCourse, setNewCourse] = useState({
    code: '',
    name: '',
    sks: 3,
    semester: 1,
    available_semesters: '1',
    category: '',
    description: '',
    prerequisite_text: '',
    prerequisite_codes: '',
    day: '',
    time: '',
    capacity: 40,
  });
  const [loading, setLoading] = useState(false);
  const [pendingRequests, setPendingRequests] = useState(0);
  const [academicYear, setAcademicYear] = useState({
    academic_year: DEFAULT_ACADEMIC_YEAR,
    max_angkatan: INITIAL_YEAR,
  });
  const [loginError, setLoginError] = useState('');
  const [authMessage, setAuthMessage] = useState('');
  const [profileDraft, setProfileDraft] = useState('Kecerdasan Bisnis');
  const [accountProfileDraft, setAccountProfileDraft] = useState({
    full_name: '', email: '', username: '', phone_number: '', program_study: '', angkatan: '',
  });
  const [passwordDraft, setPasswordDraft] = useState({ current_password: '', new_password: '', confirmation: '' });
  const [importStatus, setImportStatus] = useState('');
  const [khsPreview, setKhsPreview] = useState(null);
  const [historyEditId, setHistoryEditId] = useState(null);
  const [historyEditDraft, setHistoryEditDraft] = useState(null);
  const [historyEditBusy, setHistoryEditBusy] = useState(false);
  const [khsFiles, setKhsFiles] = useState([]);
  const [khsBusy, setKhsBusy] = useState(false);
  const [khsError, setKhsError] = useState('');
  const [modelStatus, setModelStatus] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [officialKrsPreviewUrl, setOfficialKrsPreviewUrl] = useState('');
  const [officialKrsPreviewPlanId, setOfficialKrsPreviewPlanId] = useState(null);
  const [officialKrsPreviewBusy, setOfficialKrsPreviewBusy] = useState(false);
  const previewOfficialKrs = useCallback(async (planId) => {
    const token = localStorage.getItem('courseRecomToken');
    setOfficialKrsPreviewBusy(true);
    window.dispatchEvent(new Event('courserecom:request-start'));
    try {
      const response = await fetch(`${API_BASE}/mahasiswa/rencana-studi/${planId}/pdf-resmi`, {
        headers: token ? { Authorization: 'Bearer ' + token } : {},
      });
      expireSessionOnUnauthorized(response, token);
      if (!response.ok) throw new Error('PDF resmi belum tersedia atau KRS belum disetujui.');
      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/pdf')) {
        throw new Error('Respons server bukan dokumen PDF.');
      }
      const blob = await response.blob();
      const previewUrl = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }));
      setOfficialKrsPreviewPlanId(planId);
      setOfficialKrsPreviewUrl(previewUrl);
    } finally {
      setOfficialKrsPreviewBusy(false);
      window.dispatchEvent(new Event('courserecom:request-end'));
    }
  }, []);
  const [toasts, setToasts] = useState([]);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  useEffect(() => {
    if (user?.role !== 'admin' || view !== 'kelas') return undefined;
    if (!classForm.course_code || !classForm.room || !classForm.day) {
      setScheduleSlots([]);
      setScheduleDuration(0);
      return undefined;
    }
    let active = true;
    setScheduleSlotBusy(true);
    const parameters = new URLSearchParams({
      course_code: classForm.course_code,
      room_code: classForm.room,
      day: classForm.day,
    });
    if (classForm.lecturer_id) parameters.set('lecturer_id', String(classForm.lecturer_id));
    if (editingClassId) parameters.set('exclude_class_id', String(editingClassId));
    apiRequest(`/admin/schedule-options?${parameters.toString()}`, { suppressLoader: true })
      .then((result) => {
        if (!active) return;
        const slots = Array.isArray(result.slots) ? result.slots : [];
        setScheduleSlots(slots);
        setScheduleDuration(Number(result.duration_minutes) || 0);
        setClassForm((previous) => {
          const selected = slots.find((slot) => slot.start_time === previous.start_time);
          return selected ? { ...previous, end_time: selected.end_time } : { ...previous, start_time: '', end_time: '' };
        });
      })
      .catch((error) => {
        if (!active) return;
        setScheduleSlots([]);
        setScheduleDuration(0);
        pushToast(error.message || 'Slot jadwal tidak dapat dimuat.', 'error');
      })
      .finally(() => { if (active) setScheduleSlotBusy(false); });
    return () => { active = false; };
  }, [user?.role, view, classForm.course_code, classForm.room, classForm.day, classForm.lecturer_id, editingClassId, pushToast]);

  useEffect(() => {
    if (!officialKrsPreviewUrl) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') {
        setOfficialKrsPreviewUrl('');
        setOfficialKrsPreviewPlanId(null);
      }
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => {
      window.removeEventListener('keydown', closeOnEscape);
      URL.revokeObjectURL(officialKrsPreviewUrl);
    };
  }, [officialKrsPreviewUrl]);

  const closeOfficialKrsPreview = () => {
    setOfficialKrsPreviewUrl('');
    setOfficialKrsPreviewPlanId(null);
  };
  useEffect(() => {
    let active = true;
    apiRequest('/auth/program-interests', { suppressLoader: true })
      .then((catalog) => {
        if (!active || !catalog || typeof catalog !== 'object') return;
        setProgramInterestCatalog(catalog);
        setRegistrationForm((previous) => {
          if (
            previous.program_study === 'Sistem dan Teknologi Informasi'
            && previous.interests === 'Manajemen Sistem Informasi'
            && catalog['Sistem dan Teknologi Informasi']?.options?.includes('Manajemen Teknologi Informasi')
          ) {
            return { ...previous, interests: 'Manajemen Teknologi Informasi' };
          }
          return previous;
        });
      })
      .catch(() => {});
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const handleExpiredSession = () => {
      setUser(null);
      setLoginError('Sesi telah berakhir. Silakan masuk kembali.');
      setLoading(false);
    };
    window.addEventListener('courserecom:session-expired', handleExpiredSession);
    return () => window.removeEventListener('courserecom:session-expired', handleExpiredSession);
  }, []);

  useEffect(() => {
    const onRequestStart = () => setPendingRequests((count) => count + 1);
    const onRequestEnd = () => setPendingRequests((count) => Math.max(0, count - 1));
    window.addEventListener('courserecom:request-start', onRequestStart);
    window.addEventListener('courserecom:request-end', onRequestEnd);
    return () => {
      window.removeEventListener('courserecom:request-start', onRequestStart);
      window.removeEventListener('courserecom:request-end', onRequestEnd);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiRequest('/auth/academic-year')
      .then((result) => {
        if (!cancelled) setAcademicYear(result);
      })
      .catch((error) => console.error('Academic year configuration could not be loaded:', error));
    return () => { cancelled = true; };
  }, []);

  const pushToast = useCallback((message, type = toastTypeFor(message)) => {
    setToasts((previous) => [...previous.slice(-4), { id: `${Date.now()}-${Math.random()}`, message, type }]);
  }, []);
  const deferToast = useCallback((message, type) => {
    const timeout = window.setTimeout(() => pushToast(message, type), 0);
    return () => window.clearTimeout(timeout);
  }, [pushToast]);
  const dismissToast = useCallback((id) => {
    setToasts((previous) => previous.filter((toast) => toast.id !== id));
  }, []);
  const [storedDraftCourses, setDraftCourses] = useState(() => {
    try {
      const savedDraft = localStorage.getItem('courseRecomDraft');
      return savedDraft ? JSON.parse(savedDraft) : [];
    } catch {
      return [];
    }
  });
  const draftCourses = useMemo(() => {
    const hasApprovedPlan = studyPlans.some((plan) => (
      plan.status === 'approved'
      && plan.semester === recommendationResult.target_semester
    ));
    if (recommendationResult.status !== 'ready' || hasApprovedPlan) return storedDraftCourses;
    const requiredCourses = mandatoryRecommendations;
    const existingCodes = new Set(storedDraftCourses.map((course) => course.code));
    const missingCourses = requiredCourses.filter((course) => !existingCodes.has(course.code));
    return missingCourses.length ? [...storedDraftCourses, ...missingCourses] : storedDraftCourses;
  }, [
    recommendationResult.status,
    recommendationResult.target_semester,
    mandatoryRecommendations,
    storedDraftCourses,
    studyPlans,
  ]);

  useEffect(() => {
    if (actionMessage) return deferToast(actionMessage);
    return undefined;
  }, [actionMessage, deferToast]);

  useEffect(() => {
    if (loginError) return deferToast(loginError, 'error');
    return undefined;
  }, [deferToast, loginError]);

  useEffect(() => {
    if (authMessage) return deferToast(authMessage, 'success');
    return undefined;
  }, [authMessage, deferToast]);

  useEffect(() => {
    if (khsError) return deferToast(khsError, 'error');
    return undefined;
  }, [deferToast, khsError]);

  useEffect(() => {
    if (importStatus) return deferToast(importStatus);
    return undefined;
  }, [deferToast, importStatus]);

  useEffect(() => {
    if (modelStatus) return deferToast(modelStatus);
    return undefined;
  }, [deferToast, modelStatus]);

  useEffect(() => {
    if (
      view === 'dashboard'
      && user?.role === 'mahasiswa'
      && profile
      && !profile.khs_confirmed
    ) {
      return deferToast('Unggah dan konfirmasi KHS lengkap dalam format PDF atau gambar untuk mendapatkan rekomendasi.', 'info');
    }
    return undefined;
  }, [deferToast, profile, user, view]);

  useEffect(() => {
    if (view === 'rekomendasi' && profile && recommendationResult.status !== 'ready') {
      return deferToast(
        recommendationResult.message || 'Unggah dan konfirmasi KHS sebelum meminta rekomendasi.',
        'info',
      );
    }
    return undefined;
  }, [deferToast, profile, recommendationResult.message, recommendationResult.status, view]);

  const khsWarnings = khsPreview?.warnings?.join('|') || '';
  useEffect(() => {
    if (!khsWarnings) return undefined;
    const timeouts = khsWarnings.split('|').map((warning, index) => (
      window.setTimeout(() => pushToast(warning, 'warning'), index * 100)
    ));
    return () => timeouts.forEach((timeout) => window.clearTimeout(timeout));
  }, [khsWarnings, pushToast]);

  useEffect(() => {
    if (!mobileMenuOpen) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setMobileMenuOpen(false);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [mobileMenuOpen]);

  useEffect(() => {
    if (user?.role !== 'mahasiswa') return undefined;
    const refreshStudyPlans = async () => {
      try {
        const plans = await apiRequest('/mahasiswa/rencana-studi', { suppressLoader: true });
        setStudyPlans(plans);
        if (plans.some((plan) => (
          plan.status === 'approved'
          && plan.semester === recommendationResult.target_semester
        ))) {
          setDraftCourses([]);
        }
      } catch (error) {
        console.error('Study plan status refresh failed', error);
        pushToast(error.message || 'Status KRS gagal diperbarui.', 'error');
      }
    };
    window.addEventListener('focus', refreshStudyPlans);
    const interval = hasPendingStudentPlan
      ? window.setInterval(refreshStudyPlans, 15000)
      : null;
    return () => {
      window.removeEventListener('focus', refreshStudyPlans);
      if (interval !== null) window.clearInterval(interval);
    };
  }, [hasPendingStudentPlan, pushToast, recommendationResult.target_semester, user]);

  useEffect(() => {
    const token = localStorage.getItem('courseRecomToken');
    if (!token) return;

    const restoreSession = async () => {
      try {
        const me = await apiRequest('/auth/me');
        if (me.role === 'mahasiswa') {
          try {
            const savedDraft = localStorage.getItem(`courseRecomDraft:${me.nim}`);
            const parsed = savedDraft ? JSON.parse(savedDraft) : null;
            setDraftCourses(
              parsed && parsed.semester === (me.semester ?? null) && Array.isArray(parsed.courses)
                ? parsed.courses                : [],
            );
          } catch {
            setDraftCourses([]);
          }
        } else {
          setDraftCourses([]);
        }
        setUser(me);
      } catch (error) {
        const sessionExpired = !localStorage.getItem('courseRecomToken');
        localStorage.removeItem('courseRecomToken');
        setLoginError(sessionExpired
          ? 'Sesi telah berakhir. Silakan masuk kembali.'
          : error.message || 'Sesi sebelumnya tidak dapat dipulihkan. Silakan masuk kembali.');
      }
    };

    restoreSession();
  }, []);

  useEffect(() => {
    if (!user) return;

    let cancelled = false;
    if (user.role === 'mahasiswa') {
      apiRequest('/mahasiswa/kurikulum')
        .then((curriculum) => {
          if (!cancelled) setCurriculumCourses(curriculum);
        })
        .catch((error) => {
          console.error('Curriculum data fetch failed', error);
          if (!cancelled) setCurriculumError(error.message || 'Data kurikulum gagal dimuat.');
        })
        .finally(() => {
          if (!cancelled) setCurriculumLoaded(true);
        });
    }

    const loadDashboardData = async () => {
      try {
        if (user.role === 'mahasiswa') {
          const [profileData, recommendationData, khsDocuments, plans, kprs] = await Promise.all([
            apiRequest('/mahasiswa/profil'),
            apiRequest('/mahasiswa/rekomendasi'),
            apiRequest('/mahasiswa/khs'),
            apiRequest('/mahasiswa/rencana-studi'),
            apiRequest('/mahasiswa/kprs'),
          ]);

          if (cancelled) return;
          setProfile(profileData);
          setRecommendationResult(recommendationData);
          setAcademicHistory(khsDocuments);
          setStudyPlans(plans);
          setKprsRequests(kprs);
          if (plans.some((plan) => (
            plan.status === 'approved'
            && plan.semester === recommendationData.target_semester
          ))) {
            setDraftCourses([]);
          }
          const pendingPreview = khsDocuments.find((item) => item.status === 'pending') || null;
          if (pendingPreview) {
            pendingPreview.courses = pendingPreview.courses
              || pendingPreview.semesters.flatMap((semester) => semester.courses);
          }
          setKhsPreview(pendingPreview);
        }

        if (user.role === 'dosen') {
          const [list, plans, kprs] = await Promise.all([
            apiRequest('/dosen/mahasiswa'),
            apiRequest('/dosen/rencana-studi'),
            apiRequest('/dosen/kprs'),
          ]);
          if (cancelled) return;
          setMentees(list);
          setStudyPlans(plans);
          setMenteeKprsRequests(kprs);
        }

        if (user.role === 'admin') {
          const [dashboard, lecturers, directory] = await Promise.all([
            apiRequest('/admin/dashboard'),
            apiRequest('/admin/lecturers'),
            apiRequest('/admin/lecturer-directory'),
          ]);
          if (cancelled) return;
          setMentees(dashboard.students);
          setAdminAdvisors(lecturers);
          setLecturerDirectory(directory);
          setAdminAnalytics(dashboard.analytics || null);
        }

        if (user.role === 'admin') {
          const [list, sections, rooms] = await Promise.all([
            apiRequest('/admin/courses'),
            apiRequest('/admin/classes'),
            apiRequest('/admin/rooms'),
          ]);
          if (cancelled) return;
          setCourseList(list.map((course) => ({ ...course, _originalCode: course.code })));
          setClassList(sections);
          setRoomList(rooms);
        }

        if (user.role === 'admin') {
          const [settings, auditLogs, advisorHistoryResult, approved] = await Promise.all([
            apiRequest('/admin/settings'),
            apiRequest('/admin/audit-logs'),
            apiRequest('/admin/advisor-history'),
            apiRequest('/admin/study-plans/approved'),
          ]);
          if (cancelled) return;
          setAdminSettings(settings);
          setAdminAuditLogs(auditLogs);
          setAdvisorHistory(advisorHistoryResult);
          setApprovedPlans(approved);
          const values = Object.fromEntries(settings.map((item) => [item.key, item.value]));
          setSettingDraft((previous) => ({ ...previous, ...values }));
        }
      } catch (error) {
        console.error('Dashboard data fetch failed', error);
        if (!cancelled) setActionMessage(error.message || 'Data dashboard gagal dimuat.');
      }
    };

    loadDashboardData();
    return () => { cancelled = true; };
  }, [user]);

  useEffect(() => {
    if (user?.role !== 'mahasiswa' || !recommendationResult.target_semester) {
      setStudentClasses([]);
      setStudentClassesLoaded(false);
      return undefined;
    }
    let active = true;
    setStudentClassesLoaded(false);
    apiRequest(`/mahasiswa/kelas?semester=${recommendationResult.target_semester}`, { suppressLoader: true })
      .then((sections) => { if (active) setStudentClasses(Array.isArray(sections) ? sections : []); })
      .catch((error) => { if (active) pushToast(error.message || 'Pilihan kelas paralel gagal dimuat.', 'error'); })
      .finally(() => { if (active) setStudentClassesLoaded(true); });
    return () => { active = false; };
  }, [user?.role, recommendationResult.target_semester, pushToast]);

  useEffect(() => {
    if (user?.role !== 'admin' || view !== 'dashboard') return undefined;
    let active = true;
    const refreshAdminAnalytics = async () => {
      try {
        const dashboard = await apiRequest('/admin/dashboard', { suppressLoader: true });
        if (!active) return;
        setMentees(dashboard.students || []);
        setAdminAnalytics(dashboard.analytics || null);
      } catch (error) {
        console.error('Admin analytics refresh failed:', error);
      }
    };
    const interval = window.setInterval(refreshAdminAnalytics, 30000);
    window.addEventListener('focus', refreshAdminAnalytics);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener('focus', refreshAdminAnalytics);
    };
  }, [user, view]);

  const login = async (event) => {
    event.preventDefault();
    setLoading(true);
    setLoginError('');
    let sessionStarted = false;

    try {
      const tokenResponse = await apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          username: form.username,
          password: form.password,
          role: selectedRole,
        }),
      });

      localStorage.setItem('courseRecomToken', tokenResponse.access_token);
      sessionStarted = true;
      const me = await apiRequest('/auth/me');
      setUser(me);
      setProfile(null);
      setRecommendationResult(EMPTY_RECOMMENDATIONS);
      setAcademicHistory([]);
      setCurriculumCourses([]);
      setCurriculumLoaded(false);
      setCurriculumError('');
      setKhsPreview(null);
      setView('dashboard');
    } catch (error) {
      const sessionExpired = sessionStarted && !localStorage.getItem('courseRecomToken');
      localStorage.removeItem('courseRecomToken');
      setLoginError(sessionExpired
        ? 'Sesi telah berakhir. Silakan masuk kembali.'
        : error.message || 'NIM atau password tidak valid.');
    } finally {
      setLoading(false);
    }
  };

  const loadAccountProfile = async () => {
    const account = await apiRequest('/auth/profile');
    setAccountProfileDraft({
      full_name: account.full_name || '',
      email: account.email || '',
      username: account.username || account.nim || '',
      phone_number: account.phone_number || '',
      program_study: account.program_study || '',
      angkatan: account.angkatan || '',
    });
    setPasswordDraft({ current_password: '', new_password: '', confirmation: '' });
  };

  const saveAccountProfile = async () => {
    if (passwordDraft.new_password && passwordDraft.new_password !== passwordDraft.confirmation) {
      pushToast('Konfirmasi password baru tidak sama.', 'error');
      return;
    }
    if (!accountProfileDraft.full_name.trim() || !accountProfileDraft.username.trim()) {
      pushToast('Nama dan username wajib diisi.', 'error');
      return;
    }
    try {
      const updated = await apiRequest('/auth/profile', {
        method: 'PUT',
        body: JSON.stringify({
          ...accountProfileDraft,
          current_password: passwordDraft.new_password ? passwordDraft.current_password : null,
          new_password: passwordDraft.new_password || null,
        }),
      });
      if (updated.access_token) {
        localStorage.setItem('courseRecomToken', updated.access_token);
      }
      const updatedUser = { ...updated };
      delete updatedUser.access_token;
      setUser(updatedUser);
      setProfile((previousProfile) => (
        previousProfile ? { ...previousProfile, full_name: updatedUser.full_name } : previousProfile
      ));
      setAccountProfileDraft({
        full_name: updatedUser.full_name || '',
        email: updatedUser.email || '',
        username: updatedUser.username || updatedUser.nim || '',
        phone_number: updatedUser.phone_number || '',
        program_study: updatedUser.program_study || '',
        angkatan: updatedUser.angkatan || '',
      });
      setPasswordDraft({ current_password: '', new_password: '', confirmation: '' });
      pushToast('Profil berhasil diperbarui.', 'success');
    } catch (error) {
      pushToast(error.message || 'Profil gagal diperbarui.', 'error');
    }
  };

  const registerStudent = async (event) => {
    event.preventDefault();
    setLoading(true);
    setLoginError('');
    setAuthMessage('');
    if (registrationForm.password !== registrationForm.passwordConfirmation) {
      setLoginError('Konfirmasi password tidak sama.');
      setLoading(false);
      return;
    }

    try {
      await apiRequest('/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          nim: registrationForm.nim,
          username: registrationForm.username || registrationForm.nim,
          full_name: registrationForm.full_name,
          program_study: registrationForm.program_study,
          interests: registrationForm.interests,
          angkatan: registrationForm.angkatan,
          password: registrationForm.password,
        }),
      });
      setForm({ username: registrationForm.nim.trim(), password: '' });
      setRegistrationForm({
        nim: '',
        username: '',
        full_name: '',
        program_study: 'Sistem dan Teknologi Informasi',
        interests: 'Manajemen Teknologi Informasi',
        angkatan: '',
        password: '',
        passwordConfirmation: '',
      });
      setAuthMode('login');
      setAuthMessage('Pendaftaran mahasiswa berhasil. Silakan masuk dengan NIM dan password Anda.');
    } catch (error) {
      setLoginError(error.message || 'Pendaftaran mahasiswa gagal.');
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      await apiRequest('/auth/logout', { method: 'POST' });
    } catch {
      // Clear the local session even if the server is unavailable.
    }
    localStorage.removeItem('courseRecomToken');
    if (user?.nim && user.role === 'mahasiswa') {
      localStorage.removeItem(`courseRecomDraft:${user.nim}`);
    }
    localStorage.removeItem('courseRecomDraft');
    setDraftCourses([]);
    setUser(null);
    setProfile(null);
    setRecommendationResult(EMPTY_RECOMMENDATIONS);
    setAcademicHistory([]);
    setCurriculumCourses([]);
    setCurriculumLoaded(false);
    setCurriculumError('');
    setMentees([]);
    setAdminAdvisors([]);
    setAdminAnalytics(null);
    setLecturerDirectory([]);
    setRoomList([]);
    setScheduleSlots([]);
    setScheduleDuration(0);
    setStudyPlans([]);
    setCourseList([]);
    setClassList([]);
    setStudentClasses([]);
    setStudentClassesLoaded(false);
    setKhsPreview(null);
    setView('dashboard');
  };

  const openInterests = () => {
    setProfileDraft(canonicalizeInterests(profile?.interests ?? user?.interests ?? ''));
    setView('minat');
  };

  useEffect(() => {
    if (!user?.nim || user.role !== 'mahasiswa') return;
    localStorage.setItem(`courseRecomDraft:${user.nim}`, JSON.stringify({
      semester: user.semester ?? null,
      courses: draftCourses,
    }));
  }, [draftCourses, user]);

  const saveProfile = async () => {
    if (user?.role !== 'mahasiswa') return;

    try {
      const updatedProfile = await apiRequest('/mahasiswa/profil', {
        method: 'PUT',
        body: JSON.stringify({ interests: canonicalizeInterests(profileDraft) }),
      });

      setProfile((previousProfile) => ({
        ...(previousProfile || {}),
        ...updatedProfile,
        interests: updatedProfile.interests || profileDraft,
      }));
      setUser((previousUser) => ({
        ...(previousUser || {}),
        interests: updatedProfile.interests || profileDraft,
      }));
      setActionMessage('Minat berhasil disimpan.');
    } catch (error) {
      console.error('Profile update failed', error);
      setActionMessage(error.message || 'Minat gagal disimpan.');
    }
  };

  const saveAdminSetting = async (key) => {
    try {
      await apiRequest('/admin/settings', {
        method: 'PUT',
        body: JSON.stringify({ key, value: settingDraft[key] || '' }),
      });
      setAdminSettings((previous) => [
        ...previous.filter((item) => item.key !== key),
        { key, value: settingDraft[key] || '' },
      ]);
      setActionMessage(`Pengaturan ${key} berhasil disimpan.`);
    } catch (error) {
      setActionMessage(error.message || 'Pengaturan gagal disimpan.');
    }
  };

  const overrideStudyPlan = async (planId, status, reason, courseCodesText = '') => {
    if (!reason || reason.trim().length < 10) {
      setActionMessage('Alasan override minimal 10 karakter.');
      return;
    }
    const originalPlan = approvedPlans.find((item) => item.id === planId);
    const courseCodes = courseCodesText.trim()
      ? courseCodesText.split(',').map((code) => code.trim().toUpperCase()).filter(Boolean)
      : (originalPlan?.courses || []).map((item) => typeof item === 'string' ? item : item.code);
    const selections = Object.fromEntries((originalPlan?.courses || []).filter((item) => typeof item === 'object' && item.class_id).map((item) => [item.code, Number(item.class_id)]));
    Object.entries(overrideClassSelections[planId] || {}).forEach(([code, classId]) => {
      if (classId) selections[code] = Number(classId);
    });
    try {      await apiRequest(`/admin/study-plans/${planId}/override`, {
        method: 'PATCH',
        body: JSON.stringify({
          status,
          reason: reason.trim(),
          course_codes: courseCodesText.trim() ? courseCodes : null,
          class_selections: Object.fromEntries(courseCodes.filter((code) => selections[code]).map((code) => [code, selections[code]])),
        }),
      });
      setApprovedPlans((previous) => status === 'approved' ? previous : previous.filter((plan) => plan.id !== planId));
      setAdminAuditLogs(await apiRequest('/admin/audit-logs'));
      setActionMessage('Override KRS berhasil dicatat.');
    } catch (error) {
      setActionMessage(error.message || 'Override KRS gagal.');
    }
  };

  const assignStudentAdvisor = async (studentNim) => {
    const advisorNim = advisorDraft[studentNim];
    if (!advisorNim || advisorBusyNim) return;
    const currentStudent = mentees.find((student) => student.nim === studentNim);
    if (advisorNim === (currentStudent?.advisor_nim || '')) return;
    const reason = window.prompt('Alasan penetapan atau penggantian Dosen PA (opsional):') || '';
    setAdvisorBusyNim(studentNim);
    try {
      await apiRequest(`/admin/students/${encodeURIComponent(studentNim)}/advisor`, {
        method: 'PATCH',
        body: JSON.stringify({ advisor_nim: advisorNim, reason }),
      });
      const dashboard = await apiRequest('/admin/dashboard');
      setMentees(dashboard.students);
      setAdvisorDraft((previous) => ({ ...previous, [studentNim]: advisorNim }));
      setAdvisorHistory(await apiRequest('/admin/advisor-history'));
      setActionMessage('Dosen PA berhasil ditetapkan.');
    } catch (error) {
      setActionMessage(error.message || 'Penetapan Dosen PA gagal.');
    } finally {
      setAdvisorBusyNim('');
    }
  };

  const registerLecturer = async (event) => {
    event.preventDefault();
    if (lecturerForm.password !== lecturerForm.passwordConfirmation) {
      setActionMessage('Konfirmasi password dosen tidak sama.');
      return;
    }
    setLecturerBusy(true);
    try {
      const lecturer = await apiRequest('/admin/lecturers', {
        method: 'POST',
        body: JSON.stringify({
          nip: lecturerForm.nip,
          full_name: lecturerForm.full_name,
          username: lecturerForm.username || lecturerForm.nip,
          email: lecturerForm.email,
          password: lecturerForm.password,
        }),
      });
      setAdminAdvisors((advisors) => [
        ...advisors.filter((advisor) => advisor.nim !== lecturer.nim),
        lecturer,
      ]);
      setLecturerDirectory(await apiRequest('/admin/lecturer-directory'));
      setLecturerForm({ nip: '', full_name: '', username: '', email: '', password: '', passwordConfirmation: '' });
      setLecturerFormVisible(false);
      setActionMessage('Akun dosen berhasil didaftarkan.');
    } catch (error) {
      setActionMessage(error.message || 'Pendaftaran akun dosen gagal.');
    } finally {
      setLecturerBusy(false);
    }
  };

  const updateLecturer = async (nip) => {
    const draft = lecturerEditDraft[nip] || {};
    if (!draft.full_name?.trim()) {
      setActionMessage('Nama dosen wajib diisi.');
      return;
    }
    setLecturerBusy(true);
    try {
      const lecturer = await apiRequest(`/admin/lecturers/${encodeURIComponent(nip)}`, {
        method: 'PUT',
        body: JSON.stringify({
          full_name: draft.full_name,
          username: draft.username,
          email: draft.email || '',
        }),
      });
      setAdminAdvisors((advisors) => advisors.map((advisor) => advisor.nim === nip ? lecturer : advisor));
      setEditingLecturerNip('');
      setLecturerEditDraft((drafts) => {
        const next = { ...drafts };
        delete next[nip];
        return next;
      });
      setActionMessage('Data akun dosen berhasil diperbarui.');
    } catch (error) {
      setActionMessage(error.message || 'Perubahan akun dosen gagal.');
    } finally {
      setLecturerBusy(false);
    }
  };

  const deleteLecturer = async (lecturer) => {
    if (!window.confirm(`Hapus akun dosen ${lecturer.full_name} (${lecturer.nim})? Penetapan dosen PA mahasiswa terkait akan dilepas.`)) return;
    setLecturerBusy(true);
    try {
      await apiRequest(`/admin/lecturers/${encodeURIComponent(lecturer.nim)}`, { method: 'DELETE' });
      setAdminAdvisors((advisors) => advisors.filter((advisor) => advisor.nim !== lecturer.nim));
      setLecturerDirectory(await apiRequest('/admin/lecturer-directory'));
      setMentees((students) => students.map((student) => student.advisor_nim === lecturer.nim ? { ...student, advisor_nim: null } : student));
      setActionMessage(`Akun dosen ${lecturer.full_name} berhasil dihapus.`);
    } catch (error) {
      setActionMessage(error.message || 'Penghapusan akun dosen gagal.');
    } finally {
      setLecturerBusy(false);
    }
  };

  const submitKprs = async () => {
    const courses = kprsDraft.courses.split(',').map((code) => code.trim().toUpperCase()).filter(Boolean);
    if (!kprsDraft.planId || courses.length === 0 || kprsDraft.reason.trim().length < 10) {
      setActionMessage('Pilih KRS approved, isi mata kuliah, dan alasan KPRS minimal 10 karakter.');
      return;
    }
    if (!studentClassesLoaded) {
      setActionMessage('Daftar kelas untuk semester KRS masih dimuat. Tunggu sampai selesai sebelum mengajukan KPRS.');
      return;
    }
    const sourcePlan = studyPlans.find((plan) => plan.id === Number(kprsDraft.planId));
    const selections = Object.fromEntries((sourcePlan?.courses || []).filter((course) => course.class_id).map((course) => [course.code, Number(course.class_id)]));
    Object.entries(kprsClassSelections).forEach(([code, id]) => { if (id) selections[code] = Number(id); });
    for (const code of courses) {
      const options = studentClasses.filter((section) => section.course_code === code);
      const previousClassId = sourcePlan?.courses?.find((course) => course.code === code)?.class_id;
      const selectedSection = options.find((section) => Number(section.class_id) === Number(selections[code]));
      if (options.length && (!selectedSection || !selectedSection.is_open || (selectedSection.remaining_seats <= 0 && Number(previousClassId) !== Number(selectedSection.class_id)))) {
        setActionMessage(`Pilih kelas paralel yang masih dibuka dan memiliki kursi untuk ${code}.`);
        return;
      }
    }
    try {
      await apiRequest('/mahasiswa/kprs', {
        method: 'POST',
        body: JSON.stringify({ study_plan_id: Number(kprsDraft.planId), course_codes: courses, class_selections: selections, reason: kprsDraft.reason.trim() }),
      });
      setKprsRequests(await apiRequest('/mahasiswa/kprs'));
      setActionMessage('Pengajuan KPRS berhasil dikirim.');
    } catch (error) {
      setActionMessage(error.message || 'Pengajuan KPRS gagal.');
    }
  };

  const cancelKprs = async (requestId) => {
    try {
      await apiRequest(`/mahasiswa/kprs/${requestId}`, { method: 'DELETE' });
      setKprsRequests(await apiRequest('/mahasiswa/kprs'));
      setActionMessage('Pengajuan KPRS dibatalkan.');
    } catch (error) {
      setActionMessage(error.message || 'Pembatalan KPRS gagal.');
    }
  };

  const importCourseData = async (event) => {
    const selectedFile = event.target.files?.[0];
    if (!selectedFile || user?.role !== 'admin') return;
    const fileInput = event.currentTarget;

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const result = await apiRequest('/admin/import-data', {
        method: 'POST',
        body: formData,
      });

      setImportStatus(
        result.catalog_replaced
          ? `Katalog aktif diganti dengan ${result.rows_received} mata kuliah dari ${result.file_name}.`
          : `Berhasil memperbarui ${result.rows_received} mata kuliah dari ${result.file_name}.`,
      );
      try {
        setAdminAuditLogs(await apiRequest('/admin/audit-logs'));
      } catch {
        // The catalog import already succeeded; the audit view can refresh later.
      }
      const nextList = await apiRequest('/admin/courses');
      setCourseList(nextList.map((course) => ({ ...course, _originalCode: course.code })));
    } catch (error) {
      setImportStatus(error.message || 'Gagal mengimpor data kursus.');
    } finally {
      fileInput.value = '';
    }
  };

  const updateCourseDraft = (courseCode, field, value) => {
    setCourseList((previous) => previous.map((course) => (
      course._originalCode === courseCode ? { ...course, [field]: value } : course
    )));
  };

  const saveCourse = async (course, isNew = false) => {
    const originalCode = course._originalCode || course.code;
    const payload = { ...course };
    delete payload._originalCode;
    setCourseBusyCode(originalCode);
    setImportStatus('');
    try {
      const updated = await apiRequest(
        isNew ? '/admin/courses' : `/admin/courses/${encodeURIComponent(originalCode)}`,
        { method: isNew ? 'POST' : 'PUT', body: JSON.stringify(payload) },
      );
      if (isNew) {
        setCourseList((previous) => [...previous, { ...updated, _originalCode: updated.code }]);
        setNewCourse({
          code: '', name: '', sks: 3, semester: 1, available_semesters: '1',
          category: '', description: '', prerequisite_text: '', prerequisite_codes: '', day: '', time: '', capacity: 40,
        });
      } else {
        setCourseList((previous) => previous.map((item) => (
          item._originalCode === originalCode ? { ...updated, _originalCode: updated.code } : item
        )));
        setEditingCourseCode('');
      }
      setImportStatus(`Data mata kuliah ${updated.code} berhasil disimpan.`);
      try {
        setAdminAuditLogs(await apiRequest('/admin/audit-logs'));
      } catch {
        // The course write already succeeded; the audit view can refresh later.
      }
    } catch (error) {
      setImportStatus(error.message || 'Data mata kuliah gagal disimpan.');
    } finally {
      setCourseBusyCode('');
    }
  };

  const deactivateCourse = async (course) => {
    const originalCode = course._originalCode || course.code;
    if (!window.confirm(`Nonaktifkan mata kuliah ${originalCode}?`)) return;
    setCourseBusyCode(originalCode);
    try {
      await apiRequest(`/admin/courses/${encodeURIComponent(originalCode)}`, { method: 'DELETE' });
      setCourseList((previous) => previous.filter((item) => item._originalCode !== originalCode));
      setImportStatus(`Mata kuliah ${originalCode} dinonaktifkan.`);
      try {
        setAdminAuditLogs(await apiRequest('/admin/audit-logs'));
      } catch {
        // The course deactivation already succeeded; the audit view can refresh later.
      }
    } catch (error) {
      setImportStatus(error.message || 'Mata kuliah gagal dinonaktifkan.');
    } finally {
      setCourseBusyCode('');
    }
  };

  const downloadAdminExport = async (kind) => {
    const exports = {
      lecturers: { endpoint: '/admin/lecturers/export', filename: 'Data_Dosen_CourseRecom.xlsx' },
      rooms: { endpoint: '/admin/rooms/export', filename: 'Data_Ruangan_CourseRecom.xlsx' },
    };
    const selected = exports[kind];
    if (!selected || user?.role !== 'admin') return;
    const token = localStorage.getItem('courseRecomToken');
    setExportBusy(kind);
    try {
      const response = await fetch(`${API_BASE}${selected.endpoint}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      expireSessionOnUnauthorized(response, token);
      if (!response.ok) {
        let detail = 'Ekspor data gagal.';
        try {
          const body = await response.json();
          detail = body.detail || detail;
        } catch {
          // Keep a safe default message for non-JSON responses.
        }
        throw new Error(detail);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = selected.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      pushToast(kind === 'lecturers' ? 'Data dosen berhasil diekspor.' : 'Data ruangan berhasil diekspor.', 'success');
    } catch (error) {
      pushToast(error.message || 'Ekspor data gagal.', 'error');
    } finally {
      setExportBusy('');
    }
  };

  const refreshRoomList = async () => {
    const rooms = await apiRequest('/admin/rooms');
    setRoomList(rooms);
    return rooms;
  };

  const saveRoom = async (event) => {
    event.preventDefault();
    if (user?.role !== 'admin') return;
    if (roomForm.is_active && (!roomForm.capacity || Number(roomForm.capacity) < 1)) {
      setActionMessage('Isi kapasitas resmi ruang sebelum mengaktifkannya.');
      return;
    }
    setRoomBusy(true);
    try {
      const payload = {
        ...roomForm,
        code: (editingRoomCode || roomForm.code).trim().toUpperCase(),
        capacity: roomForm.capacity === '' ? null : Number(roomForm.capacity),
      };
      await apiRequest(
        editingRoomCode ? `/admin/rooms/${encodeURIComponent(editingRoomCode)}` : '/admin/rooms',
        {
          method: editingRoomCode ? 'PATCH' : 'POST',
          body: JSON.stringify(payload),
        },
      );
      await refreshRoomList();
      const wasEditing = Boolean(editingRoomCode);
      setEditingRoomCode('');
      setRoomForm({ code: '', capacity: '', room_type: 'Ruang kuliah', is_active: false, notes: '' });
      setActionMessage(wasEditing ? 'Inventaris ruang berhasil diperbarui.' : 'Ruang berhasil ditambahkan ke inventaris.');
    } catch (error) {
      setActionMessage(error.message || 'Inventaris ruang gagal disimpan.');
    } finally {
      setRoomBusy(false);
    }
  };

  const editRoom = (room) => {
    setEditingRoomCode(room.code);
    setRoomForm({
      code: room.code,
      capacity: room.capacity ?? '',
      room_type: room.room_type || 'Ruang kuliah',
      is_active: Boolean(room.is_active),
      notes: room.notes || '',
    });
  };

  const saveLecturerDirectoryLink = async (entry) => {
    if (user?.role !== 'admin') return;
    const rawUserId = lecturerDirectoryDraft[entry.id] ?? entry.linked_user_id ?? '';
    const userId = rawUserId ? Number(rawUserId) : null;
    try {
      await apiRequest(`/admin/lecturer-directory/${entry.id}/link`, {
        method: 'PATCH',
        body: JSON.stringify({ user_id: userId }),
      });
      const directory = await apiRequest('/admin/lecturer-directory');
      setLecturerDirectory(directory);
      setLecturerDirectoryDraft((previous) => {
        const next = { ...previous };
        delete next[entry.id];
        return next;
      });
      setActionMessage(userId ? 'Profil dosen berhasil ditautkan ke akun login.' : 'Tautan akun dosen berhasil dilepas.');
    } catch (error) {
      setActionMessage(error.message || 'Pemetaan profil dan akun dosen gagal disimpan.');
    }
  };

  const refreshClassList = async () => {
    const sections = await apiRequest('/admin/classes');
    setClassList(sections);
    return sections;
  };

  const saveParallelClass = async (event) => {
    event.preventDefault();
    if (user?.role !== 'admin') return;
    setClassBusy(true);
    try {
      const payload = {
        ...classForm,
        course_code: classForm.course_code.trim().toUpperCase(),
        class_name: classForm.class_name.trim(),
        lecturer_id: classForm.lecturer_id ? Number(classForm.lecturer_id) : null,
        room: classForm.room.trim(),
        day: classForm.day.trim(),
        start_time: classForm.start_time,
        end_time: classForm.end_time || null,
        capacity: Number(classForm.capacity),
        semester: String(classForm.semester),
        is_open: Boolean(classForm.is_open),
      };
      await apiRequest(editingClassId ? `/admin/classes/${editingClassId}` : '/admin/classes', {
        method: editingClassId ? 'PUT' : 'POST',
        body: JSON.stringify(payload),
      });
      await refreshClassList();
      const wasEditing = Boolean(editingClassId);
      setEditingClassId(null);
      setClassForm({
        course_code: '', class_name: '', lecturer_id: '', room: '', day: 'Senin',
        start_time: '', end_time: '', capacity: 40, semester: '1', is_open: true,
      });
      setActionMessage(wasEditing ? 'Kelas paralel berhasil diperbarui.' : 'Kelas paralel berhasil ditambahkan.');
    } catch (error) {
      setActionMessage(error.message || 'Kelas paralel gagal disimpan.');
    } finally {
      setClassBusy(false);
    }
  };

  const editParallelClass = (section) => {
    setEditingClassId(section.id);
    setClassForm({
      course_code: section.course_code,
      class_name: section.class_name,
      lecturer_id: section.lecturer_id ?? '',
      room: section.room,
      day: section.day,
      start_time: section.start_time,
      end_time: section.end_time,
      capacity: section.capacity,
      semester: String(section.semester),
      is_open: Boolean(section.is_open),
    });
    setView('kelas');
    setMobileMenuOpen(false);
  };

  const closeParallelClass = async (section) => {
    if (section.occupied > 0 || !window.confirm(`Tutup kelas ${section.course_code} - ${section.class_name}?`)) return;
    setClassBusy(true);
    try {
      await apiRequest(`/admin/classes/${section.id}`, { method: 'DELETE' });
      await refreshClassList();
      setActionMessage('Kelas paralel berhasil ditutup. Riwayat kelas tetap disimpan.');
    } catch (error) {
      setActionMessage(error.message || 'Kelas paralel gagal ditutup.');
    } finally {
      setClassBusy(false);
    }
  };

  const updateDraftClass = (courseCode, classId) => {
    const section = studentClasses.find((item) => Number(item.class_id) === Number(classId));
    const nextDraft = draftCourses.map((course) => {
      if (course.code !== courseCode) return course;
      if (!section) return {
        ...course, class_id: null, class_name: null, lecturer_id: null,
        lecturer_name: '', room: '', day: '', start_time: '', end_time: '', schedule: '',
      };
      return {
        ...course, class_id: section.class_id, class_name: section.class_name,
        lecturer_id: section.lecturer_id, lecturer_name: section.lecturer_name,
        room: section.room, day: section.day, start_time: section.start_time,
        end_time: section.end_time, schedule: `${section.day}, ${section.start_time}-${section.end_time}`,
      };
    });
    const conflict = parallelScheduleConflict(nextDraft);
    if (conflict) {
      pushToast(`Jadwal kelas ${conflict.current} berbenturan dengan ${conflict.previous}. Pilih kelas dengan waktu berbeda.`, 'warning');
      return;
    }
    setDraftCourses(nextDraft);
  };

  const deleteStudentAccount = async (student) => {
    if (user?.role !== 'admin' || !window.confirm(
      `Hapus akun mahasiswa ${student.full_name} (${student.nim}) beserta seluruh riwayat KHS dan rencana studinya? Tindakan ini tidak dapat dibatalkan.`,
    )) return;
    setAccountBusyNim(student.nim);
    try {
      await apiRequest(`/admin/students/${encodeURIComponent(student.nim)}`, {
        method: 'DELETE',
      });
      setMentees((previous) => previous.filter((item) => item.nim !== student.nim));
      setActionMessage(`Akun mahasiswa ${student.nim} dan data terkait berhasil dihapus.`);
    } catch (error) {
      setActionMessage(error.message || `Akun mahasiswa ${student.nim} gagal dihapus.`);
    } finally {
      setAccountBusyNim('');
    }
  };

  const uploadKhs = async (event) => {
    event.preventDefault();
    if (!khsFiles.length) return;
    const hasPdf = khsFiles.some((item) => item.name.toLowerCase().endsWith('.pdf'));
    if ((hasPdf && khsFiles.length !== 1) || khsFiles.length > 10) {
      setKhsError('Pilih satu PDF saja atau maksimal 10 gambar halaman KHS.');
      return;
    }
    const uploadForm = event.currentTarget;
    setKhsBusy(true);
    setKhsError('');
    try {
      const formData = new FormData();
      khsFiles.forEach((item) => formData.append('files', item));
      const preview = await apiRequest('/mahasiswa/khs/preview', {
        method: 'POST',
        body: formData,
      });
      setKhsPreview(normalizeKhsPreview(preview));
      setKhsFiles([]);
      uploadForm.reset();
    } catch (error) {
      setKhsError(error.message || 'Dokumen KHS gagal diproses.');
    } finally {
      setKhsBusy(false);
    }
  };

  const updatePreviewMetadata = (field, value) => {
    setKhsPreview((previous) => ({
      ...previous,
      metadata: { ...previous.metadata, [field]: value },    }));
  };

  const updatePreviewCourse = (semesterNumber, courseIndex, field, value) => {
    setKhsPreview((previous) => {
      const courses = previous.courses.map((course, index) => (
        index !== courseIndex || course.semester !== semesterNumber
          ? course
          : {
            ...course,
            [field]: value,
            ...(field === 'grade' ? {
              grade_point: {
                A: 4, 'A-': 3.7, 'B+': 3.3, B: 3, 'B-': 2.7,
                'C+': 2.3, C: 2, 'C-': 1.7, D: 1, E: 0, F: 0,
              }[value.trim().toUpperCase()] ?? null,
              numeric_grade: ({ A: 85, 'A-': 82, 'B+': 78, B: 75, 'B-': 72, 'C+': 68, C: 65, 'C-': 62, D: 50, E: 40, F: 30 })[value.trim().toUpperCase()] ?? '',
              numeric_grade_estimated: true,
            } : field === 'numeric_grade' ? { numeric_grade_estimated: false } : {}),
          }
      ));
      return {
        ...previous,
        courses,
        semesters: previous.semesters.map((semester) => (
          semester.semester === semesterNumber
            ? { ...semester, courses: courses.filter((course) => course.semester === semesterNumber) }
            : semester
        )),
      };
    });
  };

  const updatePreviewSemester = (semesterNumber, field, value) => {
    setKhsPreview((previous) => {
      if (field !== 'semester') {
        return {
          ...previous,
          semesters: previous.semesters.map((semester) => (
            semester.semester === semesterNumber ? { ...semester, [field]: value } : semester
          )),
        };
      }
      const nextSemester = Number(value);
      if (
        !Number.isInteger(nextSemester)
        || nextSemester < 1
        || nextSemester > 14
        || previous.semesters.some((semester) => semester.semester === nextSemester && semester.semester !== semesterNumber)
      ) return previous;
      const courses = previous.courses.map((course) => (
          course.semester === semesterNumber ? { ...course, semester: nextSemester } : course
      ));
      const semesters = previous.semesters.map((semester) => (
        semester.semester === semesterNumber ? { ...semester, semester: nextSemester } : semester
      ));
      return {
        ...previous,
        courses,
        semesters: semesters.map((semester) => ({
          ...semester,
          courses: courses.filter((course) => course.semester === semester.semester),
        })),
      };
    });
  };

  const addPreviewCourse = (semesterNumber) => {
    setKhsPreview((previous) => {
      const course = {
        semester: semesterNumber,
        code: '',
        name: '',
        sks: 3,
        grade: '',
        numeric_grade: '',
        grade_point: null,
      };
      return {
        ...previous,
        courses: [...previous.courses, course],
        semesters: previous.semesters.map((semester) => (
          semester.semester === semesterNumber
            ? { ...semester, courses: [...semester.courses, course] }
            : semester
        )),
      };
    });
  };

  const removePreviewCourse = (semesterNumber, courseIndex) => {
    setKhsPreview((previous) => {
      const courses = previous.courses.filter((course, index) => (
        index !== courseIndex || course.semester !== semesterNumber
      ));
      return {
        ...previous,
        courses,
        semesters: previous.semesters.map((semester) => (
          semester.semester === semesterNumber
            ? { ...semester, courses: courses.filter((course) => course.semester === semesterNumber) }
            : semester
        )),
      };
    });
  };

  const refreshStudentData = async () => {
    const [profileData, recommendationData, khsDocuments] = await Promise.all([
      apiRequest('/mahasiswa/profil'),
      apiRequest('/mahasiswa/rekomendasi'),
      apiRequest('/mahasiswa/khs'),
    ]);
    setProfile(profileData);
    setRecommendationResult(recommendationData);
    setAcademicHistory(khsDocuments);
  };

  const discardKhsPreview = async () => {
    if (!khsPreview) return;
    setKhsBusy(true);
    setKhsError('');
    try {
      await apiRequest(`/mahasiswa/khs/${khsPreview.id}`, { method: 'DELETE' });
      setKhsPreview(null);
      await refreshStudentData();
    } catch (error) {
      setKhsError(error.message || 'Pratinjau KHS gagal dibatalkan.');
    } finally {
      setKhsBusy(false);
    }
  };

  const confirmKhs = async () => {
    if (!khsPreview) return;
    setKhsBusy(true);
    setKhsError('');
    try {
      const courses = khsPreview.courses.map((course) => ({
        semester: Number(course.semester),
        code: course.code.trim().toUpperCase(),
        name: course.name.trim(),
        sks: Number(course.sks),
        grade: course.grade.trim().toUpperCase(),
        numeric_grade: course.numeric_grade === '' ? null : Number(course.numeric_grade),
        numeric_grade_estimated: Boolean(course.numeric_grade_estimated),
        grade_point: course.grade_point,
      }));
      const currentSemester = Number(khsPreview.metadata.current_semester)
        || Math.max(...courses.map((course) => course.semester));
      const calculatedIpk = calculateIpkFromSemesterIps(khsPreview.semesters, currentSemester);
      if (calculatedIpk === null) {
        setKhsError(`IPS wajib diisi untuk seluruh semester 1 sampai ${currentSemester} dengan nilai 0,00–4,00 sebelum KHS dikonfirmasi.`);
        return;
      }
      const response = await apiRequest(`/mahasiswa/khs/${khsPreview.id}/confirm`, {
        method: 'POST',
        body: JSON.stringify({
          nim: khsPreview.metadata.nim,
          full_name: khsPreview.metadata.full_name,
          program_study: khsPreview.metadata.program_study || '',
          current_semester: currentSemester,
          ipk: calculatedIpk,
          ip_semesters: Object.fromEntries(khsPreview.semesters.map((semester) => [
            semester.semester,
            Number(semester.ip_semester),
          ])),
          courses,
        }),
      });
      setKhsPreview(null);
      setActionMessage(`KHS ${response.document.filename} berhasil dikonfirmasi. Rekomendasi untuk semester ${currentSemester + 1} siap diperiksa.`);
      setView('dashboard');
      try {
        await refreshStudentData();
      } catch (error) {
        setActionMessage(
          `KHS ${response.document.filename} berhasil dikonfirmasi, tetapi data dashboard gagal diperbarui: ${error.message || 'silakan muat ulang halaman.'}`,
        );
      }
    } catch (error) {
      setKhsError(error.message || 'Konfirmasi KHS gagal.');
    } finally {
      setKhsBusy(false);
    }
  };

  const beginHistoryEdit = (document) => {
    const ip_semesters = Object.fromEntries((document.semesters || []).map((item) => [String(item.semester), item.ip_semester ?? '']));
    const currentIps = (document.semesters || []).map((item) => ip_semesters[String(item.semester)]);
    const completeIps = currentIps.length > 0 && currentIps.every((value) => (
      value !== '' && Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 4
    ));
    const calculatedIpk = completeIps
      ? (currentIps.reduce((sum, value) => sum + Number(value), 0) / currentIps.length).toFixed(2)
      : document.metadata?.ipk ?? '';
    setHistoryEditId(document.id);
    setHistoryEditDraft({
      ipk: calculatedIpk,
      courses: (document.courses || []).map((course) => ({ ...course })),
      ip_semesters,
    });
  };

  const updateHistoryIps = (document, semesterNumber, value) => {
    setHistoryEditDraft((draft) => {
      if (!draft) return draft;
      const ip_semesters = { ...draft.ip_semesters, [String(semesterNumber)]: value };
      const semesterValues = (document.semesters || []).map((item) => ip_semesters[String(item.semester)]);
      const completeIps = semesterValues.length > 0 && semesterValues.every((item) => (
        item !== '' && Number.isFinite(Number(item)) && Number(item) >= 0 && Number(item) <= 4
      ));
      return {
        ...draft,
        ip_semesters,
        ipk: completeIps
          ? (semesterValues.reduce((sum, item) => sum + Number(item), 0) / semesterValues.length).toFixed(2)
          : draft.ipk,
      };
    });
  };

  const saveHistoryEdit = async (document) => {
    if (!historyEditDraft) return;
    const invalidCourse = historyEditDraft.courses.find((course) => (
      course.numeric_grade !== '' && (
        !Number.isFinite(Number(course.numeric_grade))
        || Number(course.numeric_grade) < 0 || Number(course.numeric_grade) > 100
      )
    ));
    if (invalidCourse) {
      pushToast(`Nilai angka ${invalidCourse.code} harus diisi antara 0 sampai 100.`, 'error');
      return;
    }
    const submittedIps = Object.fromEntries(
      Object.entries(historyEditDraft.ip_semesters)
        .filter(([, value]) => value !== '' && value !== null)
        .map(([semester, value]) => [semester, Number(value)]),
    );
    if (Object.values(submittedIps).some((value) => !Number.isFinite(value) || value < 0 || value > 4)) {
      pushToast('IPS harus berada di antara 0,00 sampai 4,00.', 'error');
      return;
    }
    setHistoryEditBusy(true);
    try {
      const response = await apiRequest(`/mahasiswa/khs/${document.id}/edit`, {
        method: 'PATCH',
        body: JSON.stringify({
          ipk: historyEditDraft.ipk === '' ? null : Number(historyEditDraft.ipk),
          courses: historyEditDraft.courses
            .filter((course) => course.numeric_grade !== '' && course.numeric_grade !== null && course.numeric_grade !== undefined)
            .map((course) => ({
              semester: Number(course.semester), code: course.code, numeric_grade: Number(course.numeric_grade),
            })),
          ip_semesters: submittedIps,
        }),
      });
      setAcademicHistory((previous) => previous.map((item) => item.id === document.id ? response.document : item));
      setHistoryEditId(null);
      setHistoryEditDraft(null);
      await refreshStudentData();
      pushToast('Nilai angka, IPS, dan IPK yang dihitung dari rata-rata IPS berhasil diperbarui.', 'success');
    } catch (error) {
      pushToast(error.message || 'Perubahan riwayat KHS gagal disimpan.', 'error');
    } finally {
      setHistoryEditBusy(false);
    }
  };

  const trainModel = async () => {
    setModelStatus('');
    try {
      const result = await apiRequest('/admin/model/train', { method: 'POST' });
      const precision = result.metrics.precision_at_5 === null ? 'belum cukup data' : `${(result.metrics.precision_at_5 * 100).toFixed(1)}%`;
      const recall = result.metrics.recall_at_5 === null ? 'belum cukup data' : `${(result.metrics.recall_at_5 * 100).toFixed(1)}%`;
      setModelStatus(
        `Model ${result.version} (${new Date(result.trained_at).toLocaleString('id-ID')}) dibuat dari ${result.dataset_size} record. Precision@5: ${precision}; Recall@5: ${recall}.`,
      );
    } catch (error) {
      setModelStatus(error.message || 'Training model gagal.');
    }
  };

  const dashboardProfile = profile || user;
  const curriculumLoading = user?.role === 'mahasiswa' && !curriculumLoaded;
  const totalDraftSks = draftCourses.reduce((total, course) => total + Number(course.sks || 0), 0);
  const studentIpk = profile?.ipk ?? user?.ipk;
  const kuotaSks = studentIpk == null ? 20 : studentIpk >= 3.35 ? 24 : studentIpk >= 3 ? 22 : 20;
  const approvedStudyPlan = studyPlans.find((plan) => (
    plan.status === 'approved'
    && recommendationResult.target_semester != null
    && plan.semester === recommendationResult.target_semester
  ));
  const interestDistribution = [...new Set(
    mentees.map((student) => canonicalizeInterests(student.interests || '')).filter(Boolean),
  )].map((interest) => ({
    name: interest,
    count: mentees.filter((student) => canonicalizeInterests(student.interests || '') === interest).length,
  }));
  const mostPopularInterest = [...interestDistribution].sort((left, right) => right.count - left.count)[0];
  const pendingPlans = studyPlans.filter((plan) => plan.status === 'pending');
  const latestStudyPlan = studyPlans[0] || null;
  const curriculumBySemester = Array.from({ length: 8 }, (_, index) => {
    const semester = index + 1;
    return {
      semester,
      courses: curriculumCourses.filter((course) => (
        (course.available_semesters || String(course.semester))
          .split(',')
          .map((value) => Number(value.trim()))
          .includes(semester)
      )),
    };
  });
  const totalCurriculumSks = curriculumCourses.reduce((total, course) => total + Number(course.sks || 0), 0);
  const navigationItems = [
    { key: 'dashboard', label: 'Dashboard', Icon: Home },
    ...(user?.role === 'mahasiswa' ? [
      { key: 'kurikulum', label: 'Kurikulum', Icon: BookOpenCheck },
      { key: 'khs', label: 'Upload KHS', Icon: FileUp },
      { key: 'rekomendasi', label: 'Rekomendasi MK', Icon: BookOpenCheck },
      { key: 'riwayat', label: 'Riwayat KHS', Icon: FileClock },
      { key: 'minat', label: 'Minat & Profil', Icon: UserRound },
    ] : []),
    ...(user?.role === 'admin' ? [
      { key: 'admin', label: 'Manajemen Data', Icon: Settings },
      { key: 'kelas', label: 'Kelas & Jadwal', Icon: CalendarDays },
      { key: 'akun-dosen', label: 'Daftar Akun Dosen PA', Icon: UsersRound },
      { key: 'riwayat-pa', label: 'Riwayat Dosen PA', Icon: History },
    ] : []),
    ...(user?.role === 'dosen' ? [{ key: 'bimbingan', label: 'Bimbingan Mahasiswa', Icon: UsersRound }] : []),
    { key: 'profil', label: 'Edit Profil', Icon: UserRound },
    { key: 'tentang', label: 'Tentang', Icon: Info },
    { key: 'panduan', label: 'Panduan', Icon: HelpCircle },
  ];

  const navigateTo = (key) => {
    if (key === 'profil') loadAccountProfile().catch((error) => pushToast(error.message || 'Profil gagal dimuat.', 'error'));
    if (key === 'minat') openInterests();
    else setView(key);
    setMobileMenuOpen(false);
  };

  const addToDraft = (course) => {
    if (approvedStudyPlan) {
      pushToast('KRS sudah disetujui dan tidak dapat diubah.', 'warning');
      return;
    }
    if (draftCourses.some((item) => item.code === course.code)) return;
    if (totalDraftSks + Number(course.sks) > kuotaSks) {
      pushToast(`Tidak dapat menambahkan ${course.code}. Total SKS melebihi batas maksimum (${kuotaSks} SKS).`, 'warning');
      return;
    }
    setDraftCourses((previousDraft) => [...previousDraft, course]);
  };

  const removeFromDraft = (courseCode) => {
    const course = draftCourses.find((item) => item.code === courseCode);
    if (course && isMandatoryCourse(course)) {
      pushToast('Mata kuliah wajib tidak dapat dihapus dari draft KRS.', 'warning');
      return;
    }
    if (approvedStudyPlan) {
      pushToast('KRS sudah disetujui dan tidak dapat diubah.', 'warning');
      return;
    }
    setDraftCourses((previousDraft) => previousDraft.filter((item) => item.code !== courseCode));
  };

  const clearDraft = () => {
    if (approvedStudyPlan) {
      pushToast('KRS sudah disetujui dan tidak dapat diubah.', 'warning');
      return;
    }
    setDraftCourses((currentDraft) => currentDraft.filter(isMandatoryCourse));
  };

  const submitStudyPlan = async () => {
    if (user?.role !== 'mahasiswa' || draftCourses.length === 0) return;
    if (approvedStudyPlan) {
      pushToast('KRS sudah disetujui dan tidak dapat diubah.', 'warning');
      return;
    }
    if (studyPlanSubmissionRef.current) return;
    studyPlanSubmissionRef.current = true;
    setStudyPlanBusy(true);
    setActionMessage('');
    try {
      if (recommendationResult.target_semester && !studentClassesLoaded) {
        pushToast('Daftar kelas paralel masih dimuat. Coba ajukan kembali setelah selesai.', 'warning');
        return;
      }
      for (const course of draftCourses) {
        const sections = studentClasses.filter((section) => section.course_code === course.code);
        if (sections.length && !sections.some((section) => Number(section.class_id) === Number(course.class_id) && section.is_open && section.remaining_seats > 0)) {
          pushToast(`Pilih kelas yang masih tersedia untuk ${course.code} sebelum mengajukan KRS.`, 'warning');
          return;
        }
      }
      const classSelections = Object.fromEntries(draftCourses.filter((course) => course.class_id).map((course) => [course.code, Number(course.class_id)]));      const planPayload = {
        course_codes: draftCourses.map((course) => course.code),
        class_selections: classSelections,
      };
      const revisionPlan = studyPlans.find((item) => (
        item.status === 'revision_requested'
        && item.semester === recommendationResult.target_semester
      ));
      let plan;
      if (revisionPlan) {
        await apiRequest(`/mahasiswa/rencana-studi/${revisionPlan.id}`, {
          method: 'PATCH',
          body: JSON.stringify(planPayload),
        });
        plan = await apiRequest(`/mahasiswa/rencana-studi/${revisionPlan.id}/submit`, { method: 'POST' });
        setStudyPlans((previousPlans) => [plan, ...previousPlans.filter((item) => item.id !== plan.id)]);
      } else {
        plan = await apiRequest('/mahasiswa/rencana-studi', {
          method: 'POST',
          body: JSON.stringify(planPayload),
        });
        setStudyPlans((previousPlans) => [plan, ...previousPlans]);
      }
      setDraftCourses([]);
      setActionMessage('Rencana studi berhasil diajukan ke dosen PA.');
    } catch (error) {
      setActionMessage(error.message || 'Pengajuan rencana studi gagal.');
    } finally {
      studyPlanSubmissionRef.current = false;
      setStudyPlanBusy(false);
    }
  };

  useEffect(() => {
    const revisionPlan = studyPlans.find((item) => (
      item.status === 'revision_requested'
      && item.semester === recommendationResult.target_semester
      && Array.isArray(item.courses)
    ));
    if (revisionPlan?.courses?.length) {
      setDraftCourses(revisionPlan.courses);
    }
  }, [studyPlans, recommendationResult.target_semester, setDraftCourses]);

  const reviewStudyPlan = async (planId, status) => {
    const advisorNote = (reviewNotes[planId] ?? '').trim();
    const rejectedCourseCodes = reviewRejectedCourses[planId] ?? [];
    if (status === 'revision_requested' && advisorNote.length < 10) {
      setActionMessage('Alasan revisi wajib diisi minimal 10 karakter.');
      return;
    }
    if (status === 'revision_requested' && rejectedCourseCodes.length === 0) {
      setActionMessage('Pilih minimal satu mata kuliah yang perlu direvisi.');
      return;
    }
    setStudyPlanBusy(true);
    setActionMessage('');
    try {
      const result = await apiRequest(`/dosen/rencana-studi/${planId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status, advisor_note: advisorNote, rejected_course_codes: status === 'revision_requested' ? rejectedCourseCodes : [] }),
      });
      setStudyPlans((previousPlans) => previousPlans.map((plan) => (
        plan.id === planId
          ? { ...plan, status: result.status, advisor_note: result.advisor_note, updated_at: result.updated_at }
          : plan
      )));
      setActionMessage(status === 'approved' ? 'Rencana studi disetujui.' : 'Catatan revisi berhasil dikirim.');
    } catch (error) {
      setActionMessage(error.message || 'Review rencana studi gagal disimpan.');
    } finally {
      setStudyPlanBusy(false);
    }
  };

  const reviewKprs = async (requestId, status) => {
    const note = kprsReviewNotes[requestId] ?? '';
    if (!note.trim() || (status !== 'approved' && note.trim().length < 10)) {
      setActionMessage(status === 'approved' ? 'Catatan keputusan KPRS wajib diisi.' : 'Alasan revisi/penolakan KPRS wajib diisi minimal 10 karakter.');
      return;
    }
    setStudyPlanBusy(true);
    setActionMessage('');
    try {
      const result = await apiRequest(`/dosen/kprs/${requestId}`, {
        method: 'PUT',
        body: JSON.stringify({ status, note: note.trim() }),
      });
      setMenteeKprsRequests((previous) => previous.map((request) => (
        request.id === requestId
          ? { ...request, status: result.status, reviewer_note: result.reviewer_note }
          : request
      )));
      setActionMessage(status === 'approved' ? 'Pengajuan KPRS disetujui.' : 'Keputusan KPRS berhasil disimpan.');
    } catch (error) {
      setActionMessage(error.message || 'Keputusan KPRS gagal disimpan.');
    } finally {
      setStudyPlanBusy(false);
    }
  };

  const pageContent = (() => {
    if (!user) return null;

    if (view === 'kurikulum' && user.role === 'mahasiswa') {
      return (
        <div className="card">
          <h2>Kurikulum Program Studi</h2>
          <p className="muted">Daftar mata kuliah semester 1–8 beserta bobot SKS, kategori, prasyarat, dan keterangannya. Halaman ini hanya untuk melihat informasi kurikulum.</p>
          {curriculumError && <div className="error-notice" role="alert">{curriculumError}</div>}
          {curriculumLoading ? (
            <p className="muted" role="status">Memuat data kurikulum...</p>
          ) : (
            <>
              <div className="stat-grid">
                <div className="stat"><small>Jumlah mata kuliah</small><strong>{curriculumCourses.length}</strong></div>
                <div className="stat"><small>Total beban SKS katalog</small><strong>{totalCurriculumSks} SKS</strong></div>
                <div className="stat"><small>Rentang kurikulum</small><strong>8 semester</strong></div>
              </div>
              {curriculumCourses.length === 0 && !curriculumError && (
                <p className="notice">Data kurikulum belum tersedia. Silakan hubungi admin program studi.</p>
              )}
              {curriculumBySemester.map(({ semester, courses }) => (
                <section className="history-document curriculum-semester" key={semester}>
                  <div className="preview-header">
                    <div>
                      <h3>Semester {semester}</h3>
                      <p className="muted">{courses.reduce((total, course) => total + Number(course.sks || 0), 0)} SKS ditawarkan</p>
                    </div>
                    <span className="status-pill status-pending">{courses.length} mata kuliah</span>
                  </div>
                  {courses.length > 0 ? (
                    <div className="table-wrap">
                      <table className="table curriculum-table">
                        <thead>
                          <tr>
                            <th>Kode</th>
                            <th>Mata kuliah</th>
                            <th>SKS</th>
                            <th>Kategori</th>
                            <th>Prasyarat / syarat</th>
                            <th>Keterangan</th>
                            <th>Jadwal</th>
                          </tr>
                        </thead>
                        <tbody>
                          {courses.map((course) => (
                            <tr key={`${semester}-${course.code}`}>
                              <td><strong>{course.code}</strong></td>
                              <td>{course.name}<br /><span className="muted">Semester {course.available_semesters}</span></td>
                              <td>{course.sks}</td>
                              <td>{course.category || '—'}</td>
                              <td>{course.prerequisite_text || course.prerequisite_codes || 'Tidak ada prasyarat tercatat'}</td>
                              <td>{course.description || '—'}</td>
                              <td>{[course.day, course.time].filter(Boolean).join(' · ') || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : <p className="muted">Belum ada mata kuliah yang tercatat untuk semester ini.</p>}
                </section>
              ))}
            </>
          )}
        </div>
      );
    }

    if (view === 'khs') {
      return (
        <div className="card">
          <h2>Unggah KHS Lengkap</h2>
          <p>Unggah satu PDF lengkap atau hingga 10 foto halaman KHS. Sistem membaca teks dengan OCR, lalu menyiapkan pratinjau yang dapat Anda periksa dan koreksi.</p>
          <ol className="khs-process" aria-label="Alur membaca KHS">
            <li><strong>1. Pilih dokumen</strong><span>PDF atau foto JPG, PNG, WEBP, TIFF, BMP.</span></li>
            <li><strong>2. Baca otomatis</strong><span>OCR membaca identitas dan tabel nilai.</span></li>
            <li><strong>3. Periksa hasil</strong><span>Koreksi data yang kurang tepat sebelum disimpan.</span></li>
            <li><strong>4. Konfirmasi</strong><span>Riwayat dan rekomendasi diperbarui setelah konfirmasi.</span></li>
          </ol>
          <form className="upload-form" onSubmit={uploadKhs}>
            <label htmlFor="khs-pdf">Pilih PDF atau gambar KHS (maks. 20 MB total)</label>
            <input
              id="khs-pdf"
              type="file"
              accept="application/pdf,.pdf,image/jpeg,.jpg,.jpeg,image/png,.png,image/webp,.webp,image/tiff,.tif,.tiff,image/bmp,.bmp"
              multiple
              onChange={(event) => {
                const selectedFiles = Array.from(event.target.files || []);
                setKhsError('');
                if (selectedFiles.length > 10) {
                  setKhsFiles([]);
                  event.target.value = '';
                  setKhsError('Pilih maksimal 10 gambar halaman KHS sekaligus.');
                  return;
                }
                setKhsFiles(selectedFiles);
              }}
            />
            {khsFiles.length > 0 && (
              <span className="muted" aria-live="polite">
                {khsFiles.map((item) => item.name).join(', ')}
              </span>
            )}
            <button className="btn primary" type="submit" disabled={!khsFiles.length || khsBusy}>
              {khsBusy && !khsPreview ? 'Mengunggah dan membaca...' : 'Baca dan Pratinjau KHS'}
            </button>
          </form>
          {khsPreview && (
            <section className="preview-section" aria-labelledby="khs-preview-title">
              <div className="preview-header">
                <div>
                  <h3 id="khs-preview-title">Periksa hasil ekstraksi</h3>
                  <p className="muted">{khsPreview.filename}</p>
                  {khsPreview.source_type === 'image' && <p className="muted">Hasil pembacaan OCR gambar — pastikan nilai dan grade sudah sesuai KHS.</p>}
                </div>
                <span className="status-pill status-menunggu">Menunggu konfirmasi</span>
              </div>
              <div className="metadata-grid">
                <label>NIM
                  <input value={khsPreview.metadata.nim || ''} onChange={(event) => updatePreviewMetadata('nim', event.target.value)} />
                </label>
                <label>Nama mahasiswa
                  <input value={khsPreview.metadata.full_name || ''} onChange={(event) => updatePreviewMetadata('full_name', event.target.value)} />
                </label>
                <label>Program studi
                  <input value={khsPreview.metadata.program_study || ''} onChange={(event) => updatePreviewMetadata('program_study', event.target.value)} />
                </label>
                <label>IPK (otomatis)
                  <input
                    type="number"
                    min="0"
                    max="4"
                    step="0.01"
                    value={calculateIpkFromSemesterIps(
                      khsPreview.semesters,
                      Number(khsPreview.metadata.current_semester) || Math.max(...khsPreview.semesters.map((item) => Number(item.semester))),
                    ) ?? ''}
                    readOnly
                    aria-readonly="true"
                  />
                  <small className="muted">Rata-rata IPS seluruh semester, dihitung otomatis saat IPS berubah.</small>
                </label>
              </div>
              <div className="semester-summary">
                {khsPreview.semesters.map((semester, index) => (
                  <div className="semester-summary-item" key={`${semester.semester}-${index}`}>
                    <span>{semester.courses.length} mata kuliah</span>
                    <label>Nomor semester
                      <input
                        type="number" min="1" max="14" step="1" value={semester.semester}
                        onChange={(event) => updatePreviewSemester(semester.semester, 'semester', event.target.value)}
                      />
                    </label>
                    <label>IPS semester {semester.semester} *
                      <input
                        type="number"
                        min="0"
                        max="4"
                        step="0.01"
                        required
                        value={semester.ip_semester ?? ''}
                        onChange={(event) => updatePreviewSemester(semester.semester, 'ip_semester', event.target.value)}
                        aria-label={`IPS wajib semester ${semester.semester}`}
                      />
                    </label>
                  </div>
                ))}
              </div>
              {khsPreview.semesters.map((semester, semesterIndex) => (
                <section className="semester-preview" key={`${semester.semester}-${semesterIndex}`}>
                  <h4>Semester {semester.semester}</h4>
                  <div className="table-wrap"><table className="table editable-table">
                    <thead><tr><th>Kode</th><th>Mata kuliah</th><th>SKS</th><th>Nilai angka</th><th>Grade</th><th>Aksi</th></tr></thead>
                    <tbody>{semester.courses.map((course) => {
                      const courseIndex = khsPreview.courses.indexOf(course);
                      return (
                        <tr key={`${semester.semester}-${courseIndex}`}>
                          <td><input aria-label={`Kode mata kuliah semester ${semester.semester}`} value={course.code} onChange={(event) => updatePreviewCourse(semester.semester, courseIndex, 'code', event.target.value)} /></td>
                          <td><input aria-label={`Nama mata kuliah semester ${semester.semester}`} value={course.name} onChange={(event) => updatePreviewCourse(semester.semester, courseIndex, 'name', event.target.value)} /></td>
                          <td><input aria-label={`SKS mata kuliah semester ${semester.semester}`} type="number" min="1" max="10" value={course.sks} onChange={(event) => updatePreviewCourse(semester.semester, courseIndex, 'sks', event.target.value)} /></td>
                          <td><input aria-label={`Nilai angka semester ${semester.semester}`} type="number" min="0" max="100" step="0.01" value={course.numeric_grade ?? ''} onChange={(event) => updatePreviewCourse(semester.semester, courseIndex, 'numeric_grade', event.target.value)} /></td>
                          <td><input aria-label={`Grade semester ${semester.semester}`} value={course.grade} onChange={(event) => updatePreviewCourse(semester.semester, courseIndex, 'grade', event.target.value)} /></td>
                          <td><button className="btn outline" type="button" onClick={() => removePreviewCourse(semester.semester, courseIndex)}>Hapus</button></td>
                        </tr>
                      );
                    })}</tbody>
                  </table></div>
                  <button className="btn outline" type="button" onClick={() => addPreviewCourse(semester.semester)}>Tambah mata kuliah</button>
                </section>
              ))}
              <div className="preview-actions">
                <button className="btn primary" type="button" disabled={khsBusy || !khsPreview.courses.length} onClick={confirmKhs}>
                  {khsBusy ? 'Menyimpan...' : 'Data sudah benar — konfirmasi & simpan'}
                </button>
                <button className="btn outline" type="button" disabled={khsBusy} onClick={discardKhsPreview}>Unggah ulang</button>
              </div>
            </section>
          )}
          <section className="history-list">
            <h3>Status dokumen KHS</h3>
            {academicHistory.length
              ? academicHistory.map((document) => (
                <div key={document.id} className="history-row">
                  <span>{document.filename}</span><span className={`status-pill status-${document.status}`}>{document.status}</span>
                  {document.status === 'pending' && <button type="button" className="btn outline" onClick={() => {
                    setKhsPreview(normalizeKhsPreview(document));
                  }}>Lanjutkan pratinjau</button>}
                </div>
              ))
              : <p className="muted">Belum ada dokumen KHS.</p>}
          </section>
        </div>
      );
    }

    if (view === 'dashboard' && user.role === 'admin') {
      const confirmedKhsCount = Number(adminAnalytics?.confirmed_khs_students ?? mentees.filter((student) => student.khs_confirmed).length);
      const totalStudents = Number(adminAnalytics?.total_students ?? mentees.length);
      const totalAdvisors = Number(adminAnalytics?.total_advisors ?? adminAdvisors.length);
      const totalAcademicAccounts = Math.max(1, totalStudents + totalAdvisors);
      const courseSemesterCounts = adminAnalytics?.courses_by_semester || Array.from({ length: 8 }, (_, index) => ({ semester: index + 1, count: 0 }));
      return (
        <div className="card">
          <h2>Dashboard Admin Prodi</h2>
          <p className="muted">Ringkasan akun mahasiswa dan dosen PA yang terdaftar.</p>
          <div className="admin-donut-grid">
            <AnimatedDonut title="Total mahasiswa" value={totalStudents} percentage={(totalStudents / totalAcademicAccounts) * 100} subtitle="Proporsi akun mahasiswa" accent="teal" />
            <AnimatedDonut title="KHS terkonfirmasi" value={confirmedKhsCount} percentage={totalStudents ? (confirmedKhsCount / totalStudents) * 100 : 0} subtitle={`${totalStudents ? Math.round((confirmedKhsCount / totalStudents) * 100) : 0}% dari mahasiswa`} accent="blue" />
            <AnimatedDonut title="Total dosen PA" value={totalAdvisors} percentage={(totalAdvisors / totalAcademicAccounts) * 100} subtitle="Proporsi akun dosen" accent="violet" />
          </div>
          <div className="admin-analytics-meta">
            <span>{adminAnalytics?.total_active_courses ?? courseList.length} mata kuliah aktif terdaftar</span>
            <span>Data diperbarui otomatis setiap 30 detik</span>
          </div>
          <SemesterCourseChart items={courseSemesterCounts} />
          <section style={{ marginTop: 24 }}>
            <h3>Data Mahasiswa</h3>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>NIM</th><th>Nama</th><th>Semester</th><th>IPK</th>
                    <th>Minat</th><th>Status KHS</th><th>Dosen PA</th><th>Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {mentees.map((student) => (
                    <tr key={student.nim}>
                      <td>{student.nim}</td>
                      <td>{student.full_name}</td>
                      <td>{student.semester ?? '—'}</td>
                      <td>{student.ipk ?? '—'}</td>
                      <td>{canonicalizeInterests(student.interests || '').replaceAll(',', ', ') || 'Belum dipilih'}</td>
                      <td>{student.khs_confirmed ? 'Terkonfirmasi' : 'Belum ada KHS'}</td>
                      <td>
                        <select
                          value={advisorDraft[student.nim] || student.advisor_nim || ''}
                          onChange={(event) => setAdvisorDraft((previous) => ({ ...previous, [student.nim]: event.target.value }))}
                        >
                          <option value="">Belum ditetapkan</option>
                          {adminAdvisors.map((advisor) => <option key={advisor.nim} value={advisor.nim}>{advisor.full_name}</option>)}
                        </select>
                        <button
                          className="btn outline"
                          type="button"
                          disabled={
                            Boolean(advisorBusyNim)
                            || !advisorDraft[student.nim]
                            || advisorDraft[student.nim] === (student.advisor_nim || '')
                          }
                          onClick={() => assignStudentAdvisor(student.nim)}
                        >
                          {advisorBusyNim === student.nim ? 'Menyimpan...' : 'Simpan'}
                        </button>
                      </td>
                      <td>
                        <button
                          className="btn outline"
                          type="button"
                          disabled={Boolean(accountBusyNim)}
                          onClick={() => deleteStudentAccount(student)}
                        >
                          {accountBusyNim === student.nim ? 'Menghapus...' : 'Hapus akun'}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {mentees.length === 0 && (
                    <tr><td colSpan="8" className="muted">Belum ada akun mahasiswa terdaftar.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
          <section style={{ marginTop: 24 }}>
            <h3>Data Dosen PA</h3>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>NIP / ID</th><th>Nama Dosen PA</th><th>Username</th><th>Email</th></tr></thead>
                <tbody>
                  {adminAdvisors.map((advisor) => (
                    <tr key={advisor.nim}>
                      <td>{advisor.nim}</td><td>{advisor.full_name}</td><td>{advisor.username || advisor.nim}</td><td>{advisor.email || '—'}</td>
                    </tr>
                  ))}
                  {adminAdvisors.length === 0 && (
                    <tr><td colSpan="4" className="muted">Belum ada akun dosen PA terdaftar.</td></tr>
                  )}
                </tbody>
              </table>            </div>
          </section>
        </div>
      );
    }

    if (view === 'dashboard' && user.role === 'dosen') {
      const studentsWithKhs = mentees.filter((student) => student.khs_confirmed).length;
      return (
        <div className="card">
          <h2>Dashboard Dosen PA</h2>
          <div className="stat-grid">
            <div className="stat"><small>Akun mahasiswa terdaftar</small><strong>{mentees.length}</strong></div>
            <div className="stat"><small>KHS terkonfirmasi</small><strong>{studentsWithKhs}</strong></div>
            <div className="stat"><small>Rencana menunggu review</small><strong>{pendingPlans.length}</strong></div>
            <div className="stat"><small>Rencana disetujui</small><strong>{studyPlans.filter((plan) => plan.status === 'approved').length}</strong></div>
          </div>
          <div className="preview-header">
            <div>
              <h3>Rencana studi terbaru</h3>
              <p className="muted">Pantau rekomendasi mahasiswa bimbingan, tinjau rencana studi, dan berikan arahan.</p>
            </div>
            <button className="btn primary" type="button" onClick={() => setView('bimbingan')}>
              Buka bimbingan mahasiswa
            </button>
          </div>
          {pendingPlans.length > 0 ? pendingPlans.slice(0, 3).map((plan) => (
            <article className="recommendation-card" key={plan.id}>
              <div className="recommendation-heading">
                <div>
                  <strong>{plan.student_name} ({plan.student_nim})</strong>
                  <p className="muted">Semester {plan.semester} · {plan.courses.length} mata kuliah · diajukan {new Date(plan.created_at).toLocaleDateString('id-ID')}</p>
                </div>
                <span className="status-pill status-menunggu">Menunggu review</span>
              </div>
              <p>{plan.courses.map((course) => course.name).join(' · ')}</p>
            </article>
          )) : <p className="muted">Tidak ada rencana studi yang menunggu review.</p>}
          <div className="grid-2 teacher-dashboard-grid">
            <section>
              <h3>Akun Mahasiswa Terdaftar</h3>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>NIM</th><th>Nama</th><th>IPK</th><th>Peminatan</th><th>Status KHS</th></tr></thead>
                  <tbody>
                    {mentees.map((student) => (
                      <tr key={student.nim}>
                        <td>{student.nim}</td>
                        <td>{student.full_name}</td>
                        <td>{student.ipk ?? '—'}</td>
                        <td>{canonicalizeInterests(student.interests || '').replaceAll(',', ', ') || 'Belum dipilih'}</td>
                        <td>{student.khs_confirmed ? 'Terkonfirmasi' : 'Belum ada KHS'}</td>
                      </tr>
                    ))}
                    {mentees.length === 0 && (
                      <tr><td colSpan="5" className="muted">Belum ada akun mahasiswa terdaftar.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
            <section className="interest-chart-card">
              <div className="interest-chart-heading">
                <div>
                  <h3>Sebaran Peminatan</h3>
                  <p className="muted">Peminatan mahasiswa terdaftar</p>
                </div>
                <PieChart size={22} aria-hidden="true" />
              </div>
              <div className="interest-chart-summary">
                <div><span>Total mahasiswa</span><strong>{mentees.length}</strong></div>
                <div><span>Peminatan terbanyak</span><strong>{mostPopularInterest?.count ? mostPopularInterest.name : 'Belum ada'}</strong></div>
              </div>
              <div className="interest-bars">
                {interestDistribution.map((interest, index) => {
                  const percentage = mentees.length ? Math.round((interest.count / mentees.length) * 100) : 0;
                  return (
                    <div className="interest-bar-item" key={interest.name}>
                      <div className="interest-bar-label">
                        <span><i className={`interest-dot interest-dot-${index}`} />{interest.name}</span>
                        <strong>{interest.count} <small>({percentage}%)</small></strong>
                      </div>
                      <div className="interest-bar-track">
                        <span className={`interest-bar-fill interest-bar-fill-${index}`} style={{ width: `${percentage}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          </div>
        </div>
      );
    }

    if (view === 'bimbingan' && user.role === 'dosen') {
      return (
        <div className="card">
          <h2>Bimbingan Mahasiswa</h2>
          <p className="muted">Validasi rekomendasi, pantau rencana studi, berikan catatan, dan setujui atau minta revisi.</p>
          <div className="stat-grid">
            <div className="stat"><small>Menunggu review</small><strong>{pendingPlans.length}</strong></div>
            <div className="stat"><small>Disetujui</small><strong>{studyPlans.filter((plan) => plan.status === 'approved').length}</strong></div>
            <div className="stat"><small>Perlu revisi</small><strong>{studyPlans.filter((plan) => plan.status === 'revision_requested').length}</strong></div>
            <div className="stat"><small>Total mahasiswa</small><strong>{mentees.length}</strong></div>
          </div>
          <section className="history-document">
            <h3>Pengajuan KPRS</h3>
            <p className="muted">Perubahan KRS mahasiswa bimbingan yang menunggu keputusan.</p>
            {menteeKprsRequests.length === 0 ? <p className="muted">Belum ada pengajuan KPRS.</p> : menteeKprsRequests.map((request) => (
              <article className="history-document" key={request.id}>
                <div className="preview-header">
                  <div>
                    <h4>{request.student_name} · {request.student_nim}</h4>
                    <p className="muted">KRS #{request.study_plan_id} · {request.reason}</p>
                  </div>
                  <span className="status-pill">{request.status}</span>
                </div>
                <div className="table-wrap">
                  <table className="table">
                    <thead><tr><th>Sebelum</th><th>Sesudah</th></tr></thead>
                    <tbody><tr>
                      <td>{request.before.map((course) => `${course.code} (${course.sks} SKS)${course.class_name ? ` · Kelas ${course.class_name} · ${course.day} ${course.start_time}-${course.end_time} · ${course.room}` : ''}`).join('; ')}</td>
                      <td>{request.after.map((course) => `${course.code} (${course.sks} SKS)${course.class_name ? ` · Kelas ${course.class_name} · ${course.day} ${course.start_time}-${course.end_time} · ${course.room}` : ''}`).join('; ')}</td>
                    </tr></tbody>
                  </table>
                </div>
                {request.status === 'pending' && (
                  <>
                    <label className="course-edit-field">
                      Catatan keputusan
                      <textarea rows="3" maxLength="2000" value={kprsReviewNotes[request.id] ?? ''} onChange={(event) => setKprsReviewNotes((previous) => ({ ...previous, [request.id]: event.target.value }))} />
                    </label>
                    <div className="preview-actions">
                      <button className="btn primary" type="button" disabled={studyPlanBusy} onClick={() => reviewKprs(request.id, 'approved')}>Setujui</button>
                      <button className="btn outline" type="button" disabled={studyPlanBusy} onClick={() => reviewKprs(request.id, 'revision_requested')}>Minta revisi</button>
                      <button className="btn outline" type="button" disabled={studyPlanBusy} onClick={() => reviewKprs(request.id, 'rejected')}>Tolak</button>
                    </div>
                  </>
                )}
                {request.reviewer_note && <p className="muted">Catatan: {request.reviewer_note}</p>}
              </article>
            ))}
          </section>
          {studyPlans.length > 0 ? studyPlans.map((plan) => (
            <section className="history-document" key={plan.id}>
              <div className="preview-header">
                <div>
                  <h3>{plan.student_name} · {plan.student_nim}</h3>
                  <p className="muted">Semester {plan.semester} · IPK {plan.student_ipk ?? '—'} · Peminatan {canonicalizeInterests(plan.student_interests || '').replaceAll(',', ', ') || 'belum dipilih'}</p>
                  <p className="muted">Diajukan {new Date(plan.created_at).toLocaleString('id-ID')} · diperbarui {new Date(plan.updated_at).toLocaleString('id-ID')}</p>
                </div>
                <span className={`status-pill ${plan.status === 'approved' ? 'status-disetujui' : plan.status === 'revision_requested' ? 'status-perhatian' : 'status-menunggu'}`}>
                  {plan.status === 'approved' ? 'Disetujui' : plan.status === 'revision_requested' ? 'Perlu revisi' : 'Menunggu review'}
                </span>
              </div>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Mata kuliah</th><th>SKS</th><th>Skor</th><th>Prasyarat</th><th>Alasan rekomendasi</th></tr></thead>
                  <tbody>{plan.courses.map((course) => (
                    <tr key={course.code}>
                      <td>{course.name}<br /><span className="muted">{course.code} · {course.category}</span>{course.class_name && <small className="draft-class-meta"><span><CalendarDays size={13} /> {course.class_name}</span><span><Clock3 size={13} /> {course.day} {course.start_time}-{course.end_time}</span><span><MapPin size={13} /> {course.room}</span></small>}</td>
                      <td>{course.sks}</td>
                      <td>{course.score}%</td>
                      <td>{course.prerequisite_text || '—'}</td>
                      <td>{(course.reasons || []).join('; ')}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              <label className="course-edit-field" style={{ marginTop: 14 }}>
                Alasan revisi / arahan dosen PA
                <textarea
                  rows="3"
                  minLength="10"
                  maxLength="2000"
                  placeholder="Jelaskan alasan akademik revisi (minimal 10 karakter)"
                  value={reviewNotes[plan.id] ?? plan.advisor_note ?? ''}
                  onChange={(event) => setReviewNotes((previousNotes) => ({
                    ...previousNotes,
                    [plan.id]: event.target.value,
                  }))}
                />
                <small className="muted">Wajib diisi minimal 10 karakter ketika meminta revisi. Catatan ini akan diteruskan kepada mahasiswa.</small>
              </label>
              {plan.status !== 'approved' && (
                <fieldset className="course-edit-field" style={{ marginTop: 10 }}>
                  <legend>Mata kuliah yang perlu direvisi</legend>
                  <p className="muted">Pilih mata kuliah yang ditolak/diminta untuk diganti. Mata kuliah wajib tidak dapat ditolak.</p>
                  <div className="interest-options">
                    {plan.courses.filter((course) => !isMandatoryCourse(course)).map((course) => {
                      const selected = reviewRejectedCourses[plan.id] ?? [];
                      return (
                        <label key={course.code} className="interest-option">
                          <input
                            type="checkbox"
                            checked={selected.includes(course.code)}
                            onChange={(event) => setReviewRejectedCourses((previous) => ({
                              ...previous,
                              [plan.id]: event.target.checked
                                ? [...selected, course.code]
                                : selected.filter((code) => code !== course.code),
                            }))}
                          />
                          <span>{course.name} ({course.code})</span>
                        </label>
                      );
                    })}
                  </div>
                </fieldset>
              )}
              {plan.status !== 'approved' && (
                <div className="preview-actions">
                  <button
                    className="btn primary"
                    type="button"
                    disabled={studyPlanBusy}
                    onClick={() => reviewStudyPlan(plan.id, 'approved')}
                  >
                    Setujui rencana studi
                  </button>
                  <button
                    className="btn outline"
                    type="button"
                    disabled={studyPlanBusy || (reviewNotes[plan.id] ?? plan.advisor_note ?? '').trim().length < 10 || !(reviewRejectedCourses[plan.id] ?? []).length}
                    onClick={() => reviewStudyPlan(plan.id, 'revision_requested')}
                  >
                    Kirim catatan revisi
                  </button>
                </div>
              )}
            </section>
          )) : <p className="muted">Belum ada rencana studi yang diajukan mahasiswa.</p>}
        </div>
      );
    }

    if (view === 'dashboard') {
      return (
        <div className="card">
          <h2>Halo, {dashboardProfile.full_name} | NIM {dashboardProfile.nim}</h2>
          {!profile?.khs_confirmed && (
            <div className="khs-prompt">
              <button className="btn primary" type="button" onClick={() => setView('khs')}>Unggah KHS lengkap untuk memulai</button>
            </div>
          )}
          <p className="muted">{profile?.program_study || 'Program studi belum diidentifikasi dari KHS'}</p>
          <p className="muted">
            {profile?.advisor
              ? `Dosen PA: ${profile.advisor.full_name}${profile.advisor.email ? ` · ${profile.advisor.email}` : ''}`
              : 'Anda belum mendapatkan Dosen Pembimbing Akademik. Silakan hubungi Admin Akademik untuk informasi lebih lanjut.'}
          </p>
          <div className="stat-grid">
            <div className="stat"><small>Semester terakhir</small><strong>{profile?.semester ?? '—'}</strong></div>
            <div className="stat"><small>IPK</small><strong>{profile?.ipk ?? '—'}</strong></div>
            <div className="stat"><small>SKS lulus</small><strong>{profile?.total_sks ?? 0}</strong></div>
            <div className="stat"><small>SKS tersisa</small><strong>{profile?.sks_sisa ?? '—'}</strong></div>
          </div>
          {profile?.khs_confirmed && (
            <p className="muted">{profile.passed_courses} mata kuliah lulus · {profile.failed_courses} mata kuliah belum lulus · Minat: {profile.interests || 'belum dipilih'}</p>
          )}
          {latestStudyPlan && (
            <div className="study-plan-summary">
              <span className={`status-pill ${latestStudyPlan.status === 'approved' ? 'status-disetujui' : latestStudyPlan.status === 'revision_requested' ? 'status-perhatian' : 'status-menunggu'}`}>
                {latestStudyPlan.status === 'pending' ? 'Menunggu review' : latestStudyPlan.status === 'approved' ? 'Disetujui dosen PA' : 'Perlu revisi'}
              </span>
              <span>Rencana studi semester {latestStudyPlan.semester}</span>
              {latestStudyPlan.advisor_note && <p><strong>Catatan dosen PA:</strong> {latestStudyPlan.advisor_note}</p>}
              {latestStudyPlan.status === 'revision_requested' && (
                <button type="button" className="btn primary" onClick={() => setView('rekomendasi')}>
                  Perbaiki draft dan ajukan ulang
                </button>
              )}
              {latestStudyPlan.advisor_feedback?.length > 0 && (
                <div className="history-document" style={{ marginTop: 10 }}>
                  <strong>{latestStudyPlan.status === 'revision_requested' ? 'Mata kuliah yang perlu diperbaiki' : 'Riwayat feedback dosen PA (digunakan model ML)'}</strong>
                  {latestStudyPlan.advisor_feedback.map((feedback, index) => (
                    <p key={`${feedback.course_code}-${index}`}>
                      <strong>{feedback.course_code}</strong> — {feedback.reason}
                    </p>
                  ))}
                  <p className="muted">Saran alternatif sudah diperbarui dengan mempertimbangkan catatan Dosen PA sebagai sinyal negatif pada rekomendasi berikutnya.</p>
                </div>
              )}
              {latestStudyPlan.status === 'approved' && (
                <button
                  type="button"
                  className="btn primary"
                  disabled={officialKrsPreviewBusy}
                  onClick={() => previewOfficialKrs(latestStudyPlan.id).catch((error) => pushToast(error.message, 'error'))}
                >
                  {officialKrsPreviewBusy ? 'Menyiapkan preview...' : 'Preview KRS'}
                </button>
              )}
            </div>
          )}
          {approvedStudyPlan && (
            <section className="study-plan-summary">
              <h3>Pengajuan Perubahan KRS (KPRS)</h3>
              <div className="course-edit-grid kprs-edit-grid">
                <label className="course-edit-field"><span className="muted">KRS approved</span><select value={kprsDraft.planId} onChange={(event) => {
                  const nextId = event.target.value;
                  const selectedPlan = studyPlans.find((plan) => plan.id === Number(nextId));
                  setKprsDraft((previous) => ({ ...previous, planId: nextId }));
                  setKprsClassSelections(Object.fromEntries((selectedPlan?.courses || []).filter((course) => course.class_id).map((course) => [course.code, Number(course.class_id)])));
                }}><option value="">Pilih</option><option value={approvedStudyPlan.id}>KRS semester {approvedStudyPlan.semester}</option></select></label>
                <label className="course-edit-field"><span className="muted">Kode mata kuliah baru (pisahkan koma)</span><input value={kprsDraft.courses} onChange={(event) => setKprsDraft((previous) => ({ ...previous, courses: event.target.value }))} /></label>
                <label className="course-edit-field"><span className="muted">Alasan perubahan</span><textarea rows={3} value={kprsDraft.reason} onChange={(event) => setKprsDraft((previous) => ({ ...previous, reason: event.target.value }))} /></label>
              </div>
              <div className="kprs-class-options">
                {kprsDraft.courses.split(',').map((rawCode) => rawCode.trim().toUpperCase()).filter(Boolean).map((code) => {
                  const options = studentClasses.filter((section) => section.course_code === code);
                  if (!options.length) return null;
                  const currentPlan = studyPlans.find((plan) => plan.id === Number(kprsDraft.planId));
                  const previousClassId = currentPlan?.courses?.find((course) => course.code === code)?.class_id;
                  const selectedClassId = kprsClassSelections[code] ?? previousClassId ?? '';
                  return (
                    <label className="course-edit-field" key={code}>
                      <span className="muted">Kelas paralel {code}</span>
                      <select value={selectedClassId} onChange={(event) => setKprsClassSelections((previous) => ({ ...previous, [code]: event.target.value }))}>
                        <option value="">Pilih kelas untuk {code}</option>
                        {options.map((section) => (
                          <option key={section.class_id} value={section.class_id} disabled={!section.is_open || (section.remaining_seats <= 0 && Number(selectedClassId) !== Number(section.class_id))}>
                            {section.class_name} · {section.day} {section.start_time}-{section.end_time} · {section.room} · {section.remaining_seats} kursi tersisa
                          </option>
                        ))}
                      </select>
                    </label>
                  );
                })}
              </div>
              <div className="kprs-submit-row">
                {!studentClassesLoaded && <small className="muted">Memuat jadwal kelas semester KRS...</small>}
                <button className="btn primary" type="button" onClick={submitKprs} disabled={!studentClassesLoaded}>Ajukan KPRS</button>
              </div>
              {kprsRequests.map((request) => (
                <p key={request.id}>
                  KPRS #{request.id}: <strong>{request.status}</strong>
                  {request.reviewer_note ? ` - ${request.reviewer_note}` : ''}
                  {request.status === 'pending' && (
                    <button className="btn outline" type="button" onClick={() => cancelKprs(request.id)}>
                      Batalkan pengajuan
                    </button>
                  )}
                </p>
              ))}
            </section>
          )}
          <h3>Rekomendasi Semester {recommendationResult.target_semester ?? 'Berikutnya'}</h3>
          {optionalRecommendations.length ? (
            <div className="recommendation-list">
              {optionalRecommendations.slice(0, 5).map((item) => (
                <div key={item.code} className="rec-item">
                  <strong>{item.name}</strong>
                  <div className="bar" aria-label={`Skor rekomendasi ${item.score}%`}><span style={{ width: `${item.score}%` }} /></div>
                  <strong>{item.score}%</strong>
                </div>
              ))}
            </div>
          ) : <p className="muted">Belum ada rekomendasi mata kuliah pilihan yang lolos aturan akademik.</p>}
          <button type="button" className="btn outline" onClick={() => setView('rekomendasi')}>Lihat rekomendasi dan alasannya</button>
          <div style={{ marginTop: 18 }}>
            <strong>Draft KRS:</strong> {draftCourses.length} mata kuliah • {totalDraftSks} / {kuotaSks} SKS
          </div>
        </div>
      );
    }

    if (view === 'rekomendasi') {
      return (
        <div className="card">
          <h2>Rekomendasi Mata Kuliah Semester {recommendationResult.target_semester ?? 'Berikutnya'}</h2>
          {recommendationResult.status !== 'ready' ? (
            <p className="muted">Unggah dan konfirmasi KHS untuk melihat rekomendasi mata kuliah.</p>
          ) : (
            <>
              <div className="profile-summary">
                <strong>{profile?.full_name}</strong><span>NIM {profile?.nim}</span>
                <span>{profile?.program_study || 'Program studi belum diisi'}</span>
                <span>Semester {profile?.current_semester} → {profile?.target_semester}</span>
                <span>IPK {profile?.ipk ?? '—'} · {profile?.total_sks} SKS · Minat: {profile?.interests || 'Belum diisi'}</span>
              </div>
              {recommendationResult.model && (
                <section className="ml-engine-panel" aria-label="Status mesin rekomendasi machine learning">
                  <div className="ml-engine-header">
                    <div className="ml-engine-icon"><BrainCircuit size={26} /></div>
                    <div className="ml-engine-title">
                      <span className="ml-brand-badge">MESIN REKOMENDASI MACHINE LEARNING</span>
                      <h3>Model CourseRecom sedang menganalisis pilihan studimu</h3>
                      <p>{recommendationResult.model.method}</p>
                    </div>
                    <span className="ml-engine-live"><i /> INFERENCE AKTIF</span>
                  </div>
                  <div className="ml-engine-mode">
                    <strong>{recommendationResult.model.inference_mode_label || 'Hybrid recommender'}</strong>
                    <span>
                      {recommendationResult.model.inference_mode === 'collaborative_plus_content'
                        ? 'Pola mahasiswa serupa tersedia dan digabungkan dengan analisis konten mata kuliah.'
                        : 'Data pembanding belum cukup; sistem memakai content-based fallback dari data akademik dan katalog.'}
                    </span>
                  </div>                  <div className="ml-engine-metrics">
                    <div><span>Mahasiswa serupa</span><strong>{recommendationResult.model.peer_count ?? 0}</strong></div>
                    <div><span>Riwayat KHS tersedia</span><strong>{recommendationResult.model.available_history_records ?? 0}</strong></div>
                    <div><span>Mahasiswa dalam dataset</span><strong>{recommendationResult.model.available_history_students ?? 0}</strong></div>
                    <div><span>Versi evaluasi</span><strong>{recommendationResult.model.version || 'Belum tersimpan'}</strong></div>
                  </div>
                  <div className="ml-engine-pipeline" aria-label="Alur model rekomendasi">
                    <span>Riwayat KHS</span><b>→</b><span>Nearest neighbors</span><b>→</b><span>Content scoring</span><b>→</b><span>Validasi kurikulum</span>
                  </div>
                  <div className="ml-evaluation">
                    <div>
                      <span>Precision@5</span>
                      <strong>{recommendationResult.model.metrics?.precision_at_5 == null
                        ? 'Belum dievaluasi'
                        : (Number(recommendationResult.model.metrics.precision_at_5) * 100).toFixed(1) + '%'}</strong>
                    </div>
                    <div>
                      <span>Recall@5</span>
                      <strong>{recommendationResult.model.metrics?.recall_at_5 == null
                        ? 'Belum dievaluasi'
                        : (Number(recommendationResult.model.metrics.recall_at_5) * 100).toFixed(1) + '%'}</strong>
                    </div>
                    <div>
                      <span>Sampel evaluasi</span>
                      <strong>{recommendationResult.model.metrics?.evaluation_samples ?? '—'}</strong>
                    </div>
                    <div>
                      <span>Status training/evaluasi</span>
                      <strong>{recommendationResult.model.training_status === 'evaluated'
                        ? 'Dievaluasi'
                        : recommendationResult.model.training_status === 'insufficient_history'
                          ? 'Data belum cukup'
                          : 'Belum ada versi tersimpan'}</strong>
                    </div>
                  </div>
                  <p className="ml-engine-footnote">
                    {recommendationResult.model.trained_at
                      ? 'Evaluasi terakhir: ' + new Date(recommendationResult.model.trained_at).toLocaleString('id-ID') + '. '
                      : 'Belum ada catatan versi pelatihan/evaluasi yang tersimpan. '}
                    Mesin rekomendasi tetap menghitung kecocokan berdasarkan data yang tersedia. Precision@5 dan Recall@5 hanya ditampilkan jika hasil evaluasinya tersedia.
                  </p>
                </section>
              )}
              {mandatoryRecommendations.length > 0 && (
                <section className="mandatory-recommendations" aria-label="Mata kuliah wajib otomatis">
                  <h3>Mata kuliah wajib (otomatis ditambahkan)</h3>
                  <p className="muted">Mata kuliah berikut otomatis dimasukkan ke Draft KRS oleh sistem. Kamu tidak perlu memilihnya secara manual.</p>
                  <div className="recommendation-grid recommendation-grid-mandatory">
                    {mandatoryRecommendations.map((item) => (
                    <article className="recommendation-card recommendation-card-mandatory" key={item.code} aria-disabled="true">
                      <div className="recommendation-heading">
                        <div>
                          <h4>{item.name}</h4>
                          <span className="muted">{item.code} · {item.sks} SKS · Semester {item.semester} · {item.category}</span>
                        </div>
                        <span className="mandatory-status">WAJIB · OTOMATIS</span>
                      </div>
                      <p className="mandatory-course-note">Mata kuliah wajib sudah ditambahkan ke Draft KRS dan tidak dapat dipilih atau dihapus secara manual.</p>
                      <button className="btn mandatory-disabled" type="button" disabled>Otomatis masuk Draft KRS</button>
                    </article>
                    ))}
                  </div>
                </section>
              )}
              <h3>Rekomendasi mata kuliah pilihan</h3>
              {optionalRecommendations.length ? (
                <div className="recommendation-grid">
                  {optionalRecommendations.map((item) => (
                <article className="recommendation-card" key={item.code}>
                  <div className="recommendation-heading">
                    <div>
                      <h4>{item.name}</h4>
                      <span className="muted">{item.code} · {item.sks} SKS · Semester {item.semester} · {item.category}</span>
                    </div>
                    <strong className="score-badge">{item.score}% kecocokan</strong>
                  </div>
                  <p className="ml-course-explanation">
                    <Sparkles size={17} aria-hidden="true" />
                    <span><strong>Dipilih oleh model Machine Learning CourseRecom.</strong> {item.recommendation_explanation || 'Skor menggabungkan riwayat akademik, kecocokan minat yang tersedia, prasyarat, dan kurikulum.'} Skor ini menunjukkan kecocokan rekomendasi, bukan probabilitas kelulusan.</span>
                  </p>
                  {item.description && <p>{item.description}</p>}
                  {item.prerequisite_text && (
                    <p><strong>Prasyarat:</strong><br />{item.prerequisite_text.split('\n').map((line, index) => (
                      <span key={`${item.code}-prerequisite-${index}`}>{line}<br /></span>
                    ))}</p>
                  )}
                  <div className="factor-grid">
                    {Object.entries(item.factors || {}).map(([factor, score]) => (
                      <div className="factor" key={factor} title={item.factor_details?.[factor] || RECOMMENDATION_FACTOR_HINTS[factor] || ''}>
                        <span>{RECOMMENDATION_FACTOR_LABELS[factor] || factor.replaceAll('_', ' ')}</span>
                        <strong>{score == null ? 'Belum cukup data' : `${score}%`}</strong>
                        <small>{item.factor_details?.[factor] || RECOMMENDATION_FACTOR_HINTS[factor] || ''}</small>
                        {Number(item.factor_weights?.[factor]) > 0 && (
                          <em>Bobot efektif {item.factor_weights[factor]}%</em>
                        )}
                      </div>
                    ))}
                  </div>
                  <p className="score-coverage-note">
                    Skor akhir memakai {item.available_factor_count ?? 5} dari 5 aspek terukur
                    (cakupan bobot data {item.score_coverage ?? 100}%).
                    Aspek yang belum memiliki data tidak dianggap bernilai 0; bobot aspek lain disesuaikan secara proporsional.
                  </p>
                  <ul className="reason-list">{item.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
                  <button
                    className="btn primary"
                    type="button"
                    disabled={Boolean(approvedStudyPlan) || draftCourses.some((course) => course.code === item.code)}
                    onClick={() => addToDraft(item)}
                  >
                    {approvedStudyPlan
                      ? 'KRS sudah disetujui'
                      : draftCourses.some((course) => course.code === item.code) ? 'Sudah di draft' : 'Tambah ke Draft KRS'}
                  </button>
                </article>
                  ))}
                </div>
              ) : <p className="muted">Belum ada mata kuliah pilihan yang lolos aturan akademik untuk semester target ini.</p>}
              {recommendationResult.semester_antara?.length > 0 && (
                <section className="rejected-section">
                  <h3>Wajib diulang di Semester Antara</h3>
                  <p className="muted">Mata kuliah dengan nilai di bawah D wajib diulang pada Semester Antara, yang dijadwalkan saat libur setelah semester genap.</p>
                  {recommendationResult.semester_antara.map((item) => (
                    <article className="rejected-card" key={item.code}>
                      <strong>{item.name} ({item.code})</strong>
                      <span>{item.sks} SKS · Nilai terakhir {item.grade} · Terakhir diambil semester {item.last_attempt_semester}</span>
                    </article>
                  ))}
                </section>
              )}
            </>
          )}
          {rejectedRecommendations.length > 0 && (
            <section className="rejected-section">
              <h3>Tidak dapat direkomendasikan</h3>
              {rejectedRecommendations.map((item) => (
                <article className="rejected-card" key={item.code}>
                  <strong>{item.name} ({item.code})</strong>
                  <span>{item.reason_block}</span>
                </article>
              ))}
            </section>
          )}
          <div className="draft-summary">
            <strong>Draft KRS:</strong> {draftCourses.length} mata kuliah · {totalDraftSks} / {kuotaSks} SKS
            {approvedStudyPlan && <span className="draft-lock-status"><CheckCircle2 size={16} /> KRS disetujui dan terkunci</span>}
          </div>
          <p className="muted">Batas SKS semester ini mengikuti IPK: 24 SKS untuk IPK ≥ 3,35; 22 SKS untuk IPK ≥ 3,00 dan &lt; 3,35; dan 20 SKS untuk IPK di bawah 3,00. Jika IPK belum tersedia, batasnya 20 SKS.</p>
          <div style={{ marginTop: 20 }}>
            <h4>Draft KRS saat ini</h4>
            {draftCourses.length === 0 ? (
              <p className="muted">Belum ada mata kuliah yang dipilih.</p>
            ) : (
              <ul className="draft-course-list">
                {draftCourses.map((course) => {
                  const mandatory = isMandatoryCourse(course);
                  return (
                    <li key={course.code} className={mandatory ? 'draft-course-item draft-course-item-mandatory' : 'draft-course-item'}>
                      <div className="draft-course-main">
                        <strong>{course.code} — {course.name} ({course.sks} SKS)</strong>
                        {mandatory && <span className="mandatory-status">WAJIB · OTOMATIS</span>}
                        {(() => {
                          const sections = studentClasses.filter((section) => section.course_code === course.code);
                          if (!sections.length) {
                            return <small className="muted">Kelas paralel belum dipublikasikan; jadwal mengikuti katalog prodi.</small>;
                          }
                          return (
                            <label className="draft-class-select">
                              <span><CalendarDays size={15} /> Pilih kelas paralel</span>
                              <select value={course.class_id ?? ''} disabled={Boolean(approvedStudyPlan) || !studentClassesLoaded} onChange={(event) => updateDraftClass(course.code, event.target.value)}>
                                <option value="">Pilih kelas yang tersedia</option>
                                {sections.map((section) => (
                                  <option key={section.class_id} value={section.class_id} disabled={!section.is_open || section.remaining_seats <= 0}>
                                    {section.class_name} · {section.lecturer_name} · {section.day} {section.start_time}-{section.end_time} · {section.room} · {section.remaining_seats} kursi
                                  </option>
                                ))}
                              </select>
                              {course.class_id && (
                                <small className="draft-class-meta">
                                  <span><Clock3 size={13} /> {course.day} {course.start_time}-{course.end_time}</span>
                                  <span><MapPin size={13} /> {course.room}</span>
                                  <span><Users size={13} /> {course.lecturer_name}</span>
                                </small>
                              )}
                            </label>
                          );
                        })()}
                      </div>
                      {!mandatory && <button type="button" className="btn outline" disabled={Boolean(approvedStudyPlan)} onClick={() => removeFromDraft(course.code)}>Hapus</button>}
                    </li>
                  );
                })}
              </ul>
            )}
            {draftCourses.length > 0 && (
              <div className="preview-actions">
                <button type="button" className="btn outline" disabled={Boolean(approvedStudyPlan)} onClick={clearDraft}>Hapus mata kuliah pilihan</button>
                <button
                  type="button"
                  className="btn primary"
                  disabled={studyPlanBusy || Boolean(approvedStudyPlan) || pendingPlans.some((plan) => plan.status === 'pending')}
                  onClick={submitStudyPlan}
                >
                  {studyPlanBusy ? 'Mengajukan...' : 'Ajukan ke Dosen PA'}
                </button>
              </div>
            )}
            {pendingPlans.some((plan) => plan.status === 'pending') && (
              <p className="muted">Rencana studi sedang menunggu review dosen PA. Pengajuan berikutnya tersedia setelah direview.</p>
            )}
          </div>
        </div>
      );
    }

    if (view === 'riwayat') {
      return (
        <div className="card">
          <h2>Riwayat KHS</h2>
          {academicHistory.filter((doc) => doc.status === 'confirmed').length === 0
            ? <p className="muted">Belum ada KHS yang dikonfirmasi.</p>
            : academicHistory.filter((doc) => doc.status === 'confirmed').map((doc) => {
              const editing = historyEditId === doc.id && historyEditDraft;
              return (
                <section className="history-document" key={doc.id}>
                  <div className="preview-header"><div>
                    <h3>{doc.filename} · {doc.metadata.current_semester} semester</h3>
                    <p className="muted">Nilai angka yang ditandai perkiraan bukan nilai asli pada KHS. Silakan edit jika memiliki nilai resmi.</p>
                  </div>
                  {!editing && <button className="btn outline" type="button" onClick={() => beginHistoryEdit(doc)}>Edit nilai & IPK</button>}</div>
                  <label>IPK {editing ? <input type="number" min="0" max="4" step="0.01" value={historyEditDraft.ipk} readOnly={doc.semesters.length > 0 && doc.semesters.every((semester) => historyEditDraft.ip_semesters[String(semester.semester)] !== '' && Number.isFinite(Number(historyEditDraft.ip_semesters[String(semester.semester)])) && Number(historyEditDraft.ip_semesters[String(semester.semester)]) >= 0 && Number(historyEditDraft.ip_semesters[String(semester.semester)]) <= 4)} title="IPK dihitung otomatis dari rata-rata IPS seluruh semester." onChange={(event) => setHistoryEditDraft((draft) => ({ ...draft, ipk: event.target.value }))} /> : <strong>{doc.metadata?.ipk ?? '—'}</strong>}</label>
                  {editing && <small className="muted">IPK dihitung otomatis dari rata-rata IPS. Perbarui IPS semester untuk memperbarui IPK.</small>}
                  {doc.semesters.map((semester) => (
                    <div key={semester.semester} className="history-semester">
                      <h4>Semester {semester.semester} · {semester.courses.length} mata kuliah</h4>
                      <div className="table-wrap"><table className="table">
                        <thead><tr><th>Kode</th><th>Mata kuliah</th><th>SKS</th><th>Nilai angka</th><th>Grade</th><th>Keterangan</th></tr></thead>
                        <tbody>{semester.courses.map((course, index) => {
                          const draftIndex = historyEditDraft?.courses.findIndex((item) => item.code === course.code && Number(item.semester) === Number(semester.semester));
                          const draftCourse = editing && draftIndex >= 0 ? historyEditDraft.courses[draftIndex] : course;
                          return <tr key={`${course.code}-${index}`}>
                            <td>{course.code}</td><td>{course.name}</td><td>{course.sks}</td>
                            <td>{editing ? <input aria-label={`Edit nilai angka ${course.code}`} type="number" min="0" max="100" step="0.01" value={draftCourse.numeric_grade ?? ''} onChange={(event) => setHistoryEditDraft((draft) => ({ ...draft, courses: draft.courses.map((item, idx) => idx === draftIndex ? { ...item, numeric_grade: event.target.value } : item) }))} /> : (course.numeric_grade ?? '—')}</td>
                            <td>{course.grade}</td><td>{course.numeric_grade_estimated ? 'Perkiraan, bukan nilai asli' : 'Nilai tercantum / telah dikoreksi'}</td>
                          </tr>;
                        })}</tbody>
                      </table></div>
                      <div className="semester-summary-item history-ips-result">
                        <strong>IPS Semester {semester.semester}</strong>
                        {editing
                          ? <input aria-label={`Edit IPS semester ${semester.semester}`} type="number" min="0" max="4" step="0.01" value={historyEditDraft.ip_semesters[String(semester.semester)] ?? ''} onChange={(event) => updateHistoryIps(doc, semester.semester, event.target.value)} />
                          : <span>{semester.ip_semester ?? '—'}</span>}
                      </div>
                    </div>
                  ))}
                  {editing && <div className="preview-actions"><button className="btn primary" type="button" disabled={historyEditBusy} onClick={() => saveHistoryEdit(doc)}>{historyEditBusy ? 'Menyimpan...' : 'Simpan perubahan'}</button><button className="btn outline" type="button" disabled={historyEditBusy} onClick={() => { setHistoryEditId(null); setHistoryEditDraft(null); }}>Batal</button></div>}
                </section>
              );
            })}
          <button type="button" className="btn primary" onClick={() => setView('khs')}>Unggah KHS terbaru</button>
        </div>
      );
    }

    if (view === 'minat') {
      return (
        <div className="card">
          <h3>Minat & Profil</h3>
          <p className="muted">Pilih satu bidang minat sesuai program studi. Pilihan ini memengaruhi skor kecocokan mata kuliah pada rekomendasi.</p>
          <p className="muted">{programInterestCatalog[canonicalProgramName(user?.program_study)]?.kind || 'Bidang minat'} · {programInterestCatalog[canonicalProgramName(user?.program_study)]?.note || 'Pilihan bidang minat mahasiswa.'}</p>
          <div className="interest-options">{(programInterestCatalog[canonicalProgramName(user?.program_study)]?.options || INTEREST_OPTIONS).map((interest) => {
            const selected = canonicalizeInterests(profileDraft) === interest;
            return (
              <label className="interest-option" key={interest}>
                <input
                  type="radio"
                  name="student-interest"
                  checked={selected}
                  onChange={() => setProfileDraft(interest)}
                />
                {interest}
              </label>
            );
          })}</div>
          {!canonicalizeInterests(profileDraft) && (
            <p className="muted" role="status">Pilih minimal satu peminatan sebelum menyimpan.</p>
          )}
          <button className="btn primary" type="button" onClick={saveProfile} disabled={!canonicalizeInterests(profileDraft)}>Simpan Minat</button>
        </div>
      );
    }

    if (view === 'profil') {
      return (
        <div className="card">
          <h3>Edit Profil</h3>
          <div className="form-grid">
            <label><span className="muted">Nama lengkap</span><input value={accountProfileDraft.full_name} onChange={(event) => setAccountProfileDraft((draft) => ({ ...draft, full_name: event.target.value }))} /></label>
            <label><span className="muted">Username</span><input value={accountProfileDraft.username} onChange={(event) => setAccountProfileDraft((draft) => ({ ...draft, username: event.target.value }))} /></label>
            <label><span className="muted">Email</span><input type="email" value={accountProfileDraft.email} onChange={(event) => setAccountProfileDraft((draft) => ({ ...draft, email: event.target.value }))} /></label>
            <label><span className="muted">Nomor telepon</span><input type="tel" maxLength="20" inputMode="tel" placeholder="+628123456789" value={accountProfileDraft.phone_number} onChange={(event) => setAccountProfileDraft((draft) => ({ ...draft, phone_number: event.target.value }))} /></label>
            {(user?.role === 'mahasiswa' || user?.role === 'dosen') && <label><span className="muted">Program studi</span><input value={accountProfileDraft.program_study} onChange={(event) => setAccountProfileDraft((draft) => ({ ...draft, program_study: event.target.value }))} /></label>}
            {user?.role === 'mahasiswa' && <label><span className="muted">Angkatan</span><input value={accountProfileDraft.angkatan} onChange={(event) => setAccountProfileDraft((draft) => ({ ...draft, angkatan: event.target.value }))} /></label>}
          </div>
          <h4>Ubah password</h4>
          <div className="form-grid">
            <label><span className="muted">Password saat ini</span><input type="password" autoComplete="current-password" value={passwordDraft.current_password} onChange={(event) => setPasswordDraft((draft) => ({ ...draft, current_password: event.target.value }))} /></label>
            <label><span className="muted">Password baru</span><input type="password" autoComplete="new-password" value={passwordDraft.new_password} onChange={(event) => setPasswordDraft((draft) => ({ ...draft, new_password: event.target.value }))} /></label>
            <label><span className="muted">Konfirmasi password baru</span><input type="password" autoComplete="new-password" value={passwordDraft.confirmation} onChange={(event) => setPasswordDraft((draft) => ({ ...draft, confirmation: event.target.value }))} /></label>
          </div>
          <button className="btn primary" type="button" onClick={saveAccountProfile}>Simpan Profil</button>
        </div>
      );
    }

    if (view === 'tentang') {
      return (
        <div className="card">
          <div className="ml-about-hero">
            <span className="ml-brand-badge"><BrainCircuit size={16} /> POWERED BY MACHINE LEARNING</span>
            <h2>CourseRecom — Rekomendasi Mata Kuliah Cerdas</h2>
            <p>CourseRecom menggunakan pendekatan hybrid <strong>weighted nearest-neighbor collaborative filtering</strong> dan <strong>content-based recommendation</strong> untuk membantu mahasiswa menyusun pilihan studi berdasarkan data akademiknya.</p>
          </div>
          <h3>Bagaimana model bekerja?</h3>
          <div className="ml-process-grid">
            <article><span>01</span><strong>Riwayat akademik</strong><p>KHS dikonversi menjadi histori mata kuliah dan nilai yang dapat dibandingkan.</p></article>
            <article><span>02</span><strong>Mahasiswa serupa</strong><p>Sistem membandingkan mata kuliah dan nilai untuk menemukan histori mahasiswa yang paling mirip.</p></article>
            <article><span>03</span><strong>Skor rekomendasi</strong><p>Sinyal collaborative filtering digabungkan dengan minat, nilai prasyarat/IPK, dan kesesuaian kurikulum.</p></article>
            <article><span>04</span><strong>Validasi akademik</strong><p>Hasil diperiksa kembali terhadap prasyarat, mata kuliah yang sudah lulus, dan batas SKS sebelum ditampilkan.</p></article>
          </div>
          <p className="ml-method-note">Jika data mahasiswa pembanding belum mencukupi, sistem menggunakan content-based fallback dan menandai aspek yang belum memiliki bukti. Skor kecocokan bukan probabilitas kelulusan.</p>
          <h3>Manfaat untuk pengguna</h3>
          <ul>
            <li>Mahasiswa menerima rekomendasi yang mempertimbangkan riwayat akademik dan minat.</li>
            <li>Dosen PA dapat melihat dasar rekomendasi untuk membantu proses bimbingan akademik.</li>
            <li>Admin dapat mengelola kurikulum serta menjalankan pelatihan/evaluasi ulang model dari data yang tersedia.</li>
          </ul>
        </div>
      );
    }


    if (view === 'panduan') {
      const searchTerm = guideSearch.trim().toLocaleLowerCase('id-ID');
      const guideRole = user?.role === 'admin'
        ? null
        : user?.role === 'dosen'
          ? 'Dosen PA'
          : 'Mahasiswa';
      const isAdminGuide = user?.role === 'admin';
      const guideHeading = isAdminGuide
        ? 'Panduan lengkap seluruh peran'
        : guideRole === 'Dosen PA'
          ? 'Panduan khusus Dosen PA'
          : 'Panduan khusus Mahasiswa';
      const guideDescription = isAdminGuide
        ? 'Seluruh panduan penggunaan CourseRecom untuk Admin Prodi, Dosen PA, dan Mahasiswa tersedia di halaman ini.'
        : guideRole === 'Dosen PA'
          ? 'Halaman ini hanya menampilkan panduan dan alur kerja Dosen Pembimbing Akademik sesuai hak akses akun Anda.'
          : 'Halaman ini hanya menampilkan panduan dan alur akademik yang dapat digunakan oleh akun Mahasiswa.';
      const guideScope = isAdminGuide
        ? 'Menampilkan seluruh panduan lintas peran'
        : `Menampilkan panduan khusus ${guideRole}`;
      const visibleSections = GUIDE_SECTIONS.filter((section) => (
        (isAdminGuide || section.role === guideRole)
        && (!searchTerm || [section.role, section.title, section.intro, ...section.steps].join(' ').toLocaleLowerCase('id-ID').includes(searchTerm))
      ));
      return (
        <div className="guide-page">
          <section className="guide-hero">
            <div className="guide-hero-content">
              <span className="guide-eyebrow"><HelpCircle size={15} /> PUSAT BANTUAN COURSERECOM</span>
              <h2>{guideHeading}</h2>
              <p>{guideDescription}</p>
              <div className="guide-hero-meta">
                <span><Users size={15} /> {isAdminGuide ? '3 level akun' : guideRole}</span>
                <span><BookOpenCheck size={15} /> {isAdminGuide ? 'Seluruh alur aplikasi' : 'Alur sesuai peran akun'}</span>
                <span><ShieldCheck size={15} /> Hak akses terpisah</span>
              </div>
            </div>
            <div className="guide-hero-art" aria-hidden="true">
              <div className="guide-art-orbit guide-art-orbit-one" />
              <div className="guide-art-orbit guide-art-orbit-two" />
              <div className="guide-art-document"><BookOpenCheck size={52} /><span>USER GUIDE</span><i /><i /><i /></div>
              <div className="guide-art-chip guide-art-chip-one"><CheckCircle2 size={17} /> KRS</div>
              <div className="guide-art-chip guide-art-chip-two"><CalendarDays size={17} /> Jadwal</div>
            </div>
          </section>
          <section className="guide-toolbar">
            <label className="guide-search">
              <Search size={17} />
              <input
                value={guideSearch}
                onChange={(event) => setGuideSearch(event.target.value)}
                placeholder={isAdminGuide ? 'Cari di seluruh panduan, misalnya KRS, KHS, kelas paralel...' : `Cari dalam panduan ${guideRole}, misalnya KRS atau KHS...`}
              />
              {guideSearch && <button type="button" onClick={() => setGuideSearch('')} aria-label="Hapus pencarian">×</button>}
            </label>
          </section>
          <div className="guide-summary-row">            <strong>{visibleSections.length} bagian panduan</strong>
            <span>{guideScope}. Konten dapat dibuka per topik di desktop maupun ponsel.</span>
          </div>
          <div className="guide-section-grid">
            {visibleSections.map((section, index) => (
              <article className="guide-section-card" key={section.title}>
                <div className="guide-section-top">
                  <span className={section.role === 'Mahasiswa' ? 'guide-role-tag student' : section.role === 'Dosen PA' ? 'guide-role-tag lecturer' : section.role === 'Admin Prodi' ? 'guide-role-tag admin' : 'guide-role-tag common'}>{section.role}</span>
                  <span className="guide-index">{String(index + 1).padStart(2, '0')}</span>
                </div>
                <h3>{section.title}</h3>
                <p className="guide-section-intro">{section.intro}</p>
                <details className="guide-details" open={guideSearch.length > 0}>
                  <summary><span>Lihat langkah penggunaan</span><ChevronDown size={17} /></summary>
                  <ol>{section.steps.map((step, stepIndex) => <GuideStep key={stepIndex} index={stepIndex}>{step}</GuideStep>)}</ol>
                </details>
              </article>
            ))}
          </div>
          {visibleSections.length === 0 && (
            <div className="guide-empty">
              <Search size={28} />
              <strong>Panduan tidak ditemukan</strong>
              <span>Tidak ada topik yang cocok dengan kata kunci tersebut pada panduan akun ini.</span>
              <button className="btn outline" type="button" onClick={() => setGuideSearch('')}>Hapus pencarian</button>
            </div>
          )}
          <section className="guide-help-footer">
            <div><strong>Butuh bantuan?</strong><p>{isAdminGuide ? 'Gunakan panduan lintas peran untuk memeriksa alur aplikasi. Untuk kebijakan akademik resmi, koordinasikan dengan pengelola program studi.' : 'Mulai dari petunjuk yang tersedia pada halaman ini. Untuk akun, penetapan Dosen PA, periode akademik, dan kelas paralel, hubungi Admin Prodi.'}</p></div>
            <button className="btn primary" type="button" onClick={() => setView('dashboard')}>Kembali ke Dashboard</button>
          </section>
        </div>
      );
    }

    if (view === 'akun-dosen' && user.role === 'admin') {
      return (
        <div className="card">
          <div className="class-section-heading">
            <div>
              <h2>Akun Dosen PA</h2>
              <p className="muted">Kelola akun login dosen dan cocokkan dengan direktori profil dosen FTII.</p>
            </div>
            <div className="export-actions">
              <button className="btn outline" type="button" disabled={exportBusy === 'lecturers'} onClick={() => downloadAdminExport('lecturers')}>
                {exportBusy === 'lecturers' ? 'Mengekspor...' : 'Ekspor Data Dosen'}
              </button>
              <button className="btn primary" type="button" onClick={() => setLecturerFormVisible((visible) => !visible)}>
                {lecturerFormVisible ? 'Batal' : 'Daftarkan akun dosen PA'}
              </button>
            </div>
          </div>
          {lecturerFormVisible && (
            <form className="form-grid" onSubmit={registerLecturer} style={{ margin: '16px 0' }}>
              <label><span className="muted">NIP / ID</span><input required minLength="2" maxLength="20" value={lecturerForm.nip} onChange={(event) => setLecturerForm((draft) => ({ ...draft, nip: event.target.value }))} /></label>
              <label><span className="muted">Nama lengkap</span><input required minLength="2" maxLength="120" value={lecturerForm.full_name} onChange={(event) => setLecturerForm((draft) => ({ ...draft, full_name: event.target.value }))} /></label>
              <label><span className="muted">Username</span><input minLength="2" maxLength="120" placeholder="Default: NIP / ID" value={lecturerForm.username} onChange={(event) => setLecturerForm((draft) => ({ ...draft, username: event.target.value }))} /></label>
              <label><span className="muted">Email</span><input type="email" maxLength="120" value={lecturerForm.email} onChange={(event) => setLecturerForm((draft) => ({ ...draft, email: event.target.value }))} /></label>
              <label><span className="muted">Password (minimal 8 karakter)</span><input required type="password" minLength="8" maxLength="72" value={lecturerForm.password} onChange={(event) => setLecturerForm((draft) => ({ ...draft, password: event.target.value }))} /></label>
              <label><span className="muted">Konfirmasi password</span><input required type="password" minLength="8" maxLength="72" value={lecturerForm.passwordConfirmation} onChange={(event) => setLecturerForm((draft) => ({ ...draft, passwordConfirmation: event.target.value }))} /></label>
              <button className="btn primary" type="submit" disabled={lecturerBusy}>{lecturerBusy ? 'Mendaftar...' : 'Daftarkan dosen'}</button>
            </form>
          )}
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>NIP / ID</th><th>Nama</th><th>Username</th><th>Email</th><th>Aksi</th></tr></thead>
              <tbody>
                {adminAdvisors.map((advisor) => {
                  const editing = editingLecturerNip === advisor.nim;
                  const draft = lecturerEditDraft[advisor.nim] || {
                    full_name: advisor.full_name || '',
                    username: advisor.username || advisor.nim,
                    email: advisor.email || '',
                  };
                  return (
                    <Fragment key={advisor.nim}>
                      <tr>
                        <td>{advisor.nim}</td>
                        <td>{editing ? <input value={draft.full_name} onChange={(event) => setLecturerEditDraft((drafts) => ({ ...drafts, [advisor.nim]: { ...draft, full_name: event.target.value } }))} /> : advisor.full_name}</td>
                        <td>{editing ? <input value={draft.username} onChange={(event) => setLecturerEditDraft((drafts) => ({ ...drafts, [advisor.nim]: { ...draft, username: event.target.value } }))} /> : (advisor.username || advisor.nim)}</td>
                        <td>{editing ? <input type="email" value={draft.email} onChange={(event) => setLecturerEditDraft((drafts) => ({ ...drafts, [advisor.nim]: { ...draft, email: event.target.value } }))} /> : (advisor.email || '—')}</td>
                        <td>
                          {editing ? (
                            <>
                              <button className="btn primary" type="button" disabled={lecturerBusy} onClick={() => updateLecturer(advisor.nim)}>Simpan</button>
                              <button className="btn outline" type="button" style={{ marginLeft: 6 }} onClick={() => setEditingLecturerNip('')}>Batal</button>
                            </>
                          ) : (
                            <>
                              <button className="btn outline" type="button" onClick={() => {
                                setLecturerEditDraft((drafts) => ({ ...drafts, [advisor.nim]: draft }));
                                setEditingLecturerNip(advisor.nim);
                              }}>Ubah</button>
                              <button className="btn outline" type="button" style={{ marginLeft: 6 }} disabled={lecturerBusy} onClick={() => deleteLecturer(advisor)}>Hapus</button>
                            </>
                          )}
                        </td>
                      </tr>
                    </Fragment>
                  );
                })}
                {adminAdvisors.length === 0 && <tr><td colSpan="5" className="muted">Belum ada akun dosen PA terdaftar.</td></tr>}
              </tbody>
            </table>
          </div>
          <section className="lecturer-directory-section">
            <h3>Direktori Profil Dosen FTII</h3>
            <p className="muted">Data berasal dari profil resmi FTII. Status akun terhubung otomatis bila NIDN pada direktori sama dengan NIP/ID akun dosen; entri direktori bukan berarti akun login sudah dibuat.</p>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>NIDN / ID Profil</th><th>Nama</th><th>Program Studi</th><th>Bidang Keahlian</th><th>Status Akun</th><th>Pemetaan</th><th>Sumber</th></tr></thead>
                <tbody>
                  {lecturerDirectory.map((entry) => (
                    <tr key={entry.id}>
                      <td>{entry.nidn || 'Tidak dipublikasikan'}</td>
                      <td>{entry.full_name}</td>
                      <td>{entry.program_study}</td>
                      <td>{entry.expertise || 'Tidak dicantumkan'}</td>
                      <td><span className={entry.linked_user_id ? 'class-status-open' : 'class-status-closed'}>{entry.linked_user_id ? `Akun: ${entry.account_nip}` : 'Belum ada akun terhubung'}</span></td>
                      <td>
                        <div className="directory-link-controls">
                          <select
                            aria-label={`Tautkan akun dosen untuk ${entry.full_name}`}
                            value={lecturerDirectoryDraft[entry.id] ?? (entry.linked_user_id || '')}
                            onChange={(event) => setLecturerDirectoryDraft((previous) => ({ ...previous, [entry.id]: event.target.value }))}
                          >
                            <option value="">Belum ditautkan</option>
                            {adminAdvisors.filter((account) => account.is_active !== false).map((account) => (
                              <option key={account.id} value={account.id}>{account.full_name} · {account.nim}</option>
                            ))}
                          </select>
                          <button
                            className="btn outline"
                            type="button"
                            disabled={(lecturerDirectoryDraft[entry.id] ?? String(entry.linked_user_id || '')) === String(entry.linked_user_id || '')}
                            onClick={() => saveLecturerDirectoryLink(entry)}
                          >Simpan</button>
                        </div>
                      </td>
                      <td><a href={entry.profile_url} target="_blank" rel="noreferrer">Profil resmi</a></td>
                    </tr>
                  ))}
                  {!lecturerDirectory.length && <tr><td colSpan="7" className="muted">Direktori dosen belum dimuat.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      );
    }

    if (view === 'riwayat-pa') {
      return (
        <div className="card">
          <h2>Riwayat Penetapan Dosen PA</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Mahasiswa</th><th>NIM</th><th>Dosen PA sebelumnya</th><th>Dosen PA baru</th><th>Admin</th><th>Tanggal</th><th>Alasan</th>
                </tr>
              </thead>
              <tbody>
                {advisorHistory.map((item) => (
                  <tr key={item.id}>
                    <td>{item.student_name || '—'}</td>
                    <td>{item.student_nim || '—'}</td>
                    <td>{item.previous_advisor_name ? `${item.previous_advisor_name}${item.previous_advisor_nim ? ` (${item.previous_advisor_nim})` : ''}` : 'Belum ditetapkan'}</td>
                    <td>{item.advisor_name ? `${item.advisor_name}${item.advisor_nim ? ` (${item.advisor_nim})` : ''}` : '—'}</td>
                    <td>{item.admin_name || 'Sistem'}</td>
                    <td>{new Date(item.changed_at).toLocaleString('id-ID')}</td>
                    <td>{item.reason || '—'}</td>
                  </tr>
                ))}
                {advisorHistory.length === 0 && <tr><td colSpan="7" className="muted">Belum ada perubahan penetapan Dosen PA.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      );
    }


    if (view === 'kelas' && user.role === 'admin') {
      const totalSections = classList.length;
      const openSections = classList.filter((section) => section.is_open).length;
      const totalSeats = classList.filter((section) => section.is_open).reduce((sum, section) => sum + Number(section.capacity || 0), 0);
      const usedSeats = classList.filter((section) => section.is_open).reduce((sum, section) => sum + Number(section.occupied || 0), 0);
      return (
        <div className="class-management-page">
          <section className="class-management-hero">
            <div><span className="guide-eyebrow"><CalendarDays size={15} /> MANAJEMEN PERKULIAHAN</span><h2>Kelas Paralel & Jadwal</h2><p>Publikasikan beberapa kelas untuk satu mata kuliah, atur dosen/ruang/waktu dan pantau kapasitas sebelum mahasiswa menyusun KRS.</p></div>
            <div className="class-management-icon"><CalendarDays size={54} /></div>
          </section>
          <div className="stat-grid class-management-stats">
            <div className="stat"><small>Total kelas</small><strong>{totalSections}</strong></div>
            <div className="stat"><small>Kelas dibuka</small><strong>{openSections}</strong></div>
            <div className="stat"><small>Kapasitas aktif</small><strong>{totalSeats} kursi</strong></div>
            <div className="stat"><small>Terpakai</small><strong>{usedSeats} kursi</strong></div>
          </div>
          <section className="class-form-card">
            <div className="class-section-heading"><div><span className="guide-role-tag admin">{editingClassId ? 'EDIT KELAS' : 'KELAS BARU'}</span><h3>{editingClassId ? 'Perbarui kelas paralel' : 'Buat kelas paralel'}</h3><p className="muted">Kelas yang dibuka akan muncul pada proses pemilihan kelas mahasiswa.</p></div>
              {editingClassId && <button className="btn outline" type="button" onClick={() => { setEditingClassId(null); setClassForm({ course_code: '', class_name: '', lecturer_id: '', room: '', day: 'Senin', start_time: '', end_time: '', capacity: 40, semester: '1', is_open: true }); }}>Batal edit</button>}
            </div>
            <form className="class-form-grid" onSubmit={saveParallelClass}>
              <label><span>Mata kuliah aktif</span><select required value={classForm.course_code} onChange={(event) => setClassForm((previous) => ({ ...previous, course_code: event.target.value }))}><option value="">Pilih mata kuliah</option>{courseList.map((course) => <option key={course.code} value={course.code}>{course.code} · {course.name}</option>)}</select></label>
              <label><span>Nama kelas</span><input required maxLength="40" placeholder="A / B / Reguler 1" value={classForm.class_name} onChange={(event) => setClassForm((previous) => ({ ...previous, class_name: event.target.value }))} /></label>
              <label><span>Dosen pengampu</span><select value={classForm.lecturer_id} onChange={(event) => setClassForm((previous) => ({ ...previous, lecturer_id: event.target.value }))}><option value="">Belum ditentukan</option>{adminAdvisors.filter((lecturer) => lecturer.is_active !== false).map((lecturer) => <option key={lecturer.id} value={lecturer.id}>{lecturer.full_name} · {lecturer.nim}</option>)}</select></label>
              <label><span>Ruang aktif</span>
                <select required value={classForm.room} onChange={(event) => setClassForm((previous) => ({ ...previous, room: event.target.value, start_time: '', end_time: '' }))}>
                  <option value="">Pilih ruang yang sudah diverifikasi</option>
                  {roomList.filter((room) => room.is_active).map((room) => (
                    <option key={room.code} value={room.code}>{room.code} · Lantai {room.floor} · {room.capacity} kursi</option>
                  ))}
                </select>
                <small className="muted">Hanya ruang berstatus aktif yang dapat dipakai untuk kelas.</small>
              </label>
              <label><span>Hari</span><select required value={classForm.day} onChange={(event) => setClassForm((previous) => ({ ...previous, day: event.target.value, start_time: '', end_time: '' }))}>{['Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu'].map((day) => <option key={day} value={day}>{day}</option>)}</select></label>
              <label><span>Semester</span><input required type="number" min="1" max="14" step="1" value={classForm.semester} onChange={(event) => setClassForm((previous) => ({ ...previous, semester: event.target.value }))} /></label>
              <label><span>Jam mulai (slot tersedia)</span>
                <select
                  required
                  value={classForm.start_time}
                  disabled={scheduleSlotBusy || !scheduleSlots.length}
                  onChange={(event) => {
                    const slot = scheduleSlots.find((item) => item.start_time === event.target.value);
                    setClassForm((previous) => ({
                      ...previous,
                      start_time: slot?.start_time || '',
                      end_time: slot?.end_time || '',
                    }));
                  }}
                >
                  <option value="">{scheduleSlotBusy ? 'Memeriksa bentrok...' : 'Pilih slot jam mulai'}</option>
                  {scheduleSlots.map((slot) => <option key={slot.start_time} value={slot.start_time}>{slot.start_time} – selesai {slot.end_time}</option>)}
                </select>
                <small className="muted">{scheduleSlots.length ? `${scheduleSlots.length} slot tidak bentrok tersedia` : scheduleSlotBusy ? 'Sedang memeriksa jadwal ruang dan dosen.' : 'Tidak ada slot tersedia untuk kombinasi tersebut.'}</small>
              </label>
              <label><span>Jam selesai (otomatis)</span><input value={classForm.end_time || ''} readOnly aria-readonly="true" placeholder="Dihitung dari SKS" /></label>
              <div className="schedule-duration-note">
                <Clock3 size={16} />
                <span>Durasi otomatis: {scheduleDuration || 0} menit · {courseList.find((course) => course.code === classForm.course_code)?.sks || 0} SKS × 50 menit. Jam kuliah hanya 07:00–18:00.</span>
              </div>
              <label><span>Kapasitas kursi</span><input required type="number" min="1" max="10000" step="1" value={classForm.capacity} onChange={(event) => setClassForm((previous) => ({ ...previous, capacity: event.target.value }))} /></label>
              <label className="class-open-toggle"><input type="checkbox" checked={classForm.is_open} onChange={(event) => setClassForm((previous) => ({ ...previous, is_open: event.target.checked }))} /> Buka kelas untuk dipilih mahasiswa</label>
              <div className="class-form-actions"><button className="btn primary" type="submit" disabled={classBusy || scheduleSlotBusy || !courseList.length || !classForm.room || !classForm.start_time || !classForm.end_time}>{classBusy ? 'Menyimpan...' : editingClassId ? 'Simpan perubahan' : 'Tambah kelas paralel'}</button></div>
            </form>
            <div className="class-validation-note"><ShieldCheck size={17} /><span>Sistem menghitung durasi dari bobot mata kuliah: 1 SKS = 50 menit. Slot dibatasi 07:00–18:00 dan dicek terhadap bentrok ruang serta dosen pada semua semester. Mahasiswa memilih kelas yang sudah ditetapkan, bukan menentukan waktu/ruang sendiri. Jika kelas masih memiliki peserta atau reservasi, perubahan jadwal, dosen, ruang, semester, dan status kelas dikunci; kapasitas hanya dapat dinaikkan.</span></div>
          </section>
          <section className="class-table-card">
            <div className="class-section-heading"><div><h3>Daftar kelas terdaftar</h3><p className="muted">Sisa kursi dan status kelas akan dipakai sebagai informasi saat mahasiswa memilih kelas di Draft KRS.</p></div><button className="btn outline" type="button" onClick={() => refreshClassList().catch((error) => setActionMessage(error.message))}>Perbarui data</button></div>
            <div className="table-wrap"><table className="table class-table">
              <thead><tr><th>Mata kuliah</th><th>Kelas / dosen</th><th>Jadwal / ruang</th><th>Kapasitas</th><th>Status</th><th>Aksi</th></tr></thead>
              <tbody>{classList.map((section) => (
                <tr key={section.id}>
                  <td><strong>{section.course_code}</strong><br />{section.course_name}</td>
                  <td>{section.class_name}<br /><span className="muted">{section.lecturer_name || 'Dosen belum ditentukan'}</span></td>
                  <td>{section.day}, {section.start_time}-{section.end_time}<br /><span className="muted">{section.room}</span></td>
                  <td><strong>{section.occupied}/{section.capacity}</strong><div className="class-seat-meter"><span style={{ width: `${section.capacity ? Math.min(100, (section.occupied / section.capacity) * 100) : 100}%` }} /></div><small>{section.remaining_seats} kursi tersisa</small></td>
                  <td><span className={section.is_open ? 'class-status-open' : 'class-status-closed'}>{section.is_open ? 'Dibuka' : 'Ditutup'}</span></td>
                  <td><div className="class-row-actions"><button className="btn outline" type="button" disabled={classBusy} onClick={() => editParallelClass(section)}>Edit</button><button className="btn outline danger" type="button" disabled={classBusy || !section.is_open || section.occupied > 0} onClick={() => closeParallelClass(section)}>Tutup</button></div></td>
                </tr>
              ))}{classList.length === 0 && <tr><td colSpan="6" className="muted">Belum ada kelas paralel. Buat kelas pertama menggunakan formulir di atas.</td></tr>}</tbody>
            </table></div>
          </section>
          <section className="class-table-card room-inventory-section">
            <div className="class-section-heading">
              <div>
                <h3>Inventaris Ruangan FTII</h3>
                <p className="muted">Ruang yang teridentifikasi pada arsip 2023/2024 dimasukkan sebagai nonaktif. Admin wajib mengonfirmasi kondisi fisik dan kapasitas sebelum mengaktifkannya.</p>
              </div>
              <button className="btn outline" type="button" disabled={exportBusy === 'rooms'} onClick={() => downloadAdminExport('rooms')}>
                {exportBusy === 'rooms' ? 'Mengekspor...' : 'Ekspor Data Ruangan'}
              </button>
            </div>
            <form className="room-form-grid" onSubmit={saveRoom}>
              <label><span>Kode Ruang</span><input required pattern="FT[234][0-9]{2}" title="Format FT2xx, FT3xx, atau FT4xx" placeholder="FT401" maxLength="5" value={roomForm.code} disabled={Boolean(editingRoomCode)} onChange={(event) => setRoomForm((previous) => ({ ...previous, code: event.target.value.toUpperCase().replace(/[^FT0-9]/g, '').slice(0, 5) }))} /></label>
              <label><span>Kapasitas resmi</span><input type="number" min="1" max="1000" value={roomForm.capacity} onChange={(event) => setRoomForm((previous) => ({ ...previous, capacity: event.target.value }))} placeholder="Isi setelah verifikasi" /></label>
              <label><span>Tipe ruang</span><select value={roomForm.room_type} onChange={(event) => setRoomForm((previous) => ({ ...previous, room_type: event.target.value }))}>{['Ruang kuliah','Laboratorium','Ruang praktik','Studio'].map((type) => <option key={type} value={type}>{type}</option>)}</select></label>
              <label className="class-open-toggle"><input type="checkbox" checked={roomForm.is_active} onChange={(event) => setRoomForm((previous) => ({ ...previous, is_active: event.target.checked }))} /> Aktif dan boleh dipakai untuk penjadwalan</label>
              <label className="room-notes-field"><span>Catatan verifikasi</span><textarea rows={2} value={roomForm.notes} onChange={(event) => setRoomForm((previous) => ({ ...previous, notes: event.target.value }))} placeholder="Contoh: kapasitas dan kondisi ruang sudah diverifikasi Admin" /></label>
              <div className="class-form-actions">
                <button className="btn primary" type="submit" disabled={roomBusy || !(editingRoomCode || roomForm.code)}>
                  {roomBusy ? 'Menyimpan...' : editingRoomCode ? 'Simpan perubahan ruang' : 'Tambah ruang'}
                </button>
                {editingRoomCode && <button className="btn outline" type="button" onClick={() => { setEditingRoomCode(''); setRoomForm({ code: '', capacity: '', room_type: 'Ruang kuliah', is_active: false, notes: '' }); }}>Batal</button>}
              </div>
            </form>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Kode</th><th>Lantai</th><th>Kapasitas</th><th>Tipe</th><th>Kelas terkait</th><th>Status</th><th>Aksi</th></tr></thead>
                <tbody>
                  {roomList.map((room) => (
                    <tr key={room.code}>
                      <td><strong>{room.code}</strong></td>
                      <td>{room.floor}</td>
                      <td>{room.capacity ?? 'Belum diverifikasi'}</td>
                      <td>{room.room_type}</td>
                      <td>{room.class_count}</td>
                      <td><span className={room.is_active ? 'class-status-open' : 'class-status-closed'}>{room.is_active ? 'Aktif' : 'Perlu verifikasi'}</span></td>
                      <td><button className="btn outline" type="button" disabled={roomBusy} onClick={() => editRoom(room)}>Ubah / verifikasi</button></td>
                    </tr>
                  ))}
                  {roomList.length === 0 && <tr><td colSpan="7" className="muted">Belum ada data ruangan. Tambahkan ruang yang telah diverifikasi.</td></tr>}
                </tbody>
              </table>
            </div>
            <p className="muted">Format baku: FT2xx, FT3xx, FT4xx. Arsip lama mencatat FT301–FT305 dan FT401–FT406; tidak ditemukan kode FT2xx yang dapat diverifikasi pada sumber yang ditelusuri.</p>
          </section>
        </div>
      );
    }

    if (view === 'admin') {
      const courseFields = [
        ['code', 'Kode'], ['name', 'Nama mata kuliah'], ['sks', 'SKS'],
        ['semester', 'Semester utama'], ['available_semesters', 'Semester tersedia (pisahkan koma)'],
        ['category', 'Kategori'], ['prerequisite_text', 'Prasyarat/kriteria'],
        ['prerequisite_codes', 'Kode prasyarat yang harus lulus'],
        ['description', 'Keterangan'], ['day', 'Hari'], ['time', 'Waktu'],
        ['capacity', 'Kuota total mata kuliah'],
      ];
      const courseFieldInput = (course, field, label, update) => (
        <label className="course-edit-field" key={field}>
          <span className="muted">{label}</span>
          {['description', 'prerequisite_text'].includes(field)
            ? <textarea rows={field === 'description' ? 2 : 3} value={course[field] ?? ''} onChange={(event) => update(field, event.target.value)} />
            : <input
              type={['sks', 'semester', 'capacity'].includes(field) ? 'number' : 'text'}
              min={['sks', 'semester'].includes(field) ? 1 : undefined}
              max={field === 'sks' ? 10 : field === 'semester' ? 14 : undefined}
              value={course[field] ?? ''}
              onChange={(event) => update(field, ['sks', 'semester'].includes(field) ? Number(event.target.value) : event.target.value)}
            />}
        </label>
      );
      return (
        <div className="card">
          <h3>Manajemen Data</h3>
          <p>Kelola seluruh data kurikulum, prasyarat, dan keterangan. Rekomendasi mahasiswa menggunakan katalog aktif di halaman ini.</p>
          <p className="muted">Kuota total mata kuliah adalah batas agregat seluruh kelasnya. Setiap kelas paralel juga memiliki batas kursi sendiri; pengajuan harus memenuhi kedua batas tersebut.</p>
          <div className="export-actions admin-reference-exports">
            <button className="btn outline" type="button" disabled={exportBusy === 'lecturers'} onClick={() => downloadAdminExport('lecturers')}>
              {exportBusy === 'lecturers' ? 'Mengekspor...' : 'Ekspor Data Dosen'}
            </button>
            <button className="btn outline" type="button" disabled={exportBusy === 'rooms'} onClick={() => downloadAdminExport('rooms')}>
              {exportBusy === 'rooms' ? 'Mengekspor...' : 'Ekspor Data Ruangan'}
            </button>
          </div>
          <section style={{ marginTop: 20 }}>
            <h3>Periode dan Batas Akademik</h3>
            <div className="course-edit-grid">
              <label className="course-edit-field">
                <span className="muted">Tahun ajaran aktif</span>
                <input
                  type="text"
                  maxLength="9"
                  pattern="\d{4}/\d{4}"
                  placeholder="2026/2027"
                  value={settingDraft.active_academic_year || ''}
                  onChange={(event) => setSettingDraft((previous) => ({
                    ...previous,
                    active_academic_year: event.target.value.replace(/[^0-9/]/g, '').slice(0, 9),
                  }))}
                />
                <small className="muted">Batas angkatan daftar mahasiswa mengikuti tahun pertama pada tahun ajaran ini.</small>
                <button className="btn outline" type="button" onClick={() => saveAdminSetting('active_academic_year')}>Simpan tahun ajaran</button>
              </label>
              {[
                ['krs_period_start', 'Mulai periode KRS', 'datetime-local'],
                ['krs_period_end', 'Selesai periode KRS', 'datetime-local'],
                ['krs_fill_deadline', 'Batas waktu pengisian KRS', 'datetime-local'],
                ['kprs_period_start', 'Mulai periode KPRS', 'datetime-local'],
                ['kprs_period_end', 'Selesai periode KPRS', 'datetime-local'],
              ].map(([key, label, type]) => (
                <label className="course-edit-field" key={key}>
                  <span className="muted">{label}</span>
                  <input
                    type={type}
                    value={settingDraft[key] || ''}
                    onChange={(event) => setSettingDraft((previous) => ({ ...previous, [key]: event.target.value }))}
                  />
                  <button className="btn outline" type="button" onClick={() => saveAdminSetting(key)}>Simpan</button>
                </label>
              ))}
              <label className="course-edit-field">
                <span className="muted">Maksimal SKS berdasarkan IPS (JSON)</span>
                <textarea
                  rows={3}
                  value={settingDraft.max_sks_by_ips || ''}
                  onChange={(event) => setSettingDraft((previous) => ({ ...previous, max_sks_by_ips: event.target.value }))}
                />
                <button className="btn outline" type="button" onClick={() => saveAdminSetting('max_sks_by_ips')}>Simpan</button>
              </label>
            </div>
          </section>
          <section style={{ marginTop: 20 }}>
            <h3>Override dan Pembukaan Kunci KRS</h3>
            <div className="table-scroll">
              <table className="table">
                <thead><tr><th>Mahasiswa</th><th>Semester</th><th>Mata Kuliah</th><th>Alasan</th><th>Tindakan</th></tr></thead>
                <tbody>
                  {approvedPlans.map((plan) => (
                    <tr key={plan.id}>
                      <td>{plan.student_name || plan.student_id}</td>
                      <td>{plan.semester}</td>
                      <td>{(plan.courses || []).map((course) => typeof course === 'string' ? course : course.code).join(', ')}</td>
                      <td>
                        <input
                          value={overrideReason[plan.id] || ''}
                          onChange={(event) => setOverrideReason((previous) => ({ ...previous, [plan.id]: event.target.value }))}
                          aria-label={`Alasan override ${plan.student_name || plan.student_id}`}
                        />
                        <input
                          style={{ marginTop: 6 }}
                          value={overrideCourses[plan.id] || ''}
                          onChange={(event) => setOverrideCourses((previous) => ({ ...previous, [plan.id]: event.target.value }))}
                          placeholder="Kode MK baru (pisahkan koma, opsional)"
                          aria-label={`Mata kuliah override ${plan.student_name || plan.student_id}`}
                        />
                        {(overrideCourses[plan.id]?.trim()
                          ? overrideCourses[plan.id].split(',').map((code) => code.trim().toUpperCase()).filter(Boolean)
                          : (plan.courses || []).map((course) => typeof course === 'string' ? course : course.code)
                        ).map((code) => {
                          const options = classList.filter((section) => section.course_code === code && String(section.semester) === String(plan.semester));
                          if (!options.length) return null;
                          const original = (plan.courses || []).find((course) => typeof course === 'object' && course.code === code);
                          const selected = overrideClassSelections[plan.id]?.[code] ?? original?.class_id ?? '';
                          return (
                            <label key={code} className="course-edit-field" style={{ marginTop: 7 }}>
                              <span className="muted">Kelas {code}</span>
                              <select value={selected} onChange={(event) => setOverrideClassSelections((previous) => ({
                                ...previous,
                                [plan.id]: { ...(previous[plan.id] || {}), [code]: event.target.value },
                              }))}>
                                <option value="">Pilih kelas</option>
                                {options.map((section) => <option key={section.id} value={section.id} disabled={!section.is_open || (section.remaining_seats <= 0 && Number(selected) !== Number(section.id))}>{section.class_name} · {section.day} {section.start_time}-{section.end_time} · {section.remaining_seats} kursi</option>)}
                              </select>
                            </label>
                          );
                        })}
                      </td>
                      <td>
                        <button className="btn outline" type="button" onClick={() => overrideStudyPlan(plan.id, 'revision_requested', overrideReason[plan.id], overrideCourses[plan.id])}>Buka/Revisi</button>
                        {' '}
                        <button className="btn outline danger" type="button" onClick={() => overrideStudyPlan(plan.id, 'draft', overrideReason[plan.id], overrideCourses[plan.id])}>Batalkan Approval</button>
                      </td>
                    </tr>
                  ))}
                  {!approvedPlans.length && <tr><td colSpan={5}>Tidak ada KRS approved.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 18, flexWrap: 'wrap' }}>
            <label className="btn primary" htmlFor="import-courses" style={{ cursor: 'pointer' }}>
              Impor Excel / CSV
            </label>
            <input id="import-courses" type="file" accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv" onChange={importCourseData} style={{ display: 'none' }} />
            <button className="btn outline" type="button" onClick={trainModel}>Latih / evaluasi ulang model</button>
          </div>
          <p className="muted">Impor Excel mengganti seluruh katalog aktif. Kode berulang pada beberapa semester digabung sebagai satu mata kuliah dengan beberapa semester tersedia.</p>
          <details style={{ marginTop: 20 }}>
            <summary className="btn outline" style={{ display: 'inline-flex', alignItems: 'center' }}>Tambah mata kuliah</summary>
            <div className="course-edit-grid">
              {courseFields.map(([field, label]) => courseFieldInput(
                newCourse,
                field,
                label,
                (name, value) => setNewCourse((previous) => ({ ...previous, [name]: value })),
              ))}
            </div>
            <button className="btn primary" type="button" disabled={Boolean(courseBusyCode)} onClick={() => saveCourse(newCourse, true)}>
              Simpan mata kuliah baru
            </button>
          </details>
          <div className="table-wrap" style={{ marginTop: 20 }}>
            <table className="table">
              <thead><tr><th>Mata kuliah</th><th>SKS / semester</th><th>Kategori</th><th>Prasyarat dan keterangan</th><th>Aksi</th></tr></thead>
              <tbody>
                {courseList.map((course) => (
                  <Fragment key={course._originalCode}>
                    <tr>
                      <td><strong>{course.code}</strong><br />{course.name}</td>
                      <td>{course.sks} SKS<br />Semester {course.available_semesters}</td>
                      <td>{course.category}</td>
                      <td>
                        {course.prerequisite_text && <><strong>Prasyarat:</strong> {course.prerequisite_text}<br /></>}
                        {course.description && <><strong>Keterangan:</strong> {course.description}</>}
                      </td>
                      <td>
                        <div className="course-edit-actions">
                          <button
                            className="btn outline"
                            type="button"
                            disabled={Boolean(courseBusyCode)}
                            onClick={() => setEditingCourseCode(
                              editingCourseCode === course._originalCode ? '' : course._originalCode,
                            )}
                          >
                            {editingCourseCode === course._originalCode ? 'Tutup' : 'Ubah'}
                          </button>
                          <button className="btn outline" type="button" disabled={Boolean(courseBusyCode)} onClick={() => deactivateCourse(course)}>
                            Nonaktifkan
                          </button>
                        </div>
                      </td>
                    </tr>
                    {editingCourseCode === course._originalCode && (
                      <tr>
                        <td colSpan="5">
                          <div className="course-edit-grid">
                            {courseFields.map(([field, label]) => courseFieldInput(
                              course,
                              field,
                              label,
                              (name, value) => updateCourseDraft(course._originalCode, name, value),
                            ))}
                          </div>
                          <button className="btn primary" style={{ marginTop: 12 }} type="button" disabled={Boolean(courseBusyCode)} onClick={() => saveCourse(course)}>
                            {courseBusyCode === course._originalCode ? 'Menyimpan...' : 'Simpan perubahan'}
                          </button>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>          </div>
          <section style={{ marginTop: 24 }}>
            <h3>Riwayat Aktivitas</h3>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Waktu</th><th>Aktor</th><th>Tindakan</th><th>Target</th></tr></thead>
                <tbody>
                  {adminAuditLogs.map((item) => (
                    <tr key={item.id}>
                      <td>{new Date(item.created_at).toLocaleString('id-ID')}</td>
                      <td>{item.actor_name || 'Sistem'}</td>
                      <td>{item.action}</td>
                      <td>{item.entity_type} #{item.entity_id}</td>
                    </tr>
                  ))}
                  {adminAuditLogs.length === 0 && <tr><td colSpan="4" className="muted">Belum ada aktivitas tercatat.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      );
    }

    return null;
  })();

  const userLabel = user?.role === 'mahasiswa'
    ? 'Dashboard Mahasiswa'
    : user?.role === 'dosen' ? 'Dashboard Dosen PA' : 'Dashboard Admin Prodi';

  if (!user) {
    return (
      <div className="app-shell" style={{ padding: '40px 24px' }}>
        <div className="toast-viewport" aria-live="polite">
          {toasts.map((toast) => <ToastItem key={toast.id} toast={toast} onDismiss={dismissToast} />)}
        </div>
        {(pendingRequests > 0 || loading) && (
          <div className="global-loading-overlay" role="status" aria-live="polite" aria-label="Aplikasi sedang memproses">
            <div className="global-loading-card">
              <span className="global-loading-spinner" aria-hidden="true" />
              <strong>CourseRecom</strong>
              <span>Memproses permintaan, mohon tunggu...</span>
            </div>
          </div>
        )}
        <div className="login-box">
          <div className="login-brand-block">
            <img src="/logo.png" alt="CourseRecom logo" style={{ width: 88, height: 88 }} />
            <h2>CourseRecom</h2>
            <span className="ml-brand-badge"><BrainCircuit size={16} /> POWERED BY MACHINE LEARNING</span>
            <h3>Rencanakan Studi Lebih Cerdas</h3>
            <p>Analisis kemiripan riwayat akademik, minat, nilai prasyarat, dan kurikulum untuk membantu menemukan rekomendasi mata kuliah yang lebih relevan.</p>
            <div className="login-ml-tags"><span>Academic History</span><span>Similar Students</span><span>Smart Recommendation</span></div>
          </div>
          {authMode === 'register' ? (
            <>
              <h3>Daftar akun mahasiswa</h3>
              <form className="form-grid" onSubmit={registerStudent}>
                <label>
                  <span className="muted">NIM</span>
                  <input required minLength="2" maxLength="20" autoComplete="username" value={registrationForm.nim} onChange={(e) => setRegistrationForm({ ...registrationForm, nim: e.target.value })} />
                </label>
                <label>
                  <span className="muted">Nama lengkap</span>
                  <input required minLength="2" maxLength="120" autoComplete="name" value={registrationForm.full_name} onChange={(e) => setRegistrationForm({ ...registrationForm, full_name: e.target.value })} />
                </label>
                <label>
                  <span className="muted">Username</span>
                  <input minLength="2" maxLength="120" autoComplete="username" value={registrationForm.username} placeholder="Default: NIM" onChange={(e) => setRegistrationForm({ ...registrationForm, username: e.target.value })} />
                </label>
                <label>
                  <span className="muted">Program studi</span>
                  <select
                    required
                    value={registrationForm.program_study}
                    onChange={(event) => {
                      const program_study = event.target.value;
                      const options = programInterestCatalog[program_study]?.options || [];
                      setRegistrationForm({ ...registrationForm, program_study, interests: options[0] || '' });
                    }}
                  >
                    <option value="">Pilih program studi</option>
                    {Object.keys(programInterestCatalog).map((program) => <option key={program} value={program}>{program}</option>)}
                  </select>
                </label>
                <label>
                  <span className="muted">{programInterestCatalog[registrationForm.program_study]?.kind || 'Bidang minat'}</span>
                  <select required value={registrationForm.interests} onChange={(event) => setRegistrationForm({ ...registrationForm, interests: event.target.value })}>
                    {(programInterestCatalog[registrationForm.program_study]?.options || []).map((interest) => <option key={interest} value={interest}>{interest}</option>)}
                  </select>
                  <small className="muted">{registrationForm.program_study === 'Sistem dan Teknologi Informasi'
                    ? 'Mengikuti dua peminatan resmi STI: Manajemen Teknologi Informasi (MTI) dan Kecerdasan Bisnis (KB).'
                    : 'Untuk program studi yang belum mempublikasikan jalur formal, pilihan ini dicatat sebagai bidang minat akademik.'}</small>
                </label>
                <label>
                  <span className="muted">Angkatan</span>
                  <input
                    type="number"
                    min="1900"
                    max={academicYear.max_angkatan}
                    step="1"
                    inputMode="numeric"
                    value={registrationForm.angkatan}
                    onChange={(event) => setRegistrationForm({
                      ...registrationForm,
                      angkatan: event.target.value.replace(/\D/g, '').slice(0, 4),
                    })}
                  />
                  <small className="muted">Hanya angka 4 digit, maksimal angkatan {academicYear.max_angkatan} (tahun ajaran {academicYear.academic_year}).</small>
                </label>
                <label>
                  <span className="muted">Password (minimal 8 karakter)</span>
                  <input required type="password" minLength="8" maxLength="72" autoComplete="new-password" value={registrationForm.password} onChange={(e) => setRegistrationForm({ ...registrationForm, password: e.target.value })} />
                </label>
                <label>
                  <span className="muted">Konfirmasi password</span>
                  <input required type="password" minLength="8" maxLength="72" autoComplete="new-password" value={registrationForm.passwordConfirmation} onChange={(e) => setRegistrationForm({ ...registrationForm, passwordConfirmation: e.target.value })} />
                </label>
                <button className="btn primary" type="submit" disabled={loading}>
                  {loading ? 'Memproses...' : 'Daftar sebagai mahasiswa'}
                </button>
              </form>
              <button className="btn outline" type="button" style={{ marginTop: 12, width: '100%' }} onClick={() => {
                setAuthMode('login');
                setLoginError('');
              }}>Kembali ke masuk</button>
            </>
          ) : (
            <>
              <form className="form-grid" onSubmit={login}>
                    <div className="role-selector" role="radiogroup" aria-label="Pilih peran login">
                      {[['mahasiswa', 'Mahasiswa'], ['dosen', 'Dosen PA'], ['admin', 'Admin Prodi']].map(([role, label]) => (
                        <button key={role} type="button" role="radio" aria-checked={selectedRole === role} className={`role-option${selectedRole === role ? ' active' : ''}`} onClick={() => setSelectedRole(role)}>{label}</button>
                      ))}
                    </div>
                    <strong className="login-role">Masuk sebagai {selectedRole === 'mahasiswa' ? 'Mahasiswa' : selectedRole === 'dosen' ? 'Dosen PA' : 'Admin Prodi'}</strong>
                    <label>
                  <span className="muted">Username</span>
                  <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
                </label>
                <label>
                  <span className="muted">Password</span>
                  <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
                </label>
                <button className="btn primary" type="submit" disabled={loading}>
                  {loading ? 'Memproses...' : 'Masuk'}
                </button>
              </form>
              <button className="btn outline" type="button" style={{ marginTop: 12, width: '100%' }} onClick={() => {
                setAuthMode('register');
                setLoginError('');
                setAuthMessage('');
              }}>Daftar akun mahasiswa</button>
            </>
          )}
          {!IS_PRODUCTION_ENVIRONMENT && (
            <div className="login-demo">
              <Info size={18} aria-hidden="true" />
              <span>
                Akun demo: mahasiswa <strong>2203001</strong>, dosen <strong>pa001</strong>, admin <strong>admin</strong>; password: <strong>password123</strong>.
              </span>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell authenticated-shell">
      <header className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <img src="/logo.png" alt="CourseRecom" style={{ width: 46, height: 46 }} />
          <strong>CourseRecom</strong>
        </div>
        <div className="topbar-label">{userLabel}</div>
        <button
          type="button"
          className="mobile-menu-toggle"
          aria-label={mobileMenuOpen ? 'Tutup menu' : 'Buka menu'}
          aria-expanded={mobileMenuOpen}
          aria-controls="mobile-navigation"
          onClick={() => setMobileMenuOpen((open) => !open)}
        >
          {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </header>
      <div className="main-layout">
        <aside className="sidebar">
          {navigationItems.map(({ key, label, Icon }) => (
            <button key={key} type="button" className={view === key ? 'active' : ''} onClick={() => navigateTo(key)}>
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
          <button className="logout-button" type="button" onClick={logout}><LogOut size={18} aria-hidden="true" /><span>Keluar</span></button>
        </aside>
        <main className="content">{pageContent}</main>
      </div>
      <footer style={{ textAlign: 'center', padding: '18px 20px 30px', color: '#64748b' }}>CourseRecom | Kelompok 5</footer>
      {mobileMenuOpen && (
        <div className="mobile-menu-backdrop" onClick={() => setMobileMenuOpen(false)}>
          <nav
            className="mobile-menu"
            id="mobile-navigation"
            aria-label="Navigasi utama"
            onClick={(event) => event.stopPropagation()}
          >
            {navigationItems.map(({ key, label, Icon }) => (
              <button key={key} type="button" className={view === key ? 'active' : ''} onClick={() => navigateTo(key)}>
                <Icon size={19} aria-hidden="true" />
                <span>{label}</span>
              </button>
            ))}
            <button className="logout-button" type="button" onClick={logout}>
              <LogOut size={19} aria-hidden="true" /><span>Keluar</span>
            </button>
          </nav>
        </div>
      )}
      {officialKrsPreviewUrl && (
        <div
          className="krs-preview-overlay"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeOfficialKrsPreview();
          }}
        >
          <section
            className="krs-preview-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="krs-preview-title"
          >
            <header className="krs-preview-header">
              <div>
                <span className="guide-eyebrow">DOKUMEN AKADEMIK RESMI</span>
                <h2 id="krs-preview-title">Preview KRS</h2>
                <p className="muted">Periksa detail rencana studi sebelum mengunduh dokumen PDF.</p>
              </div>
              <button className="krs-preview-close" type="button" onClick={closeOfficialKrsPreview} aria-label="Tutup preview KRS">
                <X size={22} />
              </button>
            </header>
            <div className="krs-preview-frame-wrap">
              <iframe
                className="krs-preview-frame"
                title={`Preview KRS resmi #${officialKrsPreviewPlanId || ''}`}
                src={officialKrsPreviewUrl}
              />
            </div>
            <footer className="krs-preview-footer">
              <span className="muted">KRS hanya dapat diunduh setelah disetujui Dosen PA.</span>
              <div>
                <button className="btn outline" type="button" onClick={closeOfficialKrsPreview}>Tutup</button>
                <a
                  className="btn primary"
                  href={officialKrsPreviewUrl}
                  download={`KRS-${user?.nim || 'mahasiswa'}-${officialKrsPreviewPlanId || ''}.pdf`}
                >
                  Unduh KRS
                </a>
              </div>
            </footer>
          </section>
        </div>
      )}
      <div className="toast-viewport" aria-live="polite">
        {toasts.map((toast) => <ToastItem key={toast.id} toast={toast} onDismiss={dismissToast} />)}
      </div>
      {(pendingRequests > 0 || loading || khsBusy || studyPlanBusy || lecturerBusy || Boolean(accountBusyNim) || Boolean(courseBusyCode)) && (
        <div className="global-loading-overlay" role="status" aria-live="polite" aria-label="Aplikasi sedang memproses">
          <div className="global-loading-card">
            <span className="global-loading-spinner" aria-hidden="true" />
            <strong>CourseRecom</strong>
            <span>Memproses permintaan, mohon tunggu...</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;