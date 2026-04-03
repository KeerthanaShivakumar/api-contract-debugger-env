'use client';

import { useState, useEffect } from 'react';
import axios from 'axios';
import './page.css';

interface Violation {
  endpoint_index: number;
  location: string;
  field_name: string | null;
  violation_type: string;
  description: string;
  severity: number;
}

interface Endpoint {
  method: string;
  path: string;
  status_code: number;
  request_body?: Record<string, any>;
  response_body?: Record<string, any>;
}

interface Observation {
  task_name: string;
  task_description: string;
  endpoints: Endpoint[];
  violations: Violation[];
  violations_fixed_this_step: number;
  violations_introduced_this_step: number;
  total_violations_at_start: number;
  step_count: number;
  max_steps: number;
  reward: number;
  done: boolean;
  last_action_error: string | null;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7860';
const HF_SPACE_URL =
  process.env.NEXT_PUBLIC_HF_SPACE_URL ||
  'https://huggingface.co/spaces/keerthanas1011/api-contract-debugger';

export default function Home() {
  const [observation, setObservation] = useState<Observation | null>(null);
  const [loading, setLoading] = useState(false);
  const [score, setScore] = useState<number | null>(null);
  const [selectedTask, setSelectedTask] = useState('easy');
  const [logs, setLogs] = useState<Array<{ type: string; msg: string; ts: string }>>([]);
  const [totalReward, setTotalReward] = useState(0);
  const [baseUrl, setBaseUrl] = useState(API_BASE_URL);
  const [totalFixed, setTotalFixed] = useState(0);
  const [testingUrl, setTestingUrl] = useState<string | null>(null);

  const [actionForm, setActionForm] = useState({
    kind: 'add_field',
    endpoint_index: 0,
    location: 'response_body',
    field_name: '',
    new_value: '',
  });

  useEffect(() => {
    // Load base URL from localStorage or use default from env
    const stored = localStorage.getItem('acd_base_url');
    if (stored) {
      setBaseUrl(stored);
    } else {
      setBaseUrl(API_BASE_URL);
    }
  }, []);

  const saveBaseUrl = (url: string) => {
    const normalized = url.trim().replace(/\/$/, ''); // Remove trailing slash
    setBaseUrl(normalized);
    localStorage.setItem('acd_base_url', normalized);
    setTestingUrl(null);
  };

  const setPresetUrl = (preset: 'local' | 'hf') => {
    const url = preset === 'local' ? 'http://localhost:7860' : HF_SPACE_URL;
    saveBaseUrl(url);
    toast(`Backend set to ${preset === 'local' ? 'Local' : 'HuggingFace'}`, 'ok');
  };

  const testConnection = async () => {
    const url = baseUrl.trim().replace(/\/$/, '');
    if (!url) {
      toast('Enter a backend URL first', 'err');
      return;
    }

    setTestingUrl(url);
    try {
      const resp = await axios.get(`${url}/health`, { timeout: 5000 });
      if (resp.status === 200) {
        toast('✅ Backend is online!', 'ok');
        addLog('ok', `Connected to: ${url}`);
      }
    } catch (err: any) {
      const msg = err.message || 'Connection failed';
      toast(`❌ Backend offline: ${msg}`, 'err');
      addLog('err', `Connection error: ${msg}`);
    } finally {
      setTestingUrl(null);
    }
  };

  const addLog = (type: string, msg: string) => {
    const ts = new Date().toTimeString().slice(0, 8);
    setLogs((prev) => [...prev, { type, msg, ts }]);
  };

  const clearLogs = () => setLogs([]);

  const resetEpisode = async () => {
    const url = baseUrl.trim().replace(/\/$/, '');
    if (!url) {
      toast('Set the Backend URL first', 'err');
      return;
    }

    setLoading(true);
    try {
      const resp = await axios.post(`${url}/reset`, { task_name: selectedTask }, { timeout: 10000 });
      setObservation(resp.data);
      setTotalReward(0);
      setTotalFixed(0);
      setScore(null);
      clearLogs();
      addLog('info', `Episode reset → task=${selectedTask}`);
      toast(`Environment reset (${selectedTask})`, 'ok');
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ||
        err.response?.statusText ||
        err.message ||
        'Reset failed';
      toast(`Reset failed: ${msg}`, 'err');
      addLog('err', `Reset error: ${msg}`);
    }
    setLoading(false);
  };

  const buildAction = (): any => {
    const kind = actionForm.kind;
    const ep = parseInt(actionForm.endpoint_index) || 0;
    const loc = actionForm.location;
    const field = actionForm.field_name.trim() || null;
    const rawVal = actionForm.new_value.trim();

    let new_value: any = null;
    if (rawVal) {
      try {
        new_value = JSON.parse(rawVal);
      } catch {
        new_value = rawVal;
      }
    }

    if (kind === 'no_op') {
      return { kind, endpoint_index: ep, location: loc, field_name: null, new_value: null };
    }
    if (kind !== 'change_status' && kind !== 'remove_field' && !field) {
      toast('Field Name is required for this action kind', 'err');
      return null;
    }

    return { kind, endpoint_index: ep, location: loc, field_name: field, new_value };
  };

  const submitAction = async () => {
    if (!observation || observation.done) return;
    const action = buildAction();
    if (!action) return;

    const url = baseUrl.trim().replace(/\/$/, '');
    setLoading(true);
    try {
      const resp = await axios.post(`${url}/step`, { action }, { timeout: 10000 });
      setObservation(resp.data);
      const reward = resp.data.reward || 0;
      setTotalReward((prev) => prev + reward);
      if (resp.data.violations_fixed_this_step > 0) {
        setTotalFixed((prev) => prev + resp.data.violations_fixed_this_step);
      }

      const emoji =
        resp.data.violations_fixed_this_step > 0
          ? '✅'
          : resp.data.violations_introduced_this_step > 0
            ? '⚠'
            : '→';
      addLog(
        'step',
        `${emoji} step=${resp.data.step_count} fixed=${resp.data.violations_fixed_this_step} reward≈${reward.toFixed(3)}`
      );

      if (!resp.data.violations || resp.data.violations.length === 0) {
        toast('🎉 All violations resolved!', 'ok');
        addLog('ok', 'Episode complete!');
      }

      // Reset form for next action
      setActionForm({
        kind: 'add_field',
        endpoint_index: 0,
        location: 'response_body',
        field_name: '',
        new_value: '',
      });
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ||
        err.response?.statusText ||
        err.message ||
        'Step failed';
      toast(`Step failed: ${msg}`, 'err');
      addLog('err', `Step error: ${msg}`);
    }
    setLoading(false);
  };

  const fetchScore = async () => {
    const url = baseUrl.trim().replace(/\/$/, '');
    try {
      const resp = await axios.get(`${url}/score`, { timeout: 5000 });
      const s = resp.data.score || 0;
      setScore(s);
      addLog('ok', `Score: ${s.toFixed(3)}`);
      toast(`Score: ${s.toFixed(3)}`, 'ok');
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ||
        err.response?.statusText ||
        err.message ||
        'Score fetch failed';
      toast(`Score error: ${msg}`, 'err');
      addLog('err', `Score error: ${msg}`);
    }
  };

  const copyJSON = () => {
    navigator.clipboard.writeText(JSON.stringify(observation, null, 2));
    toast('Copied to clipboard', 'ok');
  };

  const toast = (msg: string, type = 'info') => {
    const area = document.getElementById('toast-area');
    if (!area) return;
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.textContent = msg;
    area.appendChild(t);
    setTimeout(
      () => {
        t.style.opacity = '0';
        t.style.transition = 'opacity 0.4s';
        setTimeout(() => t.remove(), 400);
      },
      3000
    );
  };

  const toggleEndpoint = (idx: number) => {
    const body = document.getElementById(`ep-body-${idx}`);
    const toggle = document.getElementById(`toggle-${idx}`);
    if (body && toggle) {
      body.classList.toggle('open');
      toggle.textContent = body.classList.contains('open') ? '▴' : '▾';
    }
  };

  const onKindChange = (kind: string) => {
    setActionForm({ ...actionForm, kind });
  };

  const progressPercent = observation
    ? observation.total_violations_at_start > 0
      ? (
          ((observation.total_violations_at_start - observation.violations.length) /
            observation.total_violations_at_start) *
          100
        ).toFixed(0)
      : '0'
    : '0';

  return (
    <>
      <header>
        <div className="header-left">
          <div className="logo-badge">🔍</div>
          <div>
            <div className="site-title">API Contract Debugger</div>
            <div className="site-sub">OpenEnv · RL Benchmark</div>
          </div>
        </div>
        <div className="header-right">
          <span className="pill pill-purple">Meta × PyTorch</span>
          <span className="pill pill-green">
            <span className="status-dot"></span>
            {baseUrl ? 'Ready' : 'Waiting'}
          </span>
        </div>
      </header>

      <section className="hero">
        <div className="hero-label">Real-world RL environment</div>
        <h1>
          Debug broken <span>API contracts</span>
          <br />
          step by step.
        </h1>
        <p className="hero-desc">
          An RL benchmark where agents receive a malformed OpenAPI spec and must fix contract
          violations through targeted single-step actions.
        </p>
        <div className="hero-metrics">
          <div className="metric">
            <div className="metric-val purple">3</div>
            <div className="metric-key">Task Tiers</div>
          </div>
          <div className="metric">
            <div className="metric-val green">{score !== null ? score.toFixed(2) : '—'}</div>
            <div className="metric-key">Episode Score</div>
          </div>
          <div className="metric">
            <div className="metric-val cyan">{totalFixed}</div>
            <div className="metric-key">Violations Fixed</div>
          </div>
          <div className="metric">
            <div className="metric-val">{observation?.step_count || '—'}</div>
            <div className="metric-key">Steps Taken</div>
          </div>
        </div>
      </section>

      <main className="main">
        {/* Config Card */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <div className="icon icon-purple">⚙</div>
              Environment Config
            </div>
          </div>
          <div className="card-body">
            <div className="field-group">
              <label>Backend URL</label>
              <input
                type="url"
                placeholder="http://localhost:7860"
                value={baseUrl}
                onChange={(e) => saveBaseUrl(e.target.value)}
              />
              <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                <button
                  className="btn btn-secondary"
                  style={{ flex: 1, fontSize: '0.65rem' }}
                  onClick={() => setPresetUrl('local')}
                >
                  📍 Local
                </button>
                <button
                  className="btn btn-secondary"
                  style={{ flex: 1, fontSize: '0.65rem' }}
                  onClick={() => setPresetUrl('hf')}
                >
                  🤗 HF Space
                </button>
                <button
                  className="btn btn-secondary"
                  style={{ flex: 1, fontSize: '0.65rem' }}
                  disabled={testingUrl !== null}
                  onClick={testConnection}
                >
                  {testingUrl ? 'Testing...' : '🔗 Test'}
                </button>
              </div>
              <div
                style={{
                  fontSize: '0.6rem',
                  color: 'var(--text3)',
                  marginTop: '8px',
                  lineHeight: '1.4',
                }}
              >
                <strong>Local:</strong> http://localhost:7860
                <br />
                <strong>HF:</strong> https://huggingface.co/spaces/...
              </div>
            </div>
            <div className="field-group">
              <label>Task Difficulty</label>
              <select
                value={selectedTask}
                onChange={(e) => setSelectedTask(e.target.value)}
              >
                <option value="easy">Easy — 1 endpoint, 1 violation</option>
                <option value="medium">Medium — 3 endpoints, 3 violations</option>
                <option value="hard">Hard — 4 endpoints, 6 violations</option>
              </select>
            </div>
            <button
              className="btn btn-primary"
              disabled={loading}
              onClick={resetEpisode}
              style={{ marginTop: '12px' }}
            >
              {loading ? (
                <>
                  <span className="spin"></span> Loading
                </>
              ) : (
                '⟳ Reset Episode'
              )}
            </button>
            <button
              className="btn btn-secondary"
              disabled={!observation || loading}
              onClick={fetchScore}
              style={{ marginTop: '8px' }}
            >
              📊 Get Score
            </button>
          </div>
        </div>

        {/* Stats Card */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <div className="icon icon-cyan">◈</div>
              Episode State
            </div>
          </div>
          <div className="card-body">
            {observation ? (
              <>
                <div className="stats-row">
                  <div className="stat-box">
                    <div className="stat-val">{observation.step_count}</div>
                    <div className="stat-key">Step</div>
                  </div>
                  <div className="stat-box">
                    <div className="stat-val">{observation.max_steps}</div>
                    <div className="stat-key">Max Steps</div>
                  </div>
                  <div className="stat-box">
                    <div className="stat-val">{observation.violations.length}</div>
                    <div className="stat-key">Remaining</div>
                  </div>
                  <div className="stat-box">
                    <div className="stat-val">{observation.total_violations_at_start}</div>
                    <div className="stat-key">At Start</div>
                  </div>
                </div>
                <div className="progress-wrap">
                  <div className="progress-label-row">
                    <span>Progress</span>
                    <strong>{progressPercent}%</strong>
                  </div>
                  <div className="progress-track">
                    <div
                      className="progress-fill"
                      style={{ width: `${progressPercent}%` }}
                    ></div>
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-state">
                <div className="big-icon">⚡</div>
                Hit <strong>Reset Episode</strong> to load
              </div>
            )}
            {score !== null && (
              <div className="score-box show">
                <div
                  className={`score-big ${score >= 0.9 ? 'perfect' : score >= 0.5 ? 'good' : 'poor'}`}
                >
                  {score.toFixed(3)}
                </div>
                <div className="score-label">Episode Score</div>
              </div>
            )}
          </div>
        </div>

        <div className="section-divider">
          <div className="section-divider-line"></div>
          <div className="section-divider-label">Live Spec & Violations</div>
          <div className="section-divider-line"></div>
        </div>

        {/* Endpoints Card */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <div className="icon icon-yellow">⬡</div>
              Current Endpoint Spec
            </div>
            <span style={{ fontSize: '0.62rem', color: 'var(--text3)' }}>
              {observation?.endpoints.length || 0} endpoints
            </span>
          </div>
          <div className="card-body">
            {observation && observation.endpoints.length > 0 ? (
              <div className="endpoint-list">
                {observation.endpoints.map((ep, i) => (
                  <div key={i} className="endpoint-card">
                    <div className="endpoint-head" onClick={() => toggleEndpoint(i)}>
                      <span className={`method-badge method-${ep.method}`}>{ep.method}</span>
                      <span className="endpoint-path">{ep.path}</span>
                      <span className="endpoint-status">HTTP {ep.status_code}</span>
                      <span className="endpoint-toggle" id={`toggle-${i}`}>
                        ▾
                      </span>
                    </div>
                    <div className="endpoint-body" id={`ep-body-${i}`}>
                      {Object.keys(ep.request_body || {}).length > 0 && (
                        <div>
                          <div style={{ marginBottom: '8px' }}>
                            <strong style={{ fontSize: '0.65rem' }}>Request Body</strong>
                          </div>
                          <table className="field-table">
                            <thead>
                              <tr>
                                <th>Field</th>
                                <th>Type</th>
                                <th>Required</th>
                              </tr>
                            </thead>
                            <tbody>
                              {Object.entries(ep.request_body || {}).map(([name, spec]: any) => (
                                <tr key={name}>
                                  <td className="field-name">{name}</td>
                                  <td>
                                    <span className={`type-chip type-${spec.type || 'string'}`}>
                                      {spec.type || '?'}
                                    </span>
                                  </td>
                                  <td>{spec.required ? 'yes' : 'no'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                      {Object.keys(ep.response_body || {}).length > 0 && (
                        <div style={{ marginTop: '10px' }}>
                          <div style={{ marginBottom: '8px' }}>
                            <strong style={{ fontSize: '0.65rem' }}>Response Body</strong>
                          </div>
                          <table className="field-table">
                            <thead>
                              <tr>
                                <th>Field</th>
                                <th>Type</th>
                                <th>Required</th>
                              </tr>
                            </thead>
                            <tbody>
                              {Object.entries(ep.response_body || {}).map(([name, spec]: any) => (
                                <tr key={name}>
                                  <td className="field-name">{name}</td>
                                  <td>
                                    <span className={`type-chip type-${spec.type || 'string'}`}>
                                      {spec.type || '?'}
                                    </span>
                                  </td>
                                  <td>{spec.required ? 'yes' : 'no'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <div className="big-icon">📋</div>
                No spec loaded yet.
              </div>
            )}
          </div>
        </div>

        {/* Violations Card */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <div className="icon icon-red">⚠</div>
              Active Violations
            </div>
            <span style={{ fontSize: '0.62rem', color: 'var(--text3)' }}>
              {observation?.violations.length || 0}
            </span>
          </div>
          <div className="card-body">
            {observation && observation.violations.length > 0 ? (
              <div className="violations-list">
                {observation.violations.map((v, idx) => {
                  const typeClass =
                    v.violation_type === 'missing_field'
                      ? 'missing'
                      : v.violation_type === 'wrong_type'
                        ? 'wrong'
                        : v.violation_type === 'extra_field'
                          ? 'extra'
                          : 'status';
                  const tagClass =
                    v.violation_type === 'missing_field'
                      ? 'tag-missing'
                      : v.violation_type === 'wrong_type'
                        ? 'tag-wrong'
                        : v.violation_type === 'extra_field'
                          ? 'tag-extra'
                          : 'tag-status';
                  const label = v.violation_type.replace('_', ' ');
                  return (
                    <div key={idx} className={`violation-item ${typeClass}`}>
                      <div>
                        <span className={`violation-tag ${tagClass}`}>{label}</span>
                        <span style={{ color: 'var(--text3)', fontSize: '0.6rem' }}>
                          ep[{v.endpoint_index}] · {v.location}
                          {v.field_name ? ` · ${v.field_name}` : ''}
                        </span>
                      </div>
                      <div className="violation-desc">{v.description}</div>
                    </div>
                  );
                })}
              </div>
            ) : observation ? (
              <div className="no-violations">
                <span className="big">✅</span>
                All violations resolved!
              </div>
            ) : (
              <div className="empty-state">
                <div className="big-icon">🔎</div>
                Reset to detect violations.
              </div>
            )}
          </div>
        </div>

        <div className="section-divider">
          <div className="section-divider-line"></div>
          <div className="section-divider-label">Agent Action</div>
          <div className="section-divider-line"></div>
        </div>

        {/* Action Builder */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <div className="icon icon-green">▶</div>
              Action Builder
            </div>
          </div>
          <div className="card-body">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
              <div className="field-group" style={{ marginBottom: 0 }}>
                <label>Action Kind</label>
                <select
                  value={actionForm.kind}
                  onChange={(e) => onKindChange(e.target.value)}
                >
                  <option value="add_field">add_field</option>
                  <option value="remove_field">remove_field</option>
                  <option value="change_type">change_type</option>
                  <option value="change_status">change_status</option>
                  <option value="no_op">no_op</option>
                </select>
              </div>
              <div className="field-group" style={{ marginBottom: 0 }}>
                <label>Endpoint Index</label>
                <input
                  type="number"
                  value={actionForm.endpoint_index}
                  onChange={(e) =>
                    setActionForm({ ...actionForm, endpoint_index: parseInt(e.target.value) || 0 })
                  }
                />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
              <div className="field-group" style={{ marginBottom: 0 }}>
                <label>Location</label>
                <select
                  value={actionForm.location}
                  onChange={(e) => setActionForm({ ...actionForm, location: e.target.value })}
                >
                  <option value="response_body">response_body</option>
                  <option value="request_body">request_body</option>
                  <option value="status_code">status_code</option>
                </select>
              </div>
              <div className="field-group" style={{ marginBottom: 0 }}>
                <label>Field Name</label>
                <input
                  type="text"
                  placeholder="e.g. created_at"
                  value={actionForm.field_name}
                  onChange={(e) => setActionForm({ ...actionForm, field_name: e.target.value })}
                />
              </div>
            </div>
            <div className="field-group">
              <label>New Value</label>
              <textarea
                value={actionForm.new_value}
                onChange={(e) => setActionForm({ ...actionForm, new_value: e.target.value })}
                placeholder='{"type":"string","required":true}'
              ></textarea>
            </div>
            <div className="btn-row">
              <button
                className="btn btn-green"
                disabled={!observation || loading || observation.done}
                onClick={submitAction}
              >
                {loading ? (
                  <>
                    <span className="spin"></span> Sending
                  </>
                ) : (
                  '▶ Send Action'
                )}
              </button>
              <button
                className="btn btn-red"
                disabled={!observation || loading || observation.done}
                onClick={submitAction}
              >
                ⏭ No-Op
              </button>
            </div>
          </div>
        </div>

        {/* Log Card */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <div className="icon icon-purple">≡</div>
              Step Log
            </div>
            <button
              className="btn-link"
              style={{ fontSize: '0.6rem', padding: '4px 10px' }}
              onClick={clearLogs}
            >
              clear
            </button>
          </div>
          <div className="card-body" style={{ padding: '12px' }}>
            <div className="log-wrap">
              {logs.length === 0 ? (
                <div className="log-empty">Waiting for episode…</div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="log-entry">
                    <span className="log-ts">{log.ts}</span>
                    <span className={`log-type ${log.type}`}>[{log.type.toUpperCase()}]</span>
                    <span className="log-msg">{log.msg}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Raw JSON */}
        <div className="card col-full">
          <div className="card-header">
            <div className="card-title">
              <div className="icon icon-cyan">{ }</div>
              Raw Observation JSON
            </div>
            <button
              className="btn-link"
              style={{ fontSize: '0.6rem', padding: '4px 10px' }}
              onClick={copyJSON}
            >
              copy
            </button>
          </div>
          <div className="card-body" style={{ padding: '12px' }}>
            <pre
              style={{
                fontSize: '0.65rem',
                color: 'var(--text2)',
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '14px',
                overflow: 'auto',
                maxHeight: '260px',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {observation ? JSON.stringify(observation, null, 2) : '// No observation yet.'}
            </pre>
          </div>
        </div>
      </main>

      <div id="toast-area"></div>
    </>
  );
}
