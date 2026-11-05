import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  BookOpenCheck,
  CheckCircle2,
  FileClock,
  FileUp,
  HelpCircle,
  History,
  Home,
  Info,
  LogOut,
  Menu,
  PieChart,
  Settings,
  UserRound,
  UsersRound,
  X,
} from 'lucide-react';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '');
const IS_PRODUCTION_ENVIRONMENT = String(import.meta.env.VITE_ENVIRONMENT || '').toLowerCase() === 'production';

const EMPTY_RECOMMENDATIONS = {
  status: 'khs_required',
  profile: null,
  recommendations: [],
  rejected: [],
  semester_antara: [],
};
const INTEREST_OPTIONS = [
  'Manajemen Sistem Informasi',
  'Kecerdasan Bisnis',
];
const LEGACY_INTERESTS = {
  'manajemen sistem informasi': 'Manajemen Sistem Informasi',
  'manajemen & sistem informasi': 'Manajemen Sistem Informasi',
  'peminatan manajemen si': 'Manajemen Sistem Informasi',
  msi: 'Manajemen Sistem Informasi',
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
  return INTEREST_OPTIONS.filter((interest) => selected.has(interest)).join(',');
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

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
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
    const message = typeof data === 'object' && data !== null ? data.detail || data.message || 'Permintaan gagal' : data || 'Permintaan gagal';
    throw new Error(message);
  }

  return data;
}

function App() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState('dashboard');
  const [authMode, setAuthMode] = useState('login');
  const [selectedRole, setSelectedRole] = useState('mahasiswa');
  const [form, setForm] = useState({ username: '', password: '' });
  const [registrationForm, setRegistrationForm] = useState({ nim: '', username: '', full_name: '', program_study: '', angkatan: '', password: '', passwordConfirmation: '' });
  const [profile, setProfile] = useState(null);
  const [recommendationResult, setRecommendationResult] = useState(EMPTY_RECOMMENDATIONS);
  const recommendations = recommendationResult.recommendations || [];
  const rejectedRecommendations = recommendationResult.rejected || [];
  const [academicHistory, setAcademicHistory] = useState([]);
  const [curriculumCourses, setCurriculumCourses] = useState([]);
  const [curriculumLoaded, setCurriculumLoaded] = useState(false);
  const [curriculumError, setCurriculumError] = useState('');
  const [mentees, setMentees] = useState([]);
  const [adminAdvisors, setAdminAdvisors] = useState([]);
  const [lecturerForm, setLecturerForm] = useState({
    nip: '', full_name: '', username: '', email: '', password: '', passwordConfirmation: '',
  });
  const [lecturerFormVisible, setLecturerFormVisible] = useState(false);
  const [lecturerBusy, setLecturerBusy] = useState(false);
  const [editingLecturerNip, setEditingLecturerNip] = useState('');
  const [lecturerEditDraft, setLecturerEditDraft] = useState({});
  const [advisorDraft, setAdvisorDraft] = useState({});
  const [, setAdminSettings] = useState([]);
  const [adminAuditLogs, setAdminAuditLogs] = useState([]);
  const [advisorHistory, setAdvisorHistory] = useState([]);
  const [approvedPlans, setApprovedPlans] = useState([]);
  const [overrideReason, setOverrideReason] = useState({});
  const [overrideCourses, setOverrideCourses] = useState({});
  const [settingDraft, setSettingDraft] = useState({
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
  const [courseList, setCourseList] = useState([]);
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
  const [loginError, setLoginError] = useState('');
  const [authMessage, setAuthMessage] = useState('');
  const [profileDraft, setProfileDraft] = useState('Kecerdasan Bisnis');
  const [accountProfileDraft, setAccountProfileDraft] = useState({
    full_name: '', email: '', username: '', phone_number: '', program_study: '', angkatan: '',
  });
  const [passwordDraft, setPasswordDraft] = useState({ current_password: '', new_password: '', confirmation: '' });
  const [importStatus, setImportStatus] = useState('');
  const [khsPreview, setKhsPreview] = useState(null);
  const [khsFiles, setKhsFiles] = useState([]);
  const [khsBusy, setKhsBusy] = useState(false);
  const [khsError, setKhsError] = useState('');
  const [modelStatus, setModelStatus] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const downloadOfficialKrs = useCallback(async (planId) => {
    const token = localStorage.getItem('courseRecomToken');
    const response = await fetch(`${API_BASE}/mahasiswa/rencana-studi/${planId}/pdf-resmi`, {
      headers: token ? { Authorization: 'Bearer ' + token } : {},
    });
    expireSessionOnUnauthorized(response, token);
    if (!response.ok) throw new Error('PDF resmi belum tersedia.');
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/pdf')) {
      throw new Error('Respons server bukan dokumen PDF.');
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `KRS-${planId}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, []);
  const [toasts, setToasts] = useState([]);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  useEffect(() => {
    const handleExpiredSession = () => {
      setUser(null);
      setLoginError('Sesi telah berakhir. Silakan masuk kembali.');
      setLoading(false);
    };
    window.addEventListener('courserecom:session-expired', handleExpiredSession);
    return () => window.removeEventListener('courserecom:session-expired', handleExpiredSession);
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
  const [draftCourses, setDraftCourses] = useState(() => {
    try {
      const savedDraft = localStorage.getItem('courseRecomDraft');
      return savedDraft ? JSON.parse(savedDraft) : [];
    } catch {
      return [];
    }
  });

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
        const plans = await apiRequest('/mahasiswa/rencana-studi');
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
                ? parsed.courses
                : [],
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
          const dashboard = await apiRequest('/admin/dashboard');
          const lecturers = await apiRequest('/admin/lecturers');
          if (cancelled) return;
          setMentees(dashboard.students);
          setAdminAdvisors(lecturers);
        }

        if (user.role === 'admin') {
          const list = await apiRequest('/admin/courses');
          if (cancelled) return;
          setCourseList(list.map((course) => ({ ...course, _originalCode: course.code })));
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
      setUser(updated);
      await loadAccountProfile();
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
          angkatan: registrationForm.angkatan,
          password: registrationForm.password,
        }),
      });
      setForm({ username: registrationForm.nim.trim(), password: '' });
      setRegistrationForm({
        nim: '',
        username: '',
        full_name: '',
        program_study: '',
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
    setStudyPlans([]);
    setCourseList([]);
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
    try {
      await apiRequest(`/admin/study-plans/${planId}/override`, {
        method: 'PATCH',
        body: JSON.stringify({
          status,
          reason: reason.trim(),
          course_codes: courseCodesText.trim()
            ? courseCodesText.split(',').map((code) => code.trim().toUpperCase()).filter(Boolean)
            : null,
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
    if (!advisorNim) return;
    const reason = window.prompt('Alasan penetapan atau penggantian Dosen PA (opsional):') || '';
    try {
      await apiRequest(`/admin/students/${encodeURIComponent(studentNim)}/advisor`, {
        method: 'PATCH',
        body: JSON.stringify({ advisor_nim: advisorNim, reason }),
      });
      const dashboard = await apiRequest('/admin/dashboard');
      setMentees(dashboard.students);
      setAdvisorHistory(await apiRequest('/admin/advisor-history'));
      setActionMessage('Dosen PA berhasil ditetapkan.');
    } catch (error) {
      setActionMessage(error.message || 'Penetapan Dosen PA gagal.');
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
    try {
      await apiRequest('/mahasiswa/kprs', {
        method: 'POST',
        body: JSON.stringify({ study_plan_id: Number(kprsDraft.planId), course_codes: courses, reason: kprsDraft.reason.trim() }),
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
    } catch (error) {
      setImportStatus(error.message || 'Mata kuliah gagal dinonaktifkan.');
    } finally {
      setCourseBusyCode('');
    }
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
      preview.courses = preview.semesters.flatMap((semester) => semester.courses);
      setKhsPreview(preview);
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
      metadata: { ...previous.metadata, [field]: value },
    }));
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
            } : {}),
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

  const addPreviewSemester = () => {
    setKhsPreview((previous) => {
      const nextSemester = Math.max(0, ...previous.semesters.map((item) => Number(item.semester))) + 1;
      return {
        ...previous,
        semesters: [...previous.semesters, { semester: nextSemester, ip_semester: '', courses: [] }],
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
        numeric_grade: course.numeric_grade === '' ? null : course.numeric_grade,
        grade_point: course.grade_point,
      }));
      const currentSemester = Number(khsPreview.metadata.current_semester)
        || Math.max(...courses.map((course) => course.semester));
      const response = await apiRequest(`/mahasiswa/khs/${khsPreview.id}/confirm`, {
        method: 'POST',
        body: JSON.stringify({
          nim: khsPreview.metadata.nim,
          full_name: khsPreview.metadata.full_name,
          program_study: khsPreview.metadata.program_study || '',
          current_semester: currentSemester,
          ipk: khsPreview.metadata.ipk === '' ? null : khsPreview.metadata.ipk,
          ip_semesters: Object.fromEntries(khsPreview.semesters.map((semester) => [
            semester.semester,
            semester.ip_semester === '' ? null : semester.ip_semester,
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
  const interestDistribution = INTEREST_OPTIONS.map((interest) => ({
    name: interest,
    count: mentees.filter((student) => canonicalizeInterests(student.interests || '')
      .split(',')
      .includes(interest)).length,
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
    setDraftCourses([]);
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
      const plan = await apiRequest('/mahasiswa/rencana-studi', {
        method: 'POST',
        body: JSON.stringify({ course_codes: draftCourses.map((course) => course.code) }),
      });
      setStudyPlans((previousPlans) => [plan, ...previousPlans]);
      setDraftCourses([]);
      setActionMessage('Rencana studi berhasil diajukan ke dosen PA.');
    } catch (error) {
      setActionMessage(error.message || 'Pengajuan rencana studi gagal.');
    } finally {
      studyPlanSubmissionRef.current = false;
      setStudyPlanBusy(false);
    }
  };

  const reviewStudyPlan = async (planId, status) => {
    const advisorNote = reviewNotes[planId] ?? '';
    setStudyPlanBusy(true);
    setActionMessage('');
    try {
      const result = await apiRequest(`/dosen/rencana-studi/${planId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status, advisor_note: advisorNote }),
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
    if (!note.trim()) {
      setActionMessage('Catatan keputusan KPRS wajib diisi.');
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
                <label>IPK
                  <input type="number" min="0" max="4" step="0.01" value={khsPreview.metadata.ipk ?? ''} onChange={(event) => updatePreviewMetadata('ipk', event.target.value)} />
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
                    <label>IP semester
                      <input
                        type="number" min="0" max="4" step="0.01"
                        value={semester.ip_semester ?? ''}
                        onChange={(event) => updatePreviewSemester(semester.semester, 'ip_semester', event.target.value)}
                      />
                    </label>
                  </div>
                ))}
                <button className="btn outline" type="button" onClick={addPreviewSemester}>Tambah semester yang belum terbaca</button>
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
                    document.courses = document.courses || document.semesters.flatMap((semester) => semester.courses);
                    setKhsPreview(document);
                  }}>Lanjutkan pratinjau</button>}
                </div>
              ))
              : <p className="muted">Belum ada dokumen KHS.</p>}
          </section>
        </div>
      );
    }

    if (view === 'dashboard' && user.role === 'admin') {
      const confirmedKhsCount = mentees.filter((student) => student.khs_confirmed).length;
      return (
        <div className="card">
          <h2>Dashboard Admin Prodi</h2>
          <p className="muted">Ringkasan akun mahasiswa dan dosen PA yang terdaftar.</p>
          <div className="stat-grid">
            <div className="stat"><small>Total mahasiswa</small><strong>{mentees.length}</strong></div>
            <div className="stat"><small>KHS terkonfirmasi</small><strong>{confirmedKhsCount}</strong></div>
            <div className="stat"><small>Total dosen PA</small><strong>{adminAdvisors.length}</strong></div>
          </div>
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
                        <button className="btn outline" type="button" onClick={() => assignStudentAdvisor(student.nim)}>Simpan</button>
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
              </table>
            </div>
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
                      <td>{request.before.map((course) => `${course.code} (${course.sks} SKS)`).join(', ')}</td>
                      <td>{request.after.map((course) => `${course.code} (${course.sks} SKS)`).join(', ')}</td>
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
                      <td>{course.name}<br /><span className="muted">{course.code} · {course.category}</span></td>
                      <td>{course.sks}</td>
                      <td>{course.score}%</td>
                      <td>{course.prerequisite_text || '—'}</td>
                      <td>{(course.reasons || []).join('; ')}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              <label className="course-edit-field" style={{ marginTop: 14 }}>
                Catatan / arahan dosen PA
                <textarea
                  rows="3"
                  maxLength="2000"
                  value={reviewNotes[plan.id] ?? plan.advisor_note ?? ''}
                  onChange={(event) => setReviewNotes((previousNotes) => ({
                    ...previousNotes,
                    [plan.id]: event.target.value,
                  }))}
                />
              </label>
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
                    disabled={studyPlanBusy || !(reviewNotes[plan.id] ?? plan.advisor_note ?? '').trim()}
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
              {latestStudyPlan.advisor_note && <p><strong>Catatan dosen:</strong> {latestStudyPlan.advisor_note}</p>}
              {latestStudyPlan.status === 'approved' && (
                <button
                  type="button"
                  className="btn primary"
                  onClick={() => downloadOfficialKrs(latestStudyPlan.id).catch((error) => pushToast(error.message, 'error'))}
                >
                  Unduh PDF KRS Resmi
                </button>
              )}
            </div>
          )}
          {approvedStudyPlan && (
            <section className="study-plan-summary">
              <h3>Pengajuan Perubahan KRS (KPRS)</h3>
              <div className="course-edit-grid">
                <label className="course-edit-field"><span className="muted">KRS approved</span><select value={kprsDraft.planId} onChange={(event) => setKprsDraft((previous) => ({ ...previous, planId: event.target.value }))}><option value="">Pilih</option><option value={approvedStudyPlan.id}>KRS semester {approvedStudyPlan.semester}</option></select></label>
                <label className="course-edit-field"><span className="muted">Kode mata kuliah baru (pisahkan koma)</span><input value={kprsDraft.courses} onChange={(event) => setKprsDraft((previous) => ({ ...previous, courses: event.target.value }))} /></label>
                <label className="course-edit-field"><span className="muted">Alasan perubahan</span><textarea rows={3} value={kprsDraft.reason} onChange={(event) => setKprsDraft((previous) => ({ ...previous, reason: event.target.value }))} /></label>
              </div>
              <button className="btn primary" type="button" onClick={submitKprs}>Ajukan KPRS</button>
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
          {recommendations.length ? (
            <div className="recommendation-list">
              {recommendations.slice(0, 5).map((item) => (
                <div key={item.code} className="rec-item">
                  <strong>{item.name}</strong>
                  <div className="bar" aria-label={`Skor rekomendasi ${item.score}%`}><span style={{ width: `${item.score}%` }} /></div>
                  <strong>{item.score}%</strong>
                </div>
              ))}
            </div>
          ) : <p className="muted">{recommendationResult.message || 'Belum ada kandidat yang lolos aturan akademik.'}</p>}
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
                <p className="muted model-caption">
                  Model {recommendationResult.model.version} · {recommendationResult.model.method} · {recommendationResult.model.peer_count} mahasiswa serupa
                </p>
              )}
              <h3>Kandidat yang lolos aturan akademik</h3>
              {recommendations.length ? recommendations.map((item) => (
                <article className="recommendation-card" key={item.code}>
                  <div className="recommendation-heading">
                    <div>
                      <h4>{item.name}</h4>
                      <span className="muted">{item.code} · {item.sks} SKS · Semester {item.semester} · {item.category}</span>
                    </div>
                    <strong className="score-badge">{item.score}%</strong>
                  </div>
                  {item.description && <p>{item.description}</p>}
                  {item.prerequisite_text && (
                    <p><strong>Prasyarat:</strong><br />{item.prerequisite_text.split('\n').map((line, index) => (
                      <span key={`${item.code}-prerequisite-${index}`}>{line}<br /></span>
                    ))}</p>
                  )}
                  <div className="factor-grid">
                    {Object.entries(item.factors || {}).map(([factor, score]) => (
                      <div className="factor" key={factor}>
                        <span>{factor.replaceAll('_', ' ')}</span><strong>{score}%</strong>
                      </div>
                    ))}
                  </div>
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
              )) : <p className="muted">Tidak ada mata kuliah semester target yang lolos aturan. Periksa riwayat KHS dan kurikulum.</p>}
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
              <ul>
                {draftCourses.map((course) => (
                  <li key={course.code} style={{ marginBottom: 8 }}>
                    {course.code} — {course.name} ({course.sks} SKS)
                    <button type="button" className="btn outline" style={{ marginLeft: 8 }} disabled={Boolean(approvedStudyPlan)} onClick={() => removeFromDraft(course.code)}>
                      Hapus
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {draftCourses.length > 0 && (
              <div className="preview-actions">
                <button type="button" className="btn outline" disabled={Boolean(approvedStudyPlan)} onClick={clearDraft}>Kosongkan Draft</button>
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
            : academicHistory.filter((doc) => doc.status === 'confirmed').map((doc) => (
              <section className="history-document" key={doc.id}>
                <h3>{doc.filename} · {doc.metadata.current_semester} semester</h3>
                {doc.semesters.map((semester) => (
                  <div key={semester.semester}>
                    <h4>Semester {semester.semester} · {semester.courses.length} mata kuliah · IP semester {semester.ip_semester ?? '—'}</h4>
                    <div className="table-wrap"><table className="table">
                      <thead><tr><th>Kode</th><th>Mata kuliah</th><th>SKS</th><th>Nilai angka</th><th>Grade</th></tr></thead>
                      <tbody>{semester.courses.map((course, index) => (
                        <tr key={`${course.code}-${index}`}><td>{course.code}</td><td>{course.name}</td><td>{course.sks}</td><td>{course.numeric_grade ?? '—'}</td><td>{course.grade}</td></tr>
                      ))}</tbody>
                    </table></div>
                  </div>
                ))}
              </section>
            ))}
          <button type="button" className="btn primary" onClick={() => setView('khs')}>Unggah KHS terbaru</button>
        </div>
      );
    }

    if (view === 'minat') {
      return (
        <div className="card">
          <h3>Minat & Profil</h3>
          <p className="muted">Pilih satu atau kedua peminatan. Pilihan ini memengaruhi skor kecocokan mata kuliah pada rekomendasi.</p>
          <div className="interest-options">{INTEREST_OPTIONS.map((interest) => {
            const selected = profileDraft.split(',').map((item) => item.trim()).includes(interest);
            return (
              <label className="interest-option" key={interest}>
                <input
                  type="checkbox"
                  checked={selected}
                  onChange={() => {
                    const selectedInterests = profileDraft.split(',').map((item) => item.trim()).filter(Boolean);
                    const next = selected
                      ? selectedInterests.filter((item) => item !== interest)
                      : [...selectedInterests, interest];
                    setProfileDraft(next.join(','));
                  }}
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
      return <div className="card"><h3>CourseRecom</h3><p>Deskripsi: aplikasi berbasis AI yang merekomendasikan mata kuliah pilihan dan semester berikutnya kepada mahasiswa.</p><h4>Masalah & Tujuan</h4><p>Masalah dan tujuan disiapkan dalam halaman ini sesuai proposal produk.</p><h4>Alur Aplikasi</h4><ol><li>Data Mahasiswa</li><li>Preprocessing</li><li>Model Rekomendasi</li><li>Validasi Aturan</li><li>Daftar Rekomendasi + Alasan</li><li>Dashboard Mahasiswa & Dosen PA</li></ol></div>;
    }

    if (view === 'panduan') {
      return <div className="card"><h3>Panduan Pengguna</h3><ul><li>Mahasiswa: cek rekomendasi dan draft KRS.</li><li>Dosen PA: review dan setujui.</li><li>Admin Prodi: kelola kurikulum dan impor data.</li></ul></div>;
    }

    if (view === 'akun-dosen' && user.role === 'admin') {
      return (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <div>
              <h2>Akun Dosen PA</h2>
              <p className="muted">Tambah, ubah, dan hapus akun dosen pembimbing akademik.</p>
            </div>
            <button className="btn primary" type="button" onClick={() => setLecturerFormVisible((visible) => !visible)}>
              {lecturerFormVisible ? 'Batal' : 'Daftarkan akun dosen PA'}
            </button>
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

    if (view === 'admin') {
      const courseFields = [
        ['code', 'Kode'], ['name', 'Nama mata kuliah'], ['sks', 'SKS'],
        ['semester', 'Semester utama'], ['available_semesters', 'Semester tersedia (pisahkan koma)'],
        ['category', 'Kategori'], ['prerequisite_text', 'Prasyarat/kriteria'],
        ['prerequisite_codes', 'Kode prasyarat yang harus lulus'],
        ['description', 'Keterangan'], ['day', 'Hari'], ['time', 'Waktu'],
        ['capacity', 'Kuota kelas'],
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
          <section style={{ marginTop: 20 }}>
            <h3>Periode dan Batas Akademik</h3>
            <div className="course-edit-grid">
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
              <table>
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
                          placeholder="Kode MK baru (opsional)"
                          aria-label={`Mata kuliah override ${plan.student_name || plan.student_id}`}
                        />
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
            </table>
          </div>
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
        <div className="login-box">
          <div style={{ textAlign: 'center', marginBottom: 16 }}>
            <img src="/logo.png" alt="CourseRecom logo" style={{ width: 99, height: 99 }} />
            <h2 style={{ marginTop: 10 }}>CourseRecom</h2>
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
                  <input maxLength="120" value={registrationForm.program_study} onChange={(e) => setRegistrationForm({ ...registrationForm, program_study: e.target.value })} />
                </label>
                <label>
                  <span className="muted">Angkatan</span>
                  <input maxLength="20" inputMode="numeric" value={registrationForm.angkatan} onChange={(e) => setRegistrationForm({ ...registrationForm, angkatan: e.target.value })} />
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
      <div className="toast-viewport" aria-live="polite">
        {toasts.map((toast) => <ToastItem key={toast.id} toast={toast} onDismiss={dismissToast} />)}
      </div>
    </div>
  );
}

export default App;
