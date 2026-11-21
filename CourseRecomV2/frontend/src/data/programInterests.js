export const INTEREST_OPTIONS = [
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
export const PROGRAM_INTERESTS = {
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
export const canonicalProgramName = (value) => {
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

export function canonicalizeInterests(interests) {
  const selected = new Set(
    interests.split(',').map((interest) => (
      LEGACY_INTERESTS[interest.trim().toLowerCase()]
    )).filter(Boolean),
  );
  return INTEREST_OPTIONS.find((interest) => selected.has(interest)) || interests.trim();
}
