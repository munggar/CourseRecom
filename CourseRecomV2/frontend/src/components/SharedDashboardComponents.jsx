import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

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

function GuideStep({ index, children }) {
  return (
    <li className="guide-step">
      <span className="guide-step-number">{String(index + 1).padStart(2, '0')}</span>
      <span>{children}</span>
    </li>
  );
}
