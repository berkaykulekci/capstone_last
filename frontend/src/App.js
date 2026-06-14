import { useEffect, useMemo, useState, useRef } from 'react';
import './App.css';
import {
  PieChart, Pie, Cell, Tooltip as RechartTooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from 'recharts';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function apiUrl(path) {
  if (!path) return '';
  return path.startsWith('http') ? path : `${API_BASE}${path}`;
}

function initials(name) {
  return (name || 'A').trim().charAt(0).toUpperCase();
}

function riskClass(risk) {
  const value = (risk || '').toLowerCase();
  if (value === 'high') return 'risk-high';
  if (value === 'moderate') return 'risk-moderate';
  if (value === 'low') return 'risk-low';
  return 'risk-empty';
}

function AuthScreen({ onAuth }) {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');

    try {
      if (mode === 'register') {
        const registerRes = await fetch(`${API_BASE}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
        if (!registerRes.ok) {
          const body = await registerRes.json();
          throw new Error(body.detail || 'Kayıt oluşturulamadı.');
        }
      }

      const form = new URLSearchParams();
      form.append('username', email);
      form.append('password', password);
      const loginRes = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form,
      });
      const body = await loginRes.json();
      if (!loginRes.ok) throw new Error(body.detail || 'Giriş başarısız.');
      onAuth(body.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      {/* LEFT SIDE: Visuals & Hover Scanner */}
      <div className="auth-visual-side">
        {/* Scanner Line Effect */}
        <div className="scanner-line" />

        {/* Background Image */}
        <img
          src="/runner.png"
          alt="Biomechanical Runner"
          className="auth-video-bg"
        />

        {/* Gradient overlay */}
        <div className="auth-gradient-overlay" />

        {/* Brand Overlay */}
        <div className="brand-overlay">
          <h1 className="brand-title">KINETIC</h1>
          <p className="brand-subtitle">Performans Sistemleri</p>
        </div>
      </div>

      {/* RIGHT SIDE: Form card */}
      <div className="auth-form-side bg-tech-grid">
        {/* Glow effect in background */}
        <div className="card-glowing-glow" />

        <div className="glass-card">
          <header className="auth-form-header">
            <h2>{mode === 'login' ? 'Doktor Girişi' : 'Doktor Kaydı'}</h2>
            <p>
              {mode === 'login'
                ? 'Klinik analiz ve sporcu performans modülüne erişmek için kimlik bilgilerinizi doğrulayın.'
                : 'Klinik analiz ve sporcu takip panelini kullanmak için yeni bir doktor hesabı oluşturun.'}
            </p>
          </header>

          <form onSubmit={submit} className="auth-form-body">
            {/* Email Input */}
            <div className="form-group">
              <label htmlFor="email">E-posta Adresi</label>
              <div className="input-wrapper">
                <span className="material-symbols-outlined">mail</span>
                <input
                  id="email"
                  type="email"
                  placeholder="dr.isim@klinik.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            </div>

            {/* Password Input */}
            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label htmlFor="password">Şifre</label>
              </div>
              <div className="input-wrapper">
                <span className="material-symbols-outlined">lock</span>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  aria-label="Şifreyi Göster"
                  className="password-toggle-btn"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  <span className="material-symbols-outlined">
                    {showPassword ? 'visibility' : 'visibility_off'}
                  </span>
                </button>
              </div>
            </div>

            {/* Error Banner */}
            {error && <div className="error-banner" style={{ marginTop: '16px' }}>{error}</div>}

            {/* Submit Button */}
            <button className="submit-btn" disabled={busy} type="submit">
              <span className="submit-btn-glow" />
              <span style={{ position: 'relative', zIndex: 1 }}>
                {busy ? 'Lütfen bekleyin...' : mode === 'login' ? 'Giriş Yap' : 'Kayıt Ol'}
              </span>
              <span className="material-symbols-outlined" style={{ position: 'relative', zIndex: 1, fontSize: '18px' }}>
                arrow_forward
              </span>
            </button>
          </form>

          {/* Form switch footer */}
          <footer className="auth-form-footer">
            <p>
              {mode === 'login' ? 'Sisteme kaydolmak mı istiyorsunuz?' : 'Zaten bir hesabınız var mı?'}
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  setError('');
                  setMode(mode === 'login' ? 'register' : 'login');
                }}
                style={{ marginLeft: '4px' }}
              >
                {mode === 'login' ? 'Hesap Oluşturun' : 'Giriş Yapın'}
              </a>
            </p>
          </footer>
        </div>
      </div>
    </main>
  );
}

function ConfirmModal({ message, onConfirm, onCancel }) {
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
        <p>{message}</p>
        <div className="confirm-modal-actions">
          <button className="secondary-button" onClick={onCancel}>İptal</button>
          <button className="danger-button confirm-danger-btn" onClick={onConfirm}>Sil</button>
        </div>
      </div>
    </div>
  );
}

function CreateAthleteModal({ onClose, onCreate }) {
  const [name, setName] = useState('');
  const [sport, setSport] = useState('');
  const [team, setTeam] = useState('');

  async function submit(event) {
    event.preventDefault();
    try {
      await onCreate({ name, sport, team });
    } catch (err) {
      alert("Error: " + err.message);
    }
  }

  return (
    <div className="modal-backdrop">
      <form className="athlete-modal" onSubmit={submit}>
        <h2>Add New Athlete</h2>
        <label>Name *</label>
        <input placeholder="Full name" value={name} onChange={(event) => setName(event.target.value)} required />
        <div className="modal-grid">
          <label>
            Sport
            <input placeholder="e.g. Soccer" value={sport} onChange={(event) => setSport(event.target.value)} />
          </label>
          <label>
            Team
            <input placeholder="e.g. FC Barcelona" value={team} onChange={(event) => setTeam(event.target.value)} />
          </label>
        </div>
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onClose}>Cancel</button>
          <button type="submit" className="primary-button">Create Athlete</button>
        </div>
      </form>
    </div>
  );
}

function Sidebar({ user, onDashboard, onStatistics, onSignOut, activePage }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark small">K</div>
        <strong>Kinetic</strong>
      </div>
      <button
        className={`nav-item${activePage === 'dashboard' ? ' active' : ''}`}
        onClick={onDashboard}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 17, verticalAlign: 'middle', marginRight: 8 }}>dashboard</span>
        Dashboard
      </button>
      <button
        className={`nav-item${activePage === 'statistics' ? ' active' : ''}`}
        onClick={onStatistics}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 17, verticalAlign: 'middle', marginRight: 8 }}>bar_chart</span>
        İstatistikler
      </button>
      <div className="sidebar-user">
        <div className="avatar small-avatar">{initials(user?.email)}</div>
        <div>
          <span>Signed in as</span>
          <strong>{user?.email}</strong>
        </div>
        <button className="danger-button" onClick={onSignOut}>Sign out</button>
      </div>
    </aside>
  );
}

function Dashboard({ athletes, onAdd, onSelect }) {
  const stats = useMemo(() => {
    const high = athletes.filter((item) => item.latest_analysis?.risk === 'High').length;
    const moderate = athletes.filter((item) => item.latest_analysis?.risk === 'Moderate').length;
    const low = athletes.length - high - moderate;
    return { high, moderate, low };
  }, [athletes]);

  return (
    <main className="main-panel">
      <header className="topbar">
        <div>
          <h1>Athlete Dashboard</h1>
          <p>{athletes.length} athletes assigned</p>
        </div>
        <div className="topbar-actions">
          <button className="secondary-button">Join via Code</button>
          <button className="primary-button" onClick={onAdd}>+ Add Athlete</button>
        </div>
      </header>

      <section className="stat-grid">
        <div className="stat-card"><strong>{athletes.length}</strong><span>Total Athletes</span></div>
        <div className="stat-card red"><strong>{stats.high}</strong><span>High Risk</span></div>
        <div className="stat-card amber"><strong>{stats.moderate}</strong><span>Moderate Risk</span></div>
        <div className="stat-card green"><strong>{stats.low}</strong><span>Low / No Data</span></div>
      </section>

      <section className="athlete-list">
        {athletes.map((athlete) => (
          <button key={athlete.id} className="athlete-row" onClick={() => onSelect(athlete)}>
            <div className="avatar">{initials(athlete.name)}</div>
            <div className="athlete-copy">
              <strong>{athlete.name}</strong>
              <span>{athlete.sport || '-'} · {athlete.team || '-'}</span>
            </div>
            <div className="row-tags">
              <span className={`pill ${riskClass(athlete.latest_analysis?.risk)}`}>
                {athlete.latest_analysis?.risk || 'No data'}
              </span>
              {athlete.latest_analysis?.status && <span className="pill blue">{athlete.latest_analysis.status}</span>}
            </div>
          </button>
        ))}
        {athletes.length === 0 && <div className="empty-state">No athletes yet.</div>}
      </section>
    </main>
  );
}

function VideoUploadCard({ label, file, onChange }) {
  const [videoUrl, setVideoUrl] = useState(null);

  useEffect(() => {
    if (!file) { setVideoUrl(null); return; }
    const url = URL.createObjectURL(file);
    setVideoUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return (
    <div className="video-upload-card">
      <div className="video-card-header-row">
        <h3 className="video-card-title">{label}</h3>
        {file && (
          <span className="material-symbols-outlined video-check-icon" style={{ fontSize: 16 }}>
            check_circle
          </span>
        )}
      </div>

      {videoUrl ? (
        /* ── File selected: full video player + compact replace strip ── */
        <>
          <div className="video-preview-area has-video">
            <video
              key={videoUrl}
              src={videoUrl}
              controls
              className="video-preview-player"
            />
          </div>
          <label className="video-replace-strip" htmlFor={`vup-${label}`}>
            <input
              id={`vup-${label}`}
              type="file"
              accept="video/mp4,video/quicktime,video/x-msvideo,.mp4,.mov,.MOV,.avi"
              onChange={(e) => onChange(e.target.files?.[0] || null)}
            />
            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>upload</span>
            <span className="video-filename-inline">{file.name}</span>
            <span className="upload-zone-browse-btn" style={{ marginLeft: 'auto' }}>REPLACE</span>
          </label>
        </>
      ) : (
        /* ── No file: large upload zone with placeholder ── */
        <label className="video-upload-zone-inner empty" htmlFor={`vup-${label}`}>
          <input
            id={`vup-${label}`}
            type="file"
            accept="video/mp4,video/quicktime,video/x-msvideo,.mp4,.mov,.MOV,.avi"
            onChange={(e) => onChange(e.target.files?.[0] || null)}
          />
          <span className="material-symbols-outlined upload-zone-icon-lg">videocam</span>
          <span className="upload-zone-text">Drop a video or click to browse</span>
          <span className="upload-zone-sub">MP4, MOV, AVI</span>
          <span className="upload-zone-browse-btn" style={{ marginTop: 4 }}>BROWSE</span>
        </label>
      )}
    </div>
  );
}


const MODEL_OPTIONS = [
  { id: 'mediapipe', label: 'MediaPipe', subLabel: 'Standard', note: 'Auto-detects test side via Z-coord. All 17 items exact. Max score: 19.', latency: '~25ms', precision: '95%' },
  { id: 'yolo', label: 'YOLO Pose', subLabel: 'Fast Track', note: 'No heel/toe landmarks → M4, M9, M10 approximated. Max score: 19, approximate items flagged in CSV.', latency: '~12ms', precision: '92%' },
  { id: 'rtm', label: 'RTMPose', subLabel: 'High Fidelity', note: 'Heel + toe landmarks present → all 17 items exact (M4/M9/M10 included). Max score: 19.', latency: '~45ms', precision: '98%' },
];

function EngineModelSelector({ selected, onChange }) {
  function toggle(id) {
    if (selected.includes(id)) {
      if (selected.length === 1) return;
      onChange(selected.filter((m) => m !== id));
    } else {
      onChange([...selected, id]);
    }
  }
  return (
    <div className="engine-model-selector">
      <span className="engine-section-label">Estimation Model</span>
      <div className="engine-model-list">
        {MODEL_OPTIONS.map(({ id, label, subLabel, latency, precision }) => {
          const isSelected = selected.includes(id);
          return (
            <label key={id} className={`engine-model-item${isSelected ? ' selected' : ''}`}>
              <input type="checkbox" checked={isSelected} onChange={() => toggle(id)} />
              <div className={`engine-model-indicator${isSelected ? ' selected' : ''}`}>
                {isSelected && <div className="engine-model-dot" />}
              </div>
              <div className="engine-model-info">
                <div className="engine-model-name">
                  {label}
                  <span className="engine-model-tag">{subLabel}</span>
                </div>
                <div className="engine-model-meta">Latency: {latency} | Precision: {precision}</div>
              </div>
            </label>
          );
        })}
      </div>
      {selected.length > 1 && (
        <p className="engine-multi-note">Running {selected.length} models — results will be compared side-by-side.</p>
      )}
    </div>
  );
}

function AnalyseProgress({ onClick, busy }) {
  return (
    <div
      className={`analyse-btn-wrap${busy ? ' is-analyzing' : ''}`}
      onClick={!busy ? onClick : undefined}
    >
      <div className="analyse-btn-idle">
        <span className="material-symbols-outlined" style={{ fontSize: 18 }}>science</span>
        INITIATE ANALYSIS
      </div>
      <div className="analyse-btn-progress">
        <div className="analyse-progress-top">
          <span>Analyzing Biometrics...</span>
          <span>Processing</span>
        </div>
        <div className="analyse-progress-track-wrap">
          <div className="analyse-stickman">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <circle cx="14" cy="4" r="3" />
              <line x1="14" y1="7" x2="10" y2="14" />
              <line className="sprint-arm-l" x1="14" y1="7" x2="8" y2="11" />
              <line className="sprint-arm-r" x1="14" y1="7" x2="20" y2="11" />
              <line className="sprint-leg-l" x1="10" y1="14" x2="6" y2="21" />
              <line className="sprint-leg-r" x1="10" y1="14" x2="16" y2="21" />
            </svg>
          </div>
          <div className="analyse-progress-bar">
            <div className="analyse-progress-fill" />
          </div>
        </div>
      </div>
    </div>
  );
}

function TestSideSelect({ value, onChange }) {
  return (
    <div className="test-side-select">
      <span className="model-toggle-label">Test Leg</span>
      <div className="model-toggle-buttons">
        <button
          type="button"
          className={value === 'right' ? 'model-btn active' : 'model-btn'}
          onClick={() => onChange('right')}
        >
          Right
        </button>
        <button
          type="button"
          className={value === 'left' ? 'model-btn active' : 'model-btn'}
          onClick={() => onChange('left')}
        >
          Left
        </button>
      </div>
      <p className="model-note">Which leg faces the side camera? (required for YOLO / RTMPose)</p>
    </div>
  );
}

// Groups analyses submitted in the same minute into comparison batches.
// Analyses arrive sorted newest-first; we reverse, group, then re-reverse.
// Groups analyses submitted within 10 seconds of each other into comparison batches.
// Uses actual timestamp diff instead of minute-key to avoid false grouping of
// separate single-model runs that happen to fall within the same clock minute.
function groupAnalyses(analyses) {
  if (!analyses.length) return [];
  const asc = [...analyses].reverse();
  const groups = [];
  let current = [asc[0]];
  for (let i = 1; i < asc.length; i++) {
    const diff = Math.abs(
      new Date(asc[i].created_at).getTime() - new Date(current[0].created_at).getTime()
    );
    if (diff <= 10000) { // within 10 seconds → same batch
      current.push(asc[i]);
    } else {
      groups.push(current);
      current = [asc[i]];
    }
  }
  groups.push(current);
  return groups.reverse();
}

function ModelBadge({ model }) {
  const m = (model || '').toLowerCase();
  const label = m === 'yolo' ? 'YOLO' : m === 'rtm' ? 'RTMPose' : 'MediaPipe';
  const colored = m === 'yolo' || m === 'rtm';
  return (
    <span className={`pill ${colored ? 'blue' : ''}`} style={{ fontSize: 11 }}>
      {label}
    </span>
  );
}

function AnalysisCard({ analysis, athleteName, onError, onDelete, compact }) {
  const date = new Date(analysis.created_at).toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });

  async function downloadCsv() {
    try {
      const res = await fetch(apiUrl(analysis.csv_url));
      if (!res.ok) throw new Error('CSV could not be downloaded');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${athleteName.replace(/\s+/g, '_')}_${analysis.id}_less.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      onError(err.message);
    }
  }

  return (
    <div className={`analysis-card${compact ? ' compact' : ''}`}>
      <div className="analysis-card-header">
        <div className="analysis-card-meta">
          <ModelBadge model={analysis.pose_model} />
          <span className={`pill ${riskClass(analysis.risk)}`}>{analysis.risk || 'No data'}</span>
          <strong className="analysis-score">
            {analysis.total_score ?? '-'} <span>puan</span>
          </strong>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {!compact && <small>{date}</small>}
          {onDelete && (
            <button
              type="button"
              className="delete-analysis-btn"
              onClick={() => onDelete(analysis.id)}
              title="Analizi Sil"
            >
              Sil
            </button>
          )}
        </div>
      </div>
      <div className="output-grid">
        {analysis.csv_url && (
          <button type="button" onClick={downloadCsv}>CSV Rapor</button>
        )}
        {analysis.side_output_url && (
          <a href={apiUrl(analysis.side_output_url)} target="_blank" rel="noreferrer">Yan Video</a>
        )}
        {analysis.front_output_url && (
          <a href={apiUrl(analysis.front_output_url)} target="_blank" rel="noreferrer">Ön Video</a>
        )}
        {!analysis.csv_url && !analysis.side_output_url && !analysis.front_output_url && (
          <span style={{ color: 'var(--muted)', fontSize: 13 }}>
            {analysis.status === 'failed' ? 'Analiz başarısız.' : 'Çıktı yok.'}
          </span>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   STATISTICS PAGE
   ═══════════════════════════════════════════════════════════ */
const RISK_COLORS = { High: '#ef4444', Moderate: '#f5b51b', Low: '#37c563', 'No data': '#455264' };
const MODEL_COLORS = { mediapipe: '#10b7df', yolo: '#a855f7', rtm: '#f97316' };

function StatKpiCard({ icon, label, value, sub, accent }) {
  return (
    <div className="stats-kpi-card" style={{ borderLeftColor: accent || 'var(--cyan)' }}>
      <span className="material-symbols-outlined stats-kpi-icon" style={{ color: accent || 'var(--cyan)' }}>{icon}</span>
      <div className="stats-kpi-body">
        <strong className="stats-kpi-value">{value}</strong>
        <span className="stats-kpi-label">{label}</span>
        {sub && <span className="stats-kpi-sub">{sub}</span>}
      </div>
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="recharts-custom-tooltip">
      {label && <p className="recharts-tip-label">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || p.fill, margin: '2px 0' }}>
          {p.name}: <strong>{p.value}</strong>
        </p>
      ))}
    </div>
  );
}

function StatisticsPage({ token, athletes }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const res = await fetch(`${API_BASE}/athletes/statistics`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error('Veriler yüklenemedi.');
        const data = await res.json();
        setStats(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  if (loading) {
    return (
      <main className="main-panel">
        <div className="processing-state" style={{ minHeight: '60vh' }}>
          <div className="spinner" />
          <strong>İstatistikler yükleniyor...</strong>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="main-panel">
        <div className="error-banner" style={{ marginTop: 40 }}>{error}</div>
      </main>
    );
  }

  if (!stats) return null;

  /* ── Derived chart data ── */
  const riskData = Object.entries(stats.risk_distribution)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));

  const scoreDistData = Object.entries(stats.score_distribution).map(([name, value]) => ({ name, value }));

  const modelData = Object.entries(stats.model_usage).map(([name, value]) => ({
    name: name === 'mediapipe' ? 'MediaPipe' : name === 'yolo' ? 'YOLO' : 'RTMPose',
    value,
    key: name,
  }));

  // Group timeline by date, average score per date
  const timelineMap = {};
  for (const entry of stats.score_timeline) {
    if (!timelineMap[entry.date]) timelineMap[entry.date] = [];
    timelineMap[entry.date].push(entry.score);
  }
  const timelineData = Object.entries(timelineMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, scores]) => ({
      date,
      avg: Math.round((scores.reduce((s, v) => s + v, 0) / scores.length) * 10) / 10,
      count: scores.length,
    }));

  const avgScore = stats.athlete_summaries.length
    ? (stats.athlete_summaries.reduce((s, a) => s + (a.avg_score || 0), 0) / stats.athlete_summaries.filter(a => a.avg_score !== null).length)
    : null;

  const highRiskCount = stats.risk_distribution['High'] || 0;

  return (
    <main className="main-panel stats-page">
      {/* Header */}
      <header className="topbar" style={{ marginBottom: 28 }}>
        <div>
          <h1>İstatistikler</h1>
          <p>Tüm sporcular için toplam analiz verileri</p>
        </div>
      </header>

      {/* KPI Row */}
      <section className="stats-kpi-grid">
        <StatKpiCard icon="group" label="Toplam Sporcu" value={stats.total_athletes} accent="var(--cyan)" />
        <StatKpiCard icon="science" label="Toplam Analiz" value={stats.total_analyses} accent="#a855f7" />
        <StatKpiCard
          icon="monitor_heart"
          label="Ort. Skor"
          value={avgScore !== null && !isNaN(avgScore) ? avgScore.toFixed(1) : '—'}
          sub="/ 19 puan"
          accent="var(--green)"
        />
        <StatKpiCard icon="warning" label="Yüksek Risk" value={highRiskCount} accent="var(--red)" />
      </section>

      {/* Charts Row 1: Risk Donut + Score Distribution */}
      <section className="stats-charts-row">
        {/* Risk Donut */}
        <div className="stats-chart-card">
          <h3 className="stats-chart-title">Risk Dağılımı</h3>
          {riskData.length === 0 ? (
            <div className="empty-state" style={{ minHeight: 220 }}>Henüz analiz yok.</div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={riskData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {riskData.map((entry) => (
                    <Cell key={entry.name} fill={RISK_COLORS[entry.name] || '#455264'} />
                  ))}
                </Pie>
                <RechartTooltip content={<CustomTooltip />} />
                <Legend
                  formatter={(value) => <span style={{ color: 'var(--muted)', fontSize: 12 }}>{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Score Distribution Bar */}
        <div className="stats-chart-card">
          <h3 className="stats-chart-title">Skor Dağılımı</h3>
          {stats.total_analyses === 0 ? (
            <div className="empty-state" style={{ minHeight: 220 }}>Henüz analiz yok.</div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={scoreDistData} barCategoryGap="30%">
                <CartesianGrid strokeDasharray="3 3" stroke="#2b333f" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <RechartTooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(16,183,223,0.07)' }} />
                <Bar dataKey="value" name="Analiz" radius={[4, 4, 0, 0]}>
                  {scoreDistData.map((entry, i) => {
                    const colors = ['#ef4444', '#f5b51b', '#10b7df', '#37c563'];
                    return <Cell key={i} fill={colors[i % colors.length]} />;
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Model Usage */}
        <div className="stats-chart-card">
          <h3 className="stats-chart-title">Model Kullanımı</h3>
          {modelData.length === 0 ? (
            <div className="empty-state" style={{ minHeight: 220 }}>Henüz analiz yok.</div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={modelData} layout="vertical" barCategoryGap="25%">
                <CartesianGrid strokeDasharray="3 3" stroke="#2b333f" horizontal={false} />
                <XAxis type="number" tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <YAxis type="category" dataKey="name" tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={false} tickLine={false} width={72} />
                <RechartTooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(16,183,223,0.07)' }} />
                <Bar dataKey="value" name="Analiz" radius={[0, 4, 4, 0]}>
                  {modelData.map((entry) => (
                    <Cell key={entry.key} fill={MODEL_COLORS[entry.key] || '#10b7df'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      {/* Score Timeline */}
      {timelineData.length > 0 && (
        <section className="stats-chart-card stats-chart-wide">
          <h3 className="stats-chart-title">Zaman İçinde Ortalama Skor</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={timelineData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2b333f" />
              <XAxis dataKey="date" tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 19]} tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <RechartTooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="avg"
                name="Ort. Skor"
                stroke="var(--cyan)"
                strokeWidth={2.5}
                dot={{ fill: 'var(--cyan)', r: 4, strokeWidth: 0 }}
                activeDot={{ r: 6, fill: 'var(--cyan)' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </section>
      )}

      {/* Sport Breakdown Table */}
      {stats.sport_summary.length > 0 && (
        <section className="stats-table-card">
          <h3 className="stats-chart-title">Spora Göre Dağılım</h3>
          <div className="stats-table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Spor</th>
                  <th>Analiz</th>
                  <th>Ort. Skor</th>
                  <th>Yüksek Risk</th>
                  <th>Orta Risk</th>
                  <th>Düşük Risk</th>
                </tr>
              </thead>
              <tbody>
                {stats.sport_summary.map((row) => (
                  <tr key={row.sport}>
                    <td><strong>{row.sport}</strong></td>
                    <td>{row.analyses}</td>
                    <td>{row.avg_score !== null ? row.avg_score : '—'}</td>
                    <td><span className="pill risk-high" style={{ fontSize: 11 }}>{row.high}</span></td>
                    <td><span className="pill risk-moderate" style={{ fontSize: 11 }}>{row.moderate}</span></td>
                    <td><span className="pill risk-low" style={{ fontSize: 11 }}>{row.low}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Athlete Summary Table */}
      {stats.athlete_summaries.length > 0 && (
        <section className="stats-table-card">
          <h3 className="stats-chart-title">Sporcu Özeti</h3>
          <div className="stats-table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Sporcu</th>
                  <th>Spor / Takım</th>
                  <th>Analizler</th>
                  <th>Ort. Skor</th>
                  <th>Son Skor</th>
                  <th>Son Risk</th>
                  <th>Son Model</th>
                </tr>
              </thead>
              <tbody>
                {stats.athlete_summaries.map((a) => (
                  <tr key={a.id}>
                    <td><strong>{a.name}</strong></td>
                    <td style={{ color: 'var(--muted)', fontSize: 12 }}>{a.sport || '—'} {a.team ? `· ${a.team}` : ''}</td>
                    <td>{a.total_analyses}</td>
                    <td>{a.avg_score !== null ? a.avg_score : '—'}</td>
                    <td>{a.latest_score !== null && a.latest_score !== undefined ? a.latest_score : '—'}</td>
                    <td>
                      {a.latest_risk ? (
                        <span className={`pill ${riskClass(a.latest_risk)}`} style={{ fontSize: 11 }}>{a.latest_risk}</span>
                      ) : <span style={{ color: 'var(--muted)', fontSize: 12 }}>—</span>}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--muted)' }}>
                      {a.latest_model ? (a.latest_model === 'yolo' ? 'YOLO' : a.latest_model === 'rtm' ? 'RTMPose' : 'MediaPipe') : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}

function AthleteDetail({ athlete, onBack, onAnalysed, onDeleteAthlete }) {
  const [sideFile, setSideFile] = useState(null);
  const [frontFile, setFrontFile] = useState(null);
  const [poseModels, setPoseModels] = useState(['mediapipe']);
  const [testSide, setTestSide] = useState('right');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirmAnalysisId, setConfirmAnalysisId] = useState(null);
  const [confirmDeleteAthlete, setConfirmDeleteAthlete] = useState(false);

  const needsTestSide = poseModels.some((m) => m === 'yolo' || m === 'rtm');

  async function analyse() {
    if (!sideFile || !frontFile) {
      setError('Side and front videos are required.');
      return;
    }
    setBusy(true);
    setError('');
    const form = new FormData();
    form.append('side_video', sideFile);
    form.append('front_video', frontFile);
    form.append('pose_models', poseModels.join(','));
    form.append('test_side', testSide);

    try {
      const token = localStorage.getItem('sportsmd_token');
      const res = await fetch(`${API_BASE}/athletes/${athlete.id}/analyse`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Analysis failed');
      onAnalysed();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function doDeleteAnalysis(analysisId) {
    setConfirmAnalysisId(null);
    setBusy(true);
    setError('');
    try {
      const token = localStorage.getItem('sportsmd_token');
      const res = await fetch(`${API_BASE}/athletes/${athlete.id}/analyses/${analysisId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.detail || 'Analysis deletion failed');
      }
      onAnalysed();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function doDeleteAthlete() {
    setConfirmDeleteAthlete(false);
    setBusy(true);
    setError('');
    try {
      const token = localStorage.getItem('sportsmd_token');
      const res = await fetch(`${API_BASE}/athletes/${athlete.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.detail || 'Athlete deletion failed');
      }
      onDeleteAthlete();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  const analyses = athlete.analyses || [];
  const latest = athlete.latest_analysis;

  return (
    <main className="detail-layout">
      {confirmAnalysisId && (
        <ConfirmModal
          message="Bu analizi silmek istediğinizden emin misiniz?"
          onConfirm={() => doDeleteAnalysis(confirmAnalysisId)}
          onCancel={() => setConfirmAnalysisId(null)}
        />
      )}
      {confirmDeleteAthlete && (
        <ConfirmModal
          message={`"${athlete.name}" sporcusunu ve tüm analizlerini silmek istediğinizden emin misiniz?`}
          onConfirm={doDeleteAthlete}
          onCancel={() => setConfirmDeleteAthlete(false)}
        />
      )}
      <button className="back-button" onClick={onBack}>Back</button>
      <div className="detail-grid">
        <aside className="profile-column">
          <section className="profile-card">
            <div className="avatar large">{initials(athlete.name)}</div>
            <h2>{athlete.name}</h2>
            <p>{athlete.sport || '-'} · {athlete.team || '-'}</p>
            <span className={`pill ${riskClass(latest?.risk)}`}>{latest?.risk || 'No data'}</span>
            <div className="invite-box">
              <span>Athlete ID</span>
              <strong>{athlete.id}</strong>
            </div>
            <button
              className="danger-button"
              onClick={() => setConfirmDeleteAthlete(true)}
              disabled={busy}
            >
              Sporcuyu Sil
            </button>
          </section>
          <section className="info-card">
            <div><span>Latest Score</span><strong>{latest?.total_score ?? '-'}</strong></div>
            <div><span>Analyses</span><strong>{analyses.length}</strong></div>
          </section>
        </aside>

        <section className="detail-main">
          <div className="upload-engine-row">
            <div className="video-upload-section">
              <div className="video-section-header">
                <h2>Diagnostic Upload</h2>
                <p>Synchronized dual-angle motion capture analysis.</p>
              </div>
              <div className="video-cards-grid">
                <VideoUploadCard label="Front View" file={frontFile} onChange={setFrontFile} />
                <VideoUploadCard label="Side View" file={sideFile} onChange={setSideFile} />
              </div>
            </div>
            <div className="engine-config-panel">
              <div className="engine-panel-header">
                <span className="material-symbols-outlined engine-panel-icon">memory</span>
                <h2 className="engine-panel-title">Engine Configuration</h2>
              </div>
              <EngineModelSelector selected={poseModels} onChange={setPoseModels} />
              {needsTestSide && <TestSideSelect value={testSide} onChange={setTestSide} />}
              <AnalyseProgress onClick={analyse} busy={busy} />
              <p className="engine-status-text">
                {busy ? 'Analysis in progress...' : 'Ready to analyze media.'}
              </p>
              {error && <div className="error-banner">{error}</div>}
            </div>
          </div>

          <div className="outputs-panel">
            <h2>Analysis History <span>{busy ? '…' : analyses.length}</span></h2>
            {busy && (
              <div className="processing-state" role="status" aria-live="polite">
                <div className="spinner" />
                <strong>Processing...</strong>
                <span>Action in progress.</span>
              </div>
            )}
            {!busy && analyses.length === 0 && (
              <div className="empty-state">No analyses yet.</div>
            )}
            {!busy && groupAnalyses(analyses).map((group, i) =>
              group.length === 1 ? (
                <AnalysisCard
                  key={group[0].id}
                  analysis={group[0]}
                  athleteName={athlete.name}
                  onError={setError}
                  onDelete={(id) => setConfirmAnalysisId(id)}
                />
              ) : (
                <div key={i} className="analysis-comparison-group">
                  <div className="comparison-group-label">Comparison run · {new Date(group[0].created_at).toLocaleString('tr-TR', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' })}</div>
                  <div className="comparison-group-grid">
                    {group.map((a) => (
                      <AnalysisCard
                        key={a.id}
                        analysis={a}
                        athleteName={athlete.name}
                        onError={setError}
                        onDelete={(id) => setConfirmAnalysisId(id)}
                        compact
                      />
                    ))}
                  </div>
                </div>
              )
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('sportsmd_token'));
  const [user, setUser] = useState(null);
  const [athletes, setAthletes] = useState([]);
  const [selected, setSelected] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [page, setPage] = useState('dashboard'); // 'dashboard' | 'statistics'

  async function request(path, options = {}) {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.headers || {}),
        Authorization: `Bearer ${token}`,
      },
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Request failed');
    return res.json();
  }

  async function loadData() {
    if (!token) return;
    const [me, items] = await Promise.all([request('/users/me'), request('/athletes')]);
    setUser(me);
    setAthletes(items);
    if (selected) {
      const refreshed = items.find((item) => item.id === selected.id);
      setSelected(refreshed || null);
    }
  }

  useEffect(() => {
    loadData().catch(() => {
      localStorage.removeItem('sportsmd_token');
      setToken(null);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function handleAuth(nextToken) {
    localStorage.setItem('sportsmd_token', nextToken);
    setToken(nextToken);
  }

  function signOut() {
    localStorage.removeItem('sportsmd_token');
    setToken(null);
    setUser(null);
    setAthletes([]);
    setSelected(null);
  }

  async function createAthlete(payload) {
    const athlete = await request('/athletes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    setShowModal(false);
    await loadData();
    setSelected(athlete);
  }

  if (!token) return <AuthScreen onAuth={handleAuth} />;

  return (
    <div className="app-shell">
      {!selected && (
        <Sidebar
          user={user}
          onDashboard={() => { setSelected(null); setPage('dashboard'); }}
          onStatistics={() => { setSelected(null); setPage('statistics'); }}
          onSignOut={signOut}
          activePage={page}
        />
      )}
      {selected ? (
        <AthleteDetail
          athlete={selected}
          onBack={() => setSelected(null)}
          onAnalysed={loadData}
          onDeleteAthlete={() => { setSelected(null); loadData(); }}
        />
      ) : page === 'statistics' ? (
        <StatisticsPage token={token} athletes={athletes} />
      ) : (
        <Dashboard athletes={athletes} onAdd={() => setShowModal(true)} onSelect={(a) => { setSelected(a); setPage('dashboard'); }} />
      )}
      {showModal && <CreateAthleteModal onClose={() => setShowModal(false)} onCreate={createAthlete} />}
    </div>
  );
}

export default App;
