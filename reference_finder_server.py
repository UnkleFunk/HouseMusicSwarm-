"""Standalone Reference Finder server — run with: python reference_finder_server.py

Serves the UI at http://localhost:8081 and handles all reference finder API calls.
Run alongside the main agency server (server.py on port 8080).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from reference_finder_agent.audio_utils import extract_features
from reference_finder_agent.tools.ListAudioDevices import ListAudioDevices
from reference_finder_agent.tools.BuildDatabase import CHROMADB_DIR, COLLECTION_NAME, PREVIEW_DIR

STATIC_DIR = Path(__file__).parent / "website" / "reference-finder"

app = FastAPI(title="Reference Finder", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job state ───────────────────────────────────────────────────────

_executor = ThreadPoolExecutor(max_workers=4)
_capture_jobs: dict[str, dict] = {}  # job_id → {status, path, error, ...}
_db_refresh_jobs: dict[str, dict] = {}


# ── Request/response models ───────────────────────────────────────────────────

class CaptureStartRequest(BaseModel):
    device_index: int
    duration_seconds: int = 30


class AnalyzeRequest(BaseModel):
    capture_id: str
    top_k: int = 10
    genre_filter: str = ""


class RefreshDbRequest(BaseModel):
    sources: str = "beatport,traxsource"
    genres: str = "house,deep-house,tech-house"
    max_tracks_per_genre: int = 100


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/devices")
def get_devices():
    tool = ListAudioDevices()
    raw = tool.run()
    return JSONResponse(content=json.loads(raw))


@app.get("/api/db-status")
def db_status():
    if not CHROMADB_DIR.exists():
        return {"total": 0, "last_refresh": None, "ready": False}
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMADB_DIR))
        collection = client.get_or_create_collection(COLLECTION_NAME)
        count = collection.count()
        return {"total": count, "ready": count > 0}
    except Exception as exc:
        return {"total": 0, "ready": False, "error": str(exc)}


@app.post("/api/capture/start")
def capture_start(req: CaptureStartRequest):
    job_id = str(uuid.uuid4())
    _capture_jobs[job_id] = {"status": "recording", "started_at": time.time()}

    def _do_capture():
        import sounddevice as sd
        import soundfile as sf
        import tempfile
        import numpy as np

        try:
            device_info = sd.query_devices(req.device_index)
            sr = int(device_info["default_samplerate"])
            ch = min(int(device_info["max_input_channels"]), 2)
            frames = sd.rec(
                int(sr * req.duration_seconds),
                samplerate=sr,
                channels=ch,
                dtype="float32",
                device=req.device_index,
            )
            sd.wait()
            mono = frames.mean(axis=1) if ch > 1 else frames.flatten()
            path = os.path.join(tempfile.gettempdir(), f"ref_capture_{job_id}.wav")
            sf.write(path, mono, sr)
            _capture_jobs[job_id].update({"status": "complete", "path": path, "sample_rate": sr})
        except Exception as exc:
            _capture_jobs[job_id].update({"status": "error", "error": str(exc)})

    _executor.submit(_do_capture)
    return {"capture_id": job_id, "status": "recording", "duration_seconds": req.duration_seconds}


@app.get("/api/capture/status/{capture_id}")
def capture_status(capture_id: str):
    job = _capture_jobs.get(capture_id)
    if not job:
        raise HTTPException(status_code=404, detail="Capture job not found")
    elapsed = time.time() - job.get("started_at", time.time())
    return {**job, "elapsed_seconds": round(elapsed, 1)}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    job = _capture_jobs.get(req.capture_id)
    if not job or job["status"] != "complete":
        raise HTTPException(status_code=400, detail="Capture not complete")

    audio_path = job["path"]
    if not Path(audio_path).exists():
        raise HTTPException(status_code=404, detail="Captured audio file not found")

    # Feature extraction
    try:
        features = extract_features(audio_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Feature extraction failed: {exc}")

    # Search
    if not CHROMADB_DIR.exists() or not any(CHROMADB_DIR.iterdir()):
        return {
            "features": features["metadata"],
            "spectrum": features["spectrum"],
            "results": [],
            "db_empty": True,
            "message": "Reference database is empty. Use /api/refresh-db to build it first.",
        }

    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMADB_DIR))
        collection = client.get_or_create_collection(COLLECTION_NAME)
        count = collection.count()
        n = min(req.top_k, count)

        where = {"genre": {"$in": [req.genre_filter]}} if req.genre_filter else None
        results = collection.query(
            query_embeddings=[features["vector"]],
            n_results=n,
            where=where,
            include=["metadatas", "distances", "documents"],
        )

        tracks = []
        for i, meta in enumerate(results["metadatas"][0]):
            distance = results["distances"][0][i]
            similarity = round(max(0.0, 1.0 - distance / 2.0), 3)
            # Pull spectrum out separately (large payload)
            spectrum_json = meta.pop("spectrum_json", None)
            tracks.append({
                **meta,
                "similarity": similarity,
                "rank": i + 1,
                "track_id": results.get("ids", [[]])[0][i] if results.get("ids") else "",
            })

        return {
            "features": features["metadata"],
            "spectrum": features["spectrum"],
            "results": tracks,
            "total_in_db": count,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}")


@app.get("/api/spectrum/{track_id}")
def get_track_spectrum(track_id: str):
    """Return the stored frequency spectrum for a reference track (for overlay chart)."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMADB_DIR))
        collection = client.get_or_create_collection(COLLECTION_NAME)
        result = collection.get(ids=[track_id], include=["metadatas"])
        if not result["ids"]:
            raise HTTPException(status_code=404, detail="Track not found")
        meta = result["metadatas"][0]
        spectrum_json = meta.get("spectrum_json", "{}")
        return JSONResponse(content=json.loads(spectrum_json))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/preview/{track_id}")
def stream_preview(track_id: str):
    """Stream the cached preview MP3 for in-browser playback."""
    preview_path = PREVIEW_DIR / f"{track_id}.mp3"
    if not preview_path.exists():
        raise HTTPException(status_code=404, detail="Preview not available")
    return FileResponse(
        path=str(preview_path),
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes"},
    )


@app.post("/api/refresh-db")
def refresh_db(req: RefreshDbRequest):
    """Trigger a background database build/refresh. Returns a job ID to poll."""
    job_id = str(uuid.uuid4())
    _db_refresh_jobs[job_id] = {"status": "running", "started_at": time.time()}

    def _do_refresh():
        from reference_finder_agent.tools.BuildDatabase import BuildDatabase as BD
        tool = BD(
            sources=req.sources,
            genres=req.genres,
            max_tracks_per_genre=req.max_tracks_per_genre,
            refresh=True,
        )
        try:
            result = json.loads(tool.run())
            _db_refresh_jobs[job_id].update({"status": "complete", **result})
        except Exception as exc:
            _db_refresh_jobs[job_id].update({"status": "error", "error": str(exc)})

    _executor.submit(_do_refresh)
    return {"job_id": job_id, "status": "running"}


@app.get("/api/refresh-db/status/{job_id}")
def refresh_db_status(job_id: str):
    job = _db_refresh_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Refresh job not found")
    elapsed = time.time() - job.get("started_at", time.time())
    return {**job, "elapsed_seconds": round(elapsed, 1)}


# ── Static file serving ───────────────────────────────────────────────────────

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:
    @app.get("/")
    def root():
        return {"message": "Reference Finder API running. UI files not found — check website/reference-finder/"}


if __name__ == "__main__":
    print("Reference Finder running at http://localhost:8081")
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="warning")
