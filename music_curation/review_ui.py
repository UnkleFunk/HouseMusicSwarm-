"""
Unkle Funk — Chart Candidate Review UI
========================================

Local Flask app. Run on the Hackintosh, bookmark on your phone, review
candidates on break. Shows the scorer's top 30 with embedded 30s
previews, score breakdown, and one-tap yes/no/maybe + reason tags.

Run:
    export SEARCH_API_KEY=your_key
    python3 discovery.py          # fetches + scores, writes ranked_top_30.json
    python3 review_ui.py          # serves the review interface

Then visit http://<hackintosh-ip>:5678 from your phone (same wifi/tailscale).
"""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

from scoring import Scorer, Track

app = Flask(__name__)

RANKED_PATH = Path(__file__).parent / "ranked_top_30.json"

REASON_TAGS = [
    "too tech", "wrong vibe", "heard it too much", "weak groove",
    "vocal doesn't fit", "not my BPM", "label mismatch", "loved it",
    "perfect for a set", "surprising — more like this",
]

PAGE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>75 Deep — Chart Review</title>
<style>
  :root {
    --bg: #0E3A3A; --bg-alt: #0A2D2D; --surface: #0F3F45; --line: #1F5152;
    --ink: #EFE9DD; --ink-muted: #7FB7AE; --amber: #C25B3A; --teal: #1F7A72;
  }
  * { box-sizing: border-box; }
  body {
    background: var(--bg); color: var(--ink);
    font: 16px/1.5 system-ui, -apple-system, sans-serif;
    margin: 0; padding: 1rem;
  }
  h1 { font-size: 1.3rem; margin: 0 0 0.25rem; }
  .sub { color: var(--ink-muted); font-size: 0.9rem; margin-bottom: 1.5rem; }
  .card {
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 8px; padding: 1rem; margin-bottom: 1rem;
    transition: opacity 0.3s ease;
  }
  .card.decided { opacity: 0.35; }
  .card-head { display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; }
  .track-title { font-weight: 600; font-size: 1.05rem; }
  .track-artist { color: var(--ink-muted); }
  .score {
    font-weight: 700; font-size: 1.1rem; color: var(--amber);
    flex: none;
  }
  .label { font-size: 0.85rem; color: var(--ink-muted); margin-top: 0.15rem; }
  .explain {
    font-size: 0.78rem; color: var(--ink-muted); margin-top: 0.6rem;
    background: var(--bg-alt); border-radius: 4px; padding: 0.5rem;
    white-space: pre-wrap; display: none;
  }
  .explain.open { display: block; }
  .toggle-explain {
    background: none; border: none; color: var(--teal);
    font-size: 0.78rem; padding: 0.3rem 0; cursor: pointer;
  }
  .preview-link {
    display: inline-block; margin-top: 0.6rem; color: var(--amber);
    text-decoration: none; font-size: 0.85rem; font-weight: 600;
  }
  .actions { display: flex; gap: 0.5rem; margin-top: 0.75rem; }
  .btn {
    flex: 1; padding: 0.65rem; border-radius: 6px; border: 1px solid var(--line);
    background: transparent; color: var(--ink); font-size: 0.95rem;
    cursor: pointer; font-weight: 600;
  }
  .btn.yes { border-color: #4a9d7f; }
  .btn.yes.active { background: #4a9d7f; color: #121417; }
  .btn.no { border-color: var(--amber); }
  .btn.no.active { background: var(--amber); color: #121417; }
  .btn.maybe.active { background: var(--teal); color: #121417; }
  .tags { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.6rem; }
  .tag {
    font-size: 0.75rem; padding: 0.3rem 0.6rem; border-radius: 999px;
    border: 1px solid var(--line); background: transparent; color: var(--ink-muted);
    cursor: pointer;
  }
  .tag.active { background: var(--teal); color: #121417; border-color: var(--teal); }
  .empty { text-align: center; color: var(--ink-muted); padding: 3rem 1rem; }
</style>
</head>
<body>
  <h1>75 Deep — Chart Candidates</h1>
  <p class="sub" id="progress"></p>
  <div id="cards"></div>
  <div class="empty" id="empty" style="display:none">
    No candidates loaded. Run <code>discovery.py</code> first.
  </div>

<script>
let candidates = [];
let decisions = {};

async function load() {
  const res = await fetch('/api/candidates');
  candidates = await res.json();
  if (!candidates.length) {
    document.getElementById('empty').style.display = 'block';
    return;
  }
  render();
}

function updateProgress() {
  const done = Object.keys(decisions).length;
  document.getElementById('progress').textContent =
    `${done} / ${candidates.length} reviewed`;
}

function render() {
  const container = document.getElementById('cards');
  container.innerHTML = candidates.map((c, i) => {
    const t = c.track;
    return `
      <div class="card" id="card-${i}">
        <div class="card-head">
          <div>
            <div class="track-title">${t.title}</div>
            <div class="track-artist">${t.artist}</div>
          </div>
          <div class="score">${c.score.toFixed(1)}</div>
        </div>
        <div class="label">${t.label || 'no label'} · ${t.bpm} BPM · ${t.key || '—'} · ${t.source}</div>
        <button class="toggle-explain" onclick="toggleExplain(${i})">show score breakdown</button>
        <div class="explain" id="explain-${i}">${c.explain}</div>
        ${t.preview_url ? `<a class="preview-link" href="${t.preview_url}" target="_blank">▶ open on ${t.source}</a>` : ''}
        <div class="actions">
          <button class="btn yes" onclick="decide(${i}, 'yes')">👍 Yes</button>
          <button class="btn maybe" onclick="decide(${i}, 'maybe')">🤔 Maybe</button>
          <button class="btn no" onclick="decide(${i}, 'no')">👎 No</button>
        </div>
        <div class="tags" id="tags-${i}">
          ${REASON_TAGS_PLACEHOLDER.map(tag =>
            `<button class="tag" onclick="toggleTag(${i}, '${tag}')">${tag}</button>`
          ).join('')}
        </div>
      </div>
    `;
  }).join('');
  updateProgress();
}

function toggleExplain(i) {
  document.getElementById(`explain-${i}`).classList.toggle('open');
}

function decide(i, decision) {
  decisions[i] = decisions[i] || { reasons: [] };
  decisions[i].decision = decision;
  const card = document.getElementById(`card-${i}`);
  card.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
  card.querySelector(`.btn.${decision}`).classList.add('active');
  card.classList.add('decided');
  submitDecision(i);
  updateProgress();
}

function toggleTag(i, tag) {
  decisions[i] = decisions[i] || { reasons: [] };
  const idx = decisions[i].reasons.indexOf(tag);
  if (idx >= 0) decisions[i].reasons.splice(idx, 1);
  else decisions[i].reasons.push(tag);
  event.target.classList.toggle('active');
  if (decisions[i].decision) submitDecision(i);
}

async function submitDecision(i) {
  const c = candidates[i];
  const d = decisions[i];
  if (!d.decision) return;
  await fetch('/api/feedback', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      track: c.track,
      decision: d.decision,
      reasons: d.reasons || [],
    }),
  });
}

load();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    html = PAGE_TEMPLATE.replace(
        "REASON_TAGS_PLACEHOLDER", json.dumps(REASON_TAGS)
    )
    return render_template_string(html)


@app.route("/api/candidates")
def api_candidates():
    if not RANKED_PATH.exists():
        return jsonify([])
    return jsonify(json.loads(RANKED_PATH.read_text()))


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    payload = request.get_json()
    track_data = payload["track"]
    decision = payload["decision"]
    reasons = payload.get("reasons", [])

    track = Track(
        id=track_data["id"], title=track_data["title"], artist=track_data["artist"],
        label=track_data["label"], bpm=track_data["bpm"], key=track_data["key"],
        duration_seconds=track_data["duration_seconds"],
        release_date=track_data["release_date"],
        genre_tags=track_data.get("genre_tags", []),
        sonic_tags=track_data.get("sonic_tags", []),
        vocal_type=track_data.get("vocal_type"),
        is_reissue=track_data.get("is_reissue", False),
        preview_url=track_data.get("preview_url"),
        source=track_data.get("source", "beatport"),
    )
    scorer = Scorer.load_default()
    scorer.record_feedback(track, decision, reasons)
    return jsonify({"ok": True})


@app.route("/api/final10")
def api_final10():
    """Returns tracks marked 'yes' — ready for publish.py to embed."""
    import sqlite3
    db_path = Path(__file__).parent / "feedback.sqlite"
    if not db_path.exists():
        return jsonify([])
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM feedback WHERE decision='yes' ORDER BY ts DESC LIMIT 10"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    print("Review UI starting at http://0.0.0.0:5678")
    print("From your phone (same network): http://<hackintosh-ip>:5678")
    app.run(host="0.0.0.0", port=5678, debug=False)
