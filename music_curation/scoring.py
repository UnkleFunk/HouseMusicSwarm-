"""
Unkle Funk — Music Curation Scoring Engine
=============================================

Takes candidate tracks (from music_discovery/) and scores them against
the taste profile in profile.yaml. Returns explainable scores.

Design principles:
  - Explainable. No black-box neural net. Every score comes with a
    per-feature breakdown so the human (Glenn) knows why a track
    scored 84 vs 41 and can hand-tune the profile if wrong.
  - Compression, not automation. Goal: turn a 50:1 listen ratio into
    a 5:1. Human still picks the top 10. Engine surfaces the
    right ~30 candidates.
  - Learn incrementally. Feedback (thumbs up/down + reason tags)
    persists to feedback.sqlite and gets folded back into artist
    scores and label tier adjustments on schedule.

Usage:
  from scoring import Scorer
  scorer = Scorer.load_default()
  result = scorer.score(track)
  print(result.total, result.explain())
"""

from __future__ import annotations

import math
import sqlite3
import yaml
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


PROFILE_PATH = Path(__file__).parent / "profile.yaml"
LEARNED_PATH = Path(__file__).parent / "profile.learned.yaml"
FEEDBACK_DB = Path(__file__).parent / "feedback.sqlite"


# ---------------------------------------------------------------
# Data types
# ---------------------------------------------------------------

@dataclass
class Track:
    """A candidate track from Beatport or Traxsource."""
    id: str
    title: str
    artist: str
    label: str
    bpm: float
    key: str                       # Camelot notation, e.g. "7A"
    duration_seconds: int
    release_date: str              # ISO 8601
    genre_tags: list[str] = field(default_factory=list)
    sonic_tags: list[str] = field(default_factory=list)
    vocal_type: str | None = None  # "soulful lead", "vocal chops", etc.
    is_reissue: bool = False
    preview_url: str | None = None
    source: str = "beatport"


@dataclass
class ScoreBreakdown:
    """Per-feature score contributions with human-readable reasons."""
    total: float
    features: dict[str, dict[str, Any]] = field(default_factory=dict)
    rejected: bool = False
    rejection_reason: str | None = None

    def explain(self) -> str:
        """Human-readable breakdown for the review UI."""
        if self.rejected:
            return f"REJECTED: {self.rejection_reason}"
        lines = [f"Total: {self.total:.1f} / 100"]
        for feature, info in self.features.items():
            lines.append(
                f"  {feature:>10s}: {info['score']:.1f} × {info['weight']:>4.1f}%  "
                f"→ {info['contribution']:.1f}   ({info['reason']})"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------

class Scorer:
    def __init__(self, profile: dict, learned: dict | None = None):
        self.profile = profile
        self.learned = learned or {}
        self._label_tier_map = self._build_label_tier_map()
        self._artist_scores = self._merge_artist_scores()

    @classmethod
    def load_default(cls) -> "Scorer":
        profile = yaml.safe_load(PROFILE_PATH.read_text())
        learned = {}
        if LEARNED_PATH.exists():
            learned = yaml.safe_load(LEARNED_PATH.read_text()) or {}
        return cls(profile, learned)

    def _build_label_tier_map(self) -> dict[str, tuple[int, float]]:
        m = {}
        for tier_key in ("tier_1", "tier_2"):
            tier = self.profile["labels"]["tiers"][tier_key]
            level = 1 if tier_key == "tier_1" else 2
            for name in tier["names"]:
                m[name.lower()] = (level, float(tier["score"]))
        return m

    def _merge_artist_scores(self) -> dict[str, float]:
        seed = dict(self.profile["artists"].get("seed_scores", {}) or {})
        learned = dict(self.learned.get("artists", {}) or {})
        merged = {k.lower(): float(v) for k, v in seed.items()}
        merged.update({k.lower(): float(v) for k, v in learned.items()})
        return merged

    # -----------------------------------------------------------
    # Feature scorers — each returns (score_0_100, reason_string)
    # -----------------------------------------------------------

    def _score_bpm(self, bpm: float) -> tuple[float, str]:
        c = self.profile["bpm"]
        if bpm < c["reject_below"] or bpm > c["reject_above"]:
            return 0.0, f"{bpm:.1f} outside reject band"
        pref_lo, pref_hi = c["preferred"]
        acc_lo, acc_hi = c["acceptable"]
        tol_lo, tol_hi = c["tolerated"]
        if pref_lo <= bpm <= pref_hi:
            return 100.0, f"{bpm:.1f} in bullseye {pref_lo}-{pref_hi}"
        if acc_lo <= bpm <= acc_hi:
            return 75.0, f"{bpm:.1f} in acceptable {acc_lo}-{acc_hi}"
        if tol_lo <= bpm <= tol_hi:
            return 45.0, f"{bpm:.1f} tolerable"
        return 15.0, f"{bpm:.1f} edge of band"

    def _score_key(self, key: str) -> tuple[float, str]:
        c = self.profile["key"]
        if not key:
            return 50.0, "no key info"
        is_minor = key.upper().endswith("A")
        if is_minor:
            base = 80.0
            if key.upper() in c.get("favored_camelot", []):
                base = 100.0
            return base * c.get("minor_bonus", 1.0), f"{key} minor"
        else:
            return 80.0 * c.get("major_penalty", 0.7), f"{key} major"

    def _score_label(self, label: str) -> tuple[float, str, bool]:
        """Returns (score, reason, rejected)."""
        c = self.profile["labels"]
        label_lower = label.lower() if label else ""
        for bad in c.get("reject_labels", []) or []:
            if bad.lower() == label_lower:
                return 0.0, f"label '{label}' on reject list", True
        if label_lower in self._label_tier_map:
            level, score = self._label_tier_map[label_lower]
            return score, f"'{label}' Tier {level}", False
        fallback = c["tiers"]["tier_3_fallback"]["score"]
        return float(fallback), f"'{label}' not in tiers → fallback", False

    def _score_artist(self, artist: str) -> tuple[float, str]:
        artist_lower = artist.lower() if artist else ""
        if artist_lower in self._artist_scores:
            score = self._artist_scores[artist_lower]
            return score, f"'{artist}' → {score:.0f} from history"
        return 50.0, f"'{artist}' unknown → neutral 50"

    def _score_duration(self, seconds: int) -> tuple[float, str]:
        c = self.profile["duration"]
        pref_lo, pref_hi = c["preferred_seconds"]
        acc_lo, acc_hi = c["acceptable_seconds"]
        if pref_lo <= seconds <= pref_hi:
            return 100.0, f"{seconds//60}:{seconds%60:02d} DJ tool"
        if acc_lo <= seconds <= acc_hi:
            return 70.0, f"{seconds//60}:{seconds%60:02d} acceptable"
        if seconds < c.get("penalty_below", 300):
            return 20.0, f"{seconds//60}:{seconds%60:02d} likely radio edit"
        if seconds > c.get("penalty_above", 720):
            return 40.0, f"{seconds//60}:{seconds%60:02d} very long, check for filler"
        return 55.0, f"{seconds//60}:{seconds%60:02d} outside preferred"

    def _score_sonic(self, sonic_tags: list[str]) -> tuple[float, str]:
        c = self.profile["sonic"]
        if not sonic_tags:
            return 50.0, "no sonic tags"
        pos = c.get("positive_descriptors", {}) or {}
        neg = c.get("negative_descriptors", {}) or {}
        tag_lower = [t.lower() for t in sonic_tags]
        pos_hits = sum(pos.get(t, 0) for t in tag_lower if t in pos)
        neg_hits = sum(neg.get(t, 0) for t in tag_lower if t in neg)
        raw = pos_hits + neg_hits
        # squash to 0-100 with a sigmoid so extremes don't dominate
        squashed = 100.0 / (1.0 + math.exp(-raw))
        matched = [t for t in tag_lower if t in pos or t in neg]
        return squashed, f"tags: {', '.join(matched) or 'none matched'}"

    def _score_vocal(self, vocal_type: str | None) -> tuple[float, str]:
        c = self.profile["vocal"]
        if not vocal_type:
            return 60.0, "instrumental / unspecified"
        vt = vocal_type.lower()
        if vt in [t.lower() for t in c.get("reward_types", []) or []]:
            return 95.0, f"'{vocal_type}' rewarded"
        if vt in [t.lower() for t in c.get("penalize_types", []) or []]:
            return 25.0, f"'{vocal_type}' penalized"
        return 55.0, f"'{vocal_type}' neutral"

    def _score_recency(self, release_date: str, is_reissue: bool, label: str) -> tuple[float, str]:
        from datetime import date, datetime
        c = self.profile["recency"]
        try:
            rd = datetime.fromisoformat(release_date).date()
        except (ValueError, TypeError):
            return 50.0, "no release date"
        days = (date.today() - rd).days
        if days <= c["preferred_days"]:
            return 100.0, f"{days}d old"
        if days <= c["acceptable_days"]:
            return 70.0, f"{days}d old"
        if is_reissue and label in (c.get("reissue_bonus_labels", []) or []):
            return 80.0, f"reissue on {label}"
        return 30.0, f"{days}d old, no reissue bonus"

    # -----------------------------------------------------------
    # Public API
    # -----------------------------------------------------------

    def score(self, track: Track) -> ScoreBreakdown:
        """Score a candidate track. Returns breakdown with per-feature reasons."""
        breakdown = ScoreBreakdown(total=0.0)

        # Label first — can short-circuit as rejection
        label_score, label_reason, label_rejected = self._score_label(track.label)
        if label_rejected:
            breakdown.rejected = True
            breakdown.rejection_reason = label_reason
            return breakdown

        # BPM band check — can also short-circuit
        bpm_score, bpm_reason = self._score_bpm(track.bpm)
        if bpm_score == 0.0:
            breakdown.rejected = True
            breakdown.rejection_reason = bpm_reason
            return breakdown

        feature_scores = {
            "bpm":      (bpm_score,     self.profile["bpm"]["weight"],       bpm_reason),
            "key":      (*self._score_key(track.key),      self.profile["key"]["weight"]),
            "label":    (label_score,   self.profile["labels"]["weight"],    label_reason),
            "artist":   (*self._score_artist(track.artist), self.profile["artists"]["weight"]),
            "duration": (*self._score_duration(track.duration_seconds), self.profile["duration"]["weight"]),
            "sonic":    (*self._score_sonic(track.sonic_tags),  self.profile["sonic"]["weight"]),
            "vocal":    (*self._score_vocal(track.vocal_type),  self.profile["vocal"]["weight"]),
            "recency":  (*self._score_recency(track.release_date, track.is_reissue, track.label),
                                                                  self.profile["recency"]["weight"]),
        }

        # Some tuples above are (score, reason, weight); normalize.
        clean: dict[str, tuple[float, float, str]] = {}
        for name, val in feature_scores.items():
            if len(val) == 3 and isinstance(val[1], (int, float)) and isinstance(val[2], str):
                score, weight, reason = val
            else:  # (score, reason, weight)
                score, reason, weight = val
            clean[name] = (float(score), float(weight), reason)

        total = 0.0
        total_weight = sum(w for _, w, _ in clean.values())
        for name, (score, weight, reason) in clean.items():
            contribution = score * (weight / total_weight)
            total += contribution
            breakdown.features[name] = {
                "score": score,
                "weight": weight,
                "contribution": contribution,
                "reason": reason,
            }
        breakdown.total = total
        return breakdown

    # -----------------------------------------------------------
    # Feedback loop
    # -----------------------------------------------------------

    def record_feedback(
        self,
        track: Track,
        decision: str,             # "yes" | "no" | "maybe"
        reasons: list[str] = None, # ["too tech", "wrong vibe", ...]
    ) -> None:
        """Persist a review decision. Feeds the learning loop."""
        assert decision in ("yes", "no", "maybe")
        with sqlite3.connect(FEEDBACK_DB) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY,
                    track_id TEXT NOT NULL,
                    title TEXT,
                    artist TEXT,
                    label TEXT,
                    bpm REAL,
                    key TEXT,
                    decision TEXT NOT NULL,
                    reasons TEXT,
                    ts DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "INSERT INTO feedback (track_id, title, artist, label, bpm, key, decision, reasons) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (track.id, track.title, track.artist, track.label,
                 track.bpm, track.key, decision, ",".join(reasons or []))
            )


# ---------------------------------------------------------------
# Sanity check when run directly
# ---------------------------------------------------------------

if __name__ == "__main__":
    scorer = Scorer.load_default()

    # A track that should score high — Tier 1 label, right BPM, known artist
    good = Track(
        id="test_1",
        title="Late Night Mailman",
        artist="Dantiez Saunderson",
        label="Toolroom Records",
        bpm=122.0,
        key="8A",
        duration_seconds=430,
        release_date="2026-06-15",
        sonic_tags=["warm", "analog", "chicago house"],
        vocal_type="soulful lead",
    )
    r = scorer.score(good)
    print("=== SHOULD SCORE HIGH ===")
    print(r.explain())
    print()

    # A track that should reject — wrong label
    bad = Track(
        id="test_2",
        title="Festival Peaker",
        artist="Some EDM Producer",
        label="Spinnin' Records",
        bpm=126.0,
        key="7B",
        duration_seconds=195,
        release_date="2026-07-01",
        sonic_tags=["big room", "edm"],
    )
    r = scorer.score(bad)
    print("=== SHOULD REJECT ===")
    print(r.explain())
    print()

    # A borderline case — Tier 2 label, right BPM, unknown artist
    borderline = Track(
        id="test_3",
        title="Warehouse Cut",
        artist="Some New Producer",
        label="Local Talk",
        bpm=124.0,
        key="4A",
        duration_seconds=520,
        release_date="2026-05-20",
        sonic_tags=["warm", "dubby"],
    )
    r = scorer.score(borderline)
    print("=== BORDERLINE ===")
    print(r.explain())
