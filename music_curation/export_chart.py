"""
Export scored candidates into review-friendly formats.

Produces:
  chart_candidates.html  — mobile-first, tap to preview on Beatport,
                           checkbox to shortlist, running count
  chart_candidates.csv   — spreadsheet / Rekordbox-adjacent workflows

Usage:
    python3 export_chart.py                # all scoreable candidates
    python3 export_chart.py --min-score 60
"""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path

HERE = Path(__file__).parent
RANKED = HERE / "ranked_top_30.json"
OUT_HTML = HERE / "chart_candidates.html"
OUT_CSV = HERE / "chart_candidates.csv"

HTML_HEAD = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chart Candidates — Unkle Funk</title>
<style>
:root{--bg:#0E3A3A;--alt:#0A2D2D;--surf:#0F3F45;--line:#1F5152;
--ink:#EFE9DD;--mut:#7FB7AE;--amber:#C25B3A;--teal:#1F7A72}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);margin:0;padding:1rem 0.75rem 5rem;
font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
h1{font-size:1.25rem;margin:0 0 .2rem}
.sub{color:var(--mut);font-size:.85rem;margin:0 0 1rem}
.filters{display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:1rem}
.fbtn{background:transparent;border:1px solid var(--line);color:var(--mut);
border-radius:999px;padding:.35rem .75rem;font-size:.78rem;cursor:pointer}
.fbtn.on{background:var(--teal);color:#121417;border-color:var(--teal)}
.row{display:flex;gap:.6rem;align-items:flex-start;background:var(--surf);
border:1px solid var(--line);border-radius:7px;padding:.7rem .75rem;margin-bottom:.5rem}
.row.picked{border-color:var(--amber);background:#12474b}
.chk{flex:none;width:26px;height:26px;margin-top:.15rem;accent-color:var(--amber)}
.meta{flex:1;min-width:0}
.t{font-weight:600;font-size:.95rem;line-height:1.3}
.a{color:var(--mut);font-size:.85rem;margin-top:.1rem}
.d{color:var(--mut);font-size:.75rem;margin-top:.3rem;letter-spacing:.02em}
.d b{color:var(--ink);font-weight:600}
.sc{flex:none;font-weight:700;color:var(--amber);font-size:.95rem;
min-width:2.6rem;text-align:right}
.lnk{display:inline-block;margin-top:.4rem;color:var(--amber);
text-decoration:none;font-size:.8rem;font-weight:600}
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--alt);
border-top:1px solid var(--line);padding:.7rem .9rem;display:flex;
justify-content:space-between;align-items:center;font-size:.85rem}
.bar b{color:var(--amber);font-size:1.05rem}
.copy{background:var(--amber);color:#121417;border:none;border-radius:5px;
padding:.5rem .9rem;font-weight:700;font-size:.82rem;cursor:pointer}
</style></head><body>
<h1>Chart Candidates</h1>
<p class="sub">Sorted by taste score. Tap a title to preview on Beatport. Tick the ones you want.</p>
<div class="filters">
<button class="fbtn on" data-f="all">All</button>
<button class="fbtn" data-f="70">70+</button>
<button class="fbtn" data-f="60">60+</button>
<button class="fbtn" data-f="picked">Picked</button>
</div>
"""

HTML_TAIL = """
<div class="bar"><span><b id="n">0</b> picked</span>
<button class="copy" onclick="copyPicks()">Copy picks</button></div>
<script>
function upd(){
  const rows=[...document.querySelectorAll('.row')];
  const n=rows.filter(r=>r.querySelector('.chk').checked).length;
  document.getElementById('n').textContent=n;
  rows.forEach(r=>r.classList.toggle('picked',r.querySelector('.chk').checked));
}
document.addEventListener('change',e=>{if(e.target.classList.contains('chk'))upd()});
document.querySelectorAll('.fbtn').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.fbtn').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');
  const f=b.dataset.f;
  document.querySelectorAll('.row').forEach(r=>{
    const s=parseFloat(r.dataset.score);
    const p=r.querySelector('.chk').checked;
    let show=true;
    if(f==='70')show=s>=70; else if(f==='60')show=s>=60; else if(f==='picked')show=p;
    r.style.display=show?'flex':'none';
  });
});
function copyPicks(){
  const out=[...document.querySelectorAll('.row')]
    .filter(r=>r.querySelector('.chk').checked)
    .map((r,i)=>`${i+1}. ${r.dataset.artist} - ${r.dataset.title} [${r.dataset.label}]`)
    .join('\\n');
  if(!out){alert('Nothing picked yet');return}
  navigator.clipboard.writeText(out).then(()=>alert('Copied to clipboard'));
}
</script></body></html>
"""


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-score", type=float, default=0.0)
    args = ap.parse_args()

    data = json.loads(RANKED.read_text())
    rows = [e for e in data if e["score"] >= args.min_score]

    # CSV
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Score", "Artist", "Title", "Label", "BPM", "Key",
                    "Length", "Released", "Genre", "Beatport URL"])
        for e in rows:
            t = e["track"]
            secs = t["duration_seconds"]
            w.writerow([e["score"], t["artist"], t["title"], t["label"],
                        int(t["bpm"]), t["key"], f"{secs//60}:{secs%60:02d}",
                        t["release_date"],
                        ", ".join(t.get("genre_tags") or []), t.get("preview_url", "")])

    # HTML
    parts = [HTML_HEAD]
    for e in rows:
        t = e["track"]
        secs = t["duration_seconds"]
        url = t.get("preview_url") or "#"
        genre = ", ".join(t.get("genre_tags") or [])
        parts.append(f'''<div class="row" data-score="{e['score']}"
 data-artist="{esc(t['artist'])}" data-title="{esc(t['title'])}" data-label="{esc(t['label'])}">
<input type="checkbox" class="chk">
<div class="meta">
<div class="t"><a class="lnk" style="font-size:.95rem;color:var(--ink)" href="{esc(url)}" target="_blank">{esc(t['title'])}</a></div>
<div class="a">{esc(t['artist'])}</div>
<div class="d"><b>{esc(t['label'])}</b> &middot; {int(t['bpm'])} BPM &middot; {esc(t['key'])} &middot; {secs//60}:{secs%60:02d} &middot; {esc(t['release_date'])}{(' &middot; ' + esc(genre)) if genre else ''}</div>
<a class="lnk" href="{esc(url)}" target="_blank">Preview on Beatport &rarr;</a>
</div>
<div class="sc">{e['score']:.0f}</div>
</div>''')
    parts.append(HTML_TAIL)
    OUT_HTML.write_text("\n".join(parts), encoding="utf-8")

    print(f"{len(rows)} candidates exported")
    print(f"  {OUT_HTML.name}")
    print(f"  {OUT_CSV.name}")


if __name__ == "__main__":
    main()
