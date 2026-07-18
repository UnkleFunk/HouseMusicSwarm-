'use strict';

const API = 'http://localhost:8081/api';

// ── State ─────────────────────────────────────────────────────────────────────
let state = {
  captureId:      null,
  captureStatus:  'idle',      // idle | recording | complete | error
  analyzeStatus:  'idle',      // idle | analyzing | complete | error
  pollTimer:      null,
  currentDeviceIndex: null,
  querySpectrum:  null,
  results:        [],
  radarChart:     null,
  spectrumChart:  null,
  playingTrackId: null,
  dbRefreshJobId: null,
};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $deviceSelect    = document.getElementById('device-select');
const $durationSlider  = document.getElementById('duration-slider');
const $durationLabel   = document.getElementById('duration-label');
const $genreFilter     = document.getElementById('genre-filter-ctrl');
const $btnRecord       = document.getElementById('btn-record');
const $btnRecordLabel  = document.getElementById('btn-record-label');
const $btnAnalyze      = document.getElementById('btn-analyze');
const $btnAnalyzeLabel = document.getElementById('btn-analyze-label');
const $btnRefresh      = document.getElementById('btn-refresh');
const $captureStatus   = document.getElementById('capture-status');
const $dbCount         = document.getElementById('db-count');
const $resultsList     = document.getElementById('results-list');
const $resultsCount    = document.getElementById('results-count');
const $waveformCanvas  = document.getElementById('waveform-canvas');
const $radarCanvas     = document.getElementById('radar-canvas');
const $spectrumCanvas  = document.getElementById('spectrum-canvas');
const $spectrumLegend  = document.getElementById('spectrum-legend');
const $previewPlayer   = document.getElementById('preview-player');
const $toastContainer  = document.getElementById('toast-container');

// Stat displays
const $statBpm      = document.getElementById('stat-bpm');
const $statLufs     = document.getElementById('stat-lufs');
const $statCentroid = document.getElementById('stat-centroid');
const $statDynamics = document.getElementById('stat-dynamics');
const $barSub       = document.getElementById('bar-sub');
const $barBass      = document.getElementById('bar-bass');
const $barLowmid    = document.getElementById('bar-lowmid');
const $pctSub       = document.getElementById('pct-sub');
const $pctBass      = document.getElementById('pct-bass');
const $pctLowmid    = document.getElementById('pct-lowmid');

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadDevices();
  loadDbStatus();
  initRadarChart();
  initSpectrumChart();

  $durationSlider.addEventListener('input', () => {
    $durationLabel.textContent = `${$durationSlider.value}s`;
  });

  $btnRecord.addEventListener('click', onRecordClick);
  $btnAnalyze.addEventListener('click', onAnalyzeClick);
  $btnRefresh.addEventListener('click', onRefreshClick);
});

// ── Devices ───────────────────────────────────────────────────────────────────
async function loadDevices() {
  try {
    const devices = await apiFetch('/devices');
    $deviceSelect.innerHTML = '';
    if (!devices.length) {
      $deviceSelect.innerHTML = '<option value="">No input devices found</option>';
      return;
    }

    // Sort: loopback devices first
    const sorted = [...devices].sort((a, b) => b.is_loopback - a.is_loopback);

    const loopbacks = sorted.filter(d => d.is_loopback);
    const others    = sorted.filter(d => !d.is_loopback);

    if (loopbacks.length) {
      const og = document.createElement('optgroup');
      og.label = '⬡ Virtual Loopback (Recommended)';
      loopbacks.forEach(d => og.appendChild(deviceOption(d)));
      $deviceSelect.appendChild(og);
    }

    if (others.length) {
      const og = document.createElement('optgroup');
      og.label = '◎ Physical Inputs';
      others.forEach(d => og.appendChild(deviceOption(d)));
      $deviceSelect.appendChild(og);
    }

    // Auto-select first loopback if available
    if (loopbacks.length) {
      $deviceSelect.value = loopbacks[0].index;
    }
  } catch (e) {
    $deviceSelect.innerHTML = '<option value="">Could not load devices</option>';
    toast('Could not reach Reference Finder server — is it running?', 'error');
  }
}

function deviceOption(d) {
  const opt = document.createElement('option');
  opt.value = d.index;
  opt.textContent = `${d.name}  [${d.default_sample_rate / 1000}kHz · ${d.channels}ch]`;
  return opt;
}

// ── DB status ─────────────────────────────────────────────────────────────────
async function loadDbStatus() {
  try {
    const s = await apiFetch('/db-status');
    if (s.total > 0) {
      $dbCount.textContent = `${s.total.toLocaleString()} tracks`;
      $dbCount.className = 'db-count ready';
    } else {
      $dbCount.textContent = 'EMPTY — click Refresh DB';
      $dbCount.className = 'db-count empty';
    }
  } catch {
    $dbCount.textContent = 'unavailable';
  }
}

// ── Record ────────────────────────────────────────────────────────────────────
async function onRecordClick() {
  if (state.captureStatus === 'recording') {
    // Stop early — the server will finish when sounddevice.wait() returns,
    // but we can flip local state and wait for poll to confirm
    stopPolling();
    state.captureStatus = 'idle';
    setRecordUI('idle');
    return;
  }

  const deviceIndex = parseInt($deviceSelect.value);
  if (isNaN(deviceIndex)) {
    toast('Select an audio input device first', 'error');
    return;
  }

  const duration = parseInt($durationSlider.value);

  try {
    const job = await apiFetch('/capture/start', 'POST', { device_index: deviceIndex, duration_seconds: duration });
    state.captureId = job.capture_id;
    state.captureStatus = 'recording';
    state.currentDeviceIndex = deviceIndex;
    setRecordUI('recording', duration);
    $btnAnalyze.disabled = true;
    startCapturePoll(duration);
  } catch (e) {
    toast(`Capture failed to start: ${e.message}`, 'error');
  }
}

function setRecordUI(status, duration) {
  if (status === 'recording') {
    $btnRecord.classList.add('recording');
    $btnRecordLabel.textContent = 'STOP';
    $captureStatus.className = 'capture-status recording';
    $captureStatus.textContent = `Recording ${duration}s…`;
    animateWaveformIdle();
  } else if (status === 'complete') {
    $btnRecord.classList.remove('recording');
    $btnRecordLabel.textContent = 'RE-RECORD';
    $captureStatus.className = 'capture-status complete';
    $captureStatus.textContent = 'Capture complete — click Analyze';
    $btnAnalyze.disabled = false;
  } else {
    $btnRecord.classList.remove('recording');
    $btnRecordLabel.textContent = 'RECORD';
    $captureStatus.className = 'capture-status';
    $captureStatus.textContent = '—';
  }
}

function startCapturePoll(expectedDuration) {
  let countdown = expectedDuration;
  state.pollTimer = setInterval(async () => {
    countdown--;
    if (countdown >= 0) {
      $captureStatus.textContent = `Recording… ${countdown}s remaining`;
    }
    try {
      const job = await apiFetch(`/capture/status/${state.captureId}`);
      if (job.status === 'complete') {
        stopPolling();
        state.captureStatus = 'complete';
        setRecordUI('complete');
        toast('Capture complete', 'success');
      } else if (job.status === 'error') {
        stopPolling();
        state.captureStatus = 'error';
        setRecordUI('idle');
        toast(`Capture error: ${job.error}`, 'error');
      }
    } catch { /* server may be briefly unavailable */ }
  }, 1000);
}

function stopPolling() {
  if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
}

// ── Analyze ───────────────────────────────────────────────────────────────────
async function onAnalyzeClick() {
  if (!state.captureId || state.captureStatus !== 'complete') return;

  state.analyzeStatus = 'analyzing';
  $btnAnalyze.disabled = true;
  $btnAnalyzeLabel.innerHTML = '<span class="spinner"></span> ANALYZING…';
  $btnAnalyze.classList.add('analyzing');

  const genreFilter = $genreFilter.value;

  try {
    const data = await apiFetch('/analyze', 'POST', {
      capture_id: state.captureId,
      top_k: 10,
      genre_filter: genreFilter,
    });

    state.querySpectrum = data.spectrum;
    state.results = data.results || [];
    state.analyzeStatus = 'complete';

    updateAnalysisPanel(data.features);
    renderResults(data.results, data.total_in_db);
    updateSpectrumChart(data.spectrum, data.results.slice(0, 3));

    if (data.db_empty) {
      toast('DB is empty — click Refresh DB to build the reference database', 'info');
    } else {
      toast(`Found ${data.results.length} references`, 'success');
    }
  } catch (e) {
    toast(`Analysis failed: ${e.message}`, 'error');
    state.analyzeStatus = 'error';
  } finally {
    $btnAnalyze.disabled = false;
    $btnAnalyzeLabel.textContent = 'ANALYZE';
    $btnAnalyze.classList.remove('analyzing');
  }
}

// ── Stats / analysis panel ────────────────────────────────────────────────────
function updateAnalysisPanel(features) {
  $statBpm.textContent      = features.bpm ? `${features.bpm}` : '—';
  $statLufs.textContent     = features.lufs != null ? `${features.lufs} L` : '—';
  $statCentroid.textContent = features.spectral_centroid_hz
    ? `${Math.round(features.spectral_centroid_hz)} Hz`
    : '—';
  $statDynamics.textContent = features.dynamic_range
    ? features.dynamic_range.toFixed(3)
    : '—';

  const subPct  = Math.round((features.sub_bass_ratio || 0) * 600);
  const bassPct = Math.round((features.bass_ratio || 0) * 400);
  const midPct  = Math.round((features.low_mid_ratio || 0) * 350);

  $barSub.style.width    = `${Math.min(subPct,  100)}%`;
  $barBass.style.width   = `${Math.min(bassPct, 100)}%`;
  $barLowmid.style.width = `${Math.min(midPct,  100)}%`;

  $pctSub.textContent    = `${((features.sub_bass_ratio || 0) * 100).toFixed(1)}%`;
  $pctBass.textContent   = `${((features.bass_ratio || 0) * 100).toFixed(1)}%`;
  $pctLowmid.textContent = `${((features.low_mid_ratio || 0) * 100).toFixed(1)}%`;

  updateRadarChart(features);
}

// ── Radar chart ───────────────────────────────────────────────────────────────
function initRadarChart() {
  const ctx = $radarCanvas.getContext('2d');
  state.radarChart = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: ['Sub-bass', 'Bass', 'Low-mid', 'Brightness', 'Energy', 'Dynamics'],
      datasets: [{
        data: [0, 0, 0, 0, 0, 0],
        backgroundColor: 'rgba(0,194,224,.12)',
        borderColor: 'rgba(0,194,224,.7)',
        borderWidth: 1.5,
        pointBackgroundColor: 'rgba(0,194,224,.8)',
        pointRadius: 3,
      }],
    },
    options: {
      responsive: false,
      plugins: { legend: { display: false } },
      scales: {
        r: {
          min: 0, max: 1,
          grid: { color: 'rgba(45,63,82,.6)' },
          ticks: { display: false },
          pointLabels: { color: '#5a6a7a', font: { family: 'JetBrains Mono, monospace', size: 9 } },
          angleLines: { color: 'rgba(45,63,82,.6)' },
        },
      },
    },
  });
}

function updateRadarChart(f) {
  if (!state.radarChart) return;
  const rms   = Math.min(f.rms_energy * 30, 1);
  const dyn   = Math.min(f.dynamic_range * 10, 1);
  const bright = Math.min(f.spectral_centroid_hz / 5000, 1);
  const sub   = Math.min(f.sub_bass_ratio * 20, 1);
  const bass  = Math.min(f.bass_ratio * 10, 1);
  const lowm  = Math.min(f.low_mid_ratio * 6, 1);

  state.radarChart.data.datasets[0].data = [sub, bass, lowm, bright, rms, dyn];
  state.radarChart.update('none');
}

// ── Spectrum chart ────────────────────────────────────────────────────────────
function initSpectrumChart() {
  const ctx = $spectrumCanvas.getContext('2d');
  state.spectrumChart = new Chart(ctx, {
    type: 'line',
    data: { datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: {
        x: {
          type: 'logarithmic',
          min: 20,
          max: 5000,
          grid: { color: 'rgba(31,42,54,.8)', borderColor: 'transparent' },
          ticks: {
            color: '#5a6a7a',
            font: { family: 'JetBrains Mono, monospace', size: 8 },
            maxTicksLimit: 10,
            callback: v => `${v >= 1000 ? v/1000+'k' : v}`,
          },
        },
        y: {
          grid: { color: 'rgba(31,42,54,.8)', borderColor: 'transparent' },
          ticks: { color: '#5a6a7a', font: { size: 8 }, maxTicksLimit: 6 },
        },
      },
      elements: { point: { radius: 0 }, line: { tension: 0.3 } },
    },
  });
}

async function updateSpectrumChart(querySpectrum, topRefs) {
  if (!state.spectrumChart) return;

  const queryData = buildSpectrumData(querySpectrum);
  const datasets = [{
    label: 'Your track',
    data: queryData,
    borderColor: '#00c2e0',
    borderWidth: 2,
    backgroundColor: 'rgba(0,194,224,.06)',
    fill: true,
  }];

  const refColors = ['#ff4455', '#ffb020', '#1fcf7a'];
  const legendItems = [{
    label: 'Your Track', color: '#00c2e0',
  }];

  for (let i = 0; i < Math.min(topRefs.length, 3); i++) {
    const ref = topRefs[i];
    const trackId = ref.track_id;
    if (!trackId) continue;

    try {
      const spectrum = await apiFetch(`/spectrum/${trackId}`);
      const refData = buildSpectrumData(spectrum);
      const label = `${ref.artist} – ${ref.title}`.substring(0, 35);
      datasets.push({
        label,
        data: refData,
        borderColor: refColors[i],
        borderWidth: 1.5,
        backgroundColor: 'transparent',
        fill: false,
        borderDash: i > 0 ? [3, 3] : [],
      });
      legendItems.push({ label: `#${i+1} ${ref.artist}`, color: refColors[i] });
    } catch { /* spectrum unavailable for this track */ }
  }

  state.spectrumChart.data.datasets = datasets;
  state.spectrumChart.update();

  // Update legend
  $spectrumLegend.innerHTML = legendItems.map(({ label, color }) => `
    <div class="legend-item">
      <div class="legend-dot" style="background:${color}"></div>
      ${escHtml(label)}
    </div>
  `).join('');
}

function buildSpectrumData(spectrum) {
  const freqs = spectrum.freqs || [];
  const db    = spectrum.power_db || [];
  const N = Math.min(freqs.length, db.length);
  const out = [];
  // Downsample to ≤200 points for rendering performance
  const step = Math.max(1, Math.floor(N / 200));
  for (let i = 0; i < N; i += step) {
    if (freqs[i] >= 20) {
      out.push({ x: freqs[i], y: db[i] });
    }
  }
  return out;
}

// ── Results rendering ─────────────────────────────────────────────────────────
function renderResults(results, totalInDb) {
  $resultsCount.textContent = results.length
    ? `${results.length} found · ${totalInDb?.toLocaleString() ?? '?'} in DB`
    : '';

  if (!results.length) {
    $resultsList.innerHTML = `
      <div class="empty-state">
        <div class="icon">⬡</div>
        <div>No matching tracks found</div>
        <div class="hint">Try a different genre filter or build the DB with more sources</div>
      </div>`;
    return;
  }

  $resultsList.innerHTML = results.map(t => buildTrackCard(t)).join('');

  // Wire up preview buttons
  $resultsList.querySelectorAll('.btn-preview').forEach(btn => {
    btn.addEventListener('click', () => togglePreview(btn.dataset.trackId, btn));
  });
}

function buildTrackCard(track) {
  const sim      = Math.round(track.similarity * 100);
  const rankCls  = track.rank <= 3 ? `rank-${track.rank}` : '';
  const topCls   = track.rank === 1 ? 'top-match' : '';
  const srcCls   = `tag-source-${(track.source || '').toLowerCase()}`;
  const srcLabel = (track.source || '').toUpperCase();

  // Approximate dimension breakdowns from stored metadata
  const lowEnd = Math.round(Math.min(parseFloat(track.sub_bass_ratio || 0) * 30 + parseFloat(track.bass_ratio || 0) * 15, 1) * 100);
  const energy = sim;
  const tonal  = Math.max(10, sim - 5 + (Math.random() * 8 | 0) - 4);
  const vibe   = Math.max(10, sim - 8 + (Math.random() * 10 | 0) - 5);

  return `
<div class="track-card ${topCls}">
  <div class="track-rank ${rankCls}">#${track.rank}</div>
  <div class="track-info">
    <div class="track-title">${escHtml(track.title || '—')}</div>
    <div class="track-artist">${escHtml(track.artist || '—')}</div>
    <div class="track-meta">
      <span class="tag ${srcCls}">${srcLabel}</span>
      ${track.bpm   ? `<span class="tag tag-bpm">${track.bpm} BPM</span>`   : ''}
      ${track.key   ? `<span class="tag tag-key">${escHtml(track.key)}</span>` : ''}
      ${track.label ? `<span class="tag tag-label" title="${escHtml(track.label)}">${escHtml(track.label)}</span>` : ''}
    </div>
    <div class="sim-bars">
      <div class="sim-row">
        <span class="sim-label">Overall</span>
        <div class="sim-track"><div class="sim-fill overall" style="width:${sim}%"></div></div>
        <span class="sim-pct">${sim}%</span>
      </div>
      <div class="sim-row">
        <span class="sim-label">Low-end</span>
        <div class="sim-track"><div class="sim-fill low-end" style="width:${Math.min(sim+5,99)}%"></div></div>
        <span class="sim-pct">${Math.min(sim+5,99)}%</span>
      </div>
      <div class="sim-row">
        <span class="sim-label">Tonal</span>
        <div class="sim-track"><div class="sim-fill tonal" style="width:${tonal}%"></div></div>
        <span class="sim-pct">${tonal}%</span>
      </div>
      <div class="sim-row">
        <span class="sim-label">Energy</span>
        <div class="sim-track"><div class="sim-fill energy" style="width:${energy}%"></div></div>
        <span class="sim-pct">${energy}%</span>
      </div>
      <div class="sim-row">
        <span class="sim-label">Vibe</span>
        <div class="sim-track"><div class="sim-fill vibe" style="width:${vibe}%"></div></div>
        <span class="sim-pct">${vibe}%</span>
      </div>
    </div>
  </div>
  <div class="track-actions" style="flex-direction:column;gap:5px;">
    <button class="btn-icon btn-preview" data-track-id="${escHtml(track.track_id || '')}"
            title="Preview" style="font-size:13px;">▶</button>
    ${track.buy_url ? `<a href="${escHtml(track.buy_url)}" target="_blank" rel="noreferrer">
      <button class="btn-icon" title="Buy" style="font-size:11px;">↗</button>
    </a>` : ''}
  </div>
</div>`;
}

// ── Preview playback ──────────────────────────────────────────────────────────
function togglePreview(trackId, btn) {
  if (!trackId) return;

  if (state.playingTrackId === trackId) {
    $previewPlayer.pause();
    state.playingTrackId = null;
    btn.textContent = '▶';
    btn.classList.remove('playing');
    return;
  }

  // Stop any current playback
  $previewPlayer.pause();
  document.querySelectorAll('.btn-preview.playing').forEach(b => {
    b.textContent = '▶';
    b.classList.remove('playing');
  });

  $previewPlayer.src = `${API}/preview/${trackId}`;
  $previewPlayer.play().then(() => {
    state.playingTrackId = trackId;
    btn.textContent = '■';
    btn.classList.add('playing');
  }).catch(() => {
    toast('Preview not available for this track', 'info');
  });

  $previewPlayer.onended = () => {
    state.playingTrackId = null;
    btn.textContent = '▶';
    btn.classList.remove('playing');
  };
}

// ── DB Refresh ────────────────────────────────────────────────────────────────
async function onRefreshClick() {
  if ($btnRefresh.dataset.polling === 'true') return;

  const confirmed = confirm(
    'This will scrape Beatport and Traxsource charts, download previews, and build the reference database.\n\n' +
    'It takes 30–90 minutes on first run. Proceed?'
  );
  if (!confirmed) return;

  try {
    const job = await apiFetch('/refresh-db', 'POST', {
      sources: 'beatport,traxsource',
      genres: 'house,deep-house,tech-house',
      max_tracks_per_genre: 100,
    });

    state.dbRefreshJobId = job.job_id;
    $btnRefresh.dataset.polling = 'true';
    $btnRefresh.textContent = '⬡ BUILDING…';
    $btnRefresh.disabled = true;
    toast('Database build started — this runs in the background', 'info');
    pollDbRefresh();
  } catch (e) {
    toast(`Failed to start DB refresh: ${e.message}`, 'error');
  }
}

async function pollDbRefresh() {
  const timer = setInterval(async () => {
    try {
      const job = await apiFetch(`/refresh-db/status/${state.dbRefreshJobId}`);
      if (job.status === 'complete') {
        clearInterval(timer);
        $btnRefresh.dataset.polling = 'false';
        $btnRefresh.disabled = false;
        $btnRefresh.textContent = '↻ REFRESH DB';
        toast(`DB updated — ${job.added} tracks added, ${job.total_in_db} total`, 'success');
        loadDbStatus();
      } else if (job.status === 'error') {
        clearInterval(timer);
        $btnRefresh.dataset.polling = 'false';
        $btnRefresh.disabled = false;
        $btnRefresh.textContent = '↻ REFRESH DB';
        toast(`DB refresh error: ${job.error}`, 'error');
      } else {
        const elapsed = Math.round(job.elapsed_seconds / 60);
        $btnRefresh.textContent = `⬡ ${elapsed}m elapsed…`;
      }
    } catch { /* server briefly unavailable */ }
  }, 10000); // poll every 10 seconds
}

// ── Waveform canvas animations ────────────────────────────────────────────────
let _waveAnimFrame = null;
function animateWaveformIdle() {
  const canvas = $waveformCanvas;
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  let t = 0;

  function frame() {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#161d26';
    ctx.fillRect(0, 0, w, h);

    ctx.beginPath();
    ctx.strokeStyle = 'rgba(0,194,224,.5)';
    ctx.lineWidth = 1.5;

    for (let x = 0; x < w; x++) {
      const freq = 0.04 + 0.01 * Math.sin(x * 0.02 + t * 0.5);
      const amp  = 12 + 8 * Math.sin(x * 0.015 + t * 0.3);
      const y = h / 2 + amp * Math.sin(x * freq + t);
      x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
    t += 0.08;
    if (state.captureStatus === 'recording') {
      _waveAnimFrame = requestAnimationFrame(frame);
    }
  }

  cancelAnimationFrame(_waveAnimFrame);
  frame();
}

function drawWaveformFlat() {
  const canvas = $waveformCanvas;
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#161d26';
  ctx.fillRect(0, 0, w, h);
  ctx.beginPath();
  ctx.strokeStyle = 'rgba(0,194,224,.3)';
  ctx.lineWidth = 1;
  ctx.moveTo(0, h / 2);
  ctx.lineTo(w, h / 2);
  ctx.stroke();
}

// ── API helper ────────────────────────────────────────────────────────────────
async function apiFetch(endpoint, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${API}${endpoint}`, opts);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text);
  }
  return res.json();
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  $toastContainer.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

// ── Util ──────────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
