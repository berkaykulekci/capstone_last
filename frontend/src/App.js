import { useEffect, useMemo, useState } from 'react';
import './App.css';

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
          throw new Error(body.detail || 'Account could not be created');
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
      if (!loginRes.ok) throw new Error(body.detail || 'Login failed');
      onAuth(body.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="brand-mark">S</div>
        <h1>SportsMD</h1>
        <p>{mode === 'login' ? 'Sign in to manage athletes and LESS analysis.' : 'Create your SportsMD workspace.'}</p>
        <form onSubmit={submit} className="auth-form">
          <label>Email</label>
          <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required />
          <label>Password</label>
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" required />
          {error && <div className="error-banner">{error}</div>}
          <button className="primary-button" disabled={busy} type="submit">
            {busy ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>
        <button className="text-button" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? 'Create an account' : 'Already have an account? Sign in'}
        </button>
      </section>
    </main>
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

function Sidebar({ user, onDashboard, onSignOut }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark small">S</div>
        <strong>SportsMD</strong>
      </div>
      <button className="nav-item active" onClick={onDashboard}>Dashboard</button>
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

function UploadBox({ label, file, onChange }) {
  return (
    <label className="upload-box">
      <input type="file" accept="video/mp4,video/quicktime,video/x-msvideo,.mp4,.mov,.MOV,.avi" onChange={(event) => onChange(event.target.files?.[0] || null)} />
      <span className="camera-icon">CAM</span>
      <strong>{label}</strong>
      <small>{file ? file.name : 'MP4, MOV, AVI'}</small>
    </label>
  );
}

function ModelToggle({ value, onChange }) {
  return (
    <div className="model-toggle">
      <span className="model-toggle-label">Pose Model</span>
      <div className="model-toggle-buttons">
        <button
          type="button"
          className={value === 'mediapipe' ? 'model-btn active' : 'model-btn'}
          onClick={() => onChange('mediapipe')}
        >
          MediaPipe
        </button>
        <button
          type="button"
          className={value === 'yolo' ? 'model-btn active' : 'model-btn'}
          onClick={() => onChange('yolo')}
        >
          YOLO
        </button>
      </div>
      {value === 'yolo' && (
        <p className="model-note">M4 (plantar fleksiyon), M9 (iç rot), M10 (dış rot) maddeleri toe/heel landmark olmadığından proxy yöntemle yaklaşık hesaplanır. Max skor: 19, yaklaşık maddeler CSV'de işaretlenir.</p>
      )}
    </div>
  );
}

function TestSideSelect({ value, onChange }) {
  return (
    <div className="test-side-select">
      <span className="model-toggle-label">Test Leg (YOLO)</span>
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
      <p className="model-note">Which leg faces the side camera?</p>
    </div>
  );
}

function ModelBadge({ model }) {
  const isYolo = (model || '').toLowerCase() === 'yolo';
  return (
    <span className={`pill ${isYolo ? 'blue' : ''}`} style={{ fontSize: 11 }}>
      {isYolo ? 'YOLO' : 'MediaPipe'}
    </span>
  );
}

function AnalysisCard({ analysis, athleteName, onError, onDelete }) {
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
    <div className="analysis-card">
      <div className="analysis-card-header">
        <div className="analysis-card-meta">
          <ModelBadge model={analysis.pose_model} />
          <span className={`pill ${riskClass(analysis.risk)}`}>{analysis.risk || 'No data'}</span>
          <strong className="analysis-score">
            {analysis.total_score ?? '-'} <span>puan</span>
          </strong>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <small>{date}</small>
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

function AthleteDetail({ athlete, onBack, onAnalysed }) {
  const [sideFile, setSideFile] = useState(null);
  const [frontFile, setFrontFile] = useState(null);
  const [poseModel, setPoseModel] = useState('mediapipe');
  const [testSide, setTestSide] = useState('right');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

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
    form.append('pose_model', poseModel);
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

  async function deleteAnalysis(analysisId) {
    if (!window.confirm("Bu analizi silmek istediğinizden emin misiniz?")) {
      return;
    }
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

  const analyses = athlete.analyses || [];
  const latest = athlete.latest_analysis;

  return (
    <main className="detail-layout">
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
          </section>
          <section className="info-card">
            <div><span>Latest Score</span><strong>{latest?.total_score ?? '-'}</strong></div>
            <div><span>Analyses</span><strong>{analyses.length}</strong></div>
          </section>
        </aside>

        <section className="detail-main">
          <div className="upload-panel">
            <h2>Upload Video</h2>
            <div className="upload-grid">
              <UploadBox label="Side view (sagittal)" file={sideFile} onChange={setSideFile} />
              <UploadBox label="Front view (frontal)" file={frontFile} onChange={setFrontFile} />
            </div>
            <ModelToggle value={poseModel} onChange={setPoseModel} />
            {poseModel === 'yolo' && <TestSideSelect value={testSide} onChange={setTestSide} />}
            <div className="upload-actions-row">
              <button className="primary-button" onClick={analyse} disabled={busy}>
                {busy ? 'Analysing...' : 'Upload & Analyse'}
              </button>
            </div>
            {error && <div className="error-banner">{error}</div>}
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
            {!busy && analyses.map((a) => (
              <AnalysisCard
                key={a.id}
                analysis={a}
                athleteName={athlete.name}
                onError={setError}
                onDelete={deleteAnalysis}
              />
            ))}
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
      {!selected && <Sidebar user={user} onDashboard={() => setSelected(null)} onSignOut={signOut} />}
      {selected ? (
        <AthleteDetail athlete={selected} onBack={() => setSelected(null)} onAnalysed={loadData} />
      ) : (
        <Dashboard athletes={athletes} onAdd={() => setShowModal(true)} onSelect={setSelected} />
      )}
      {showModal && <CreateAthleteModal onClose={() => setShowModal(false)} onCreate={createAthlete} />}
    </div>
  );
}

export default App;
