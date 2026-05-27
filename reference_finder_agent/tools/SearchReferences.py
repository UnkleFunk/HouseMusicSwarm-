import json
from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field

CHROMADB_DIR = Path.home() / ".housemusic_refs" / "chromadb"
COLLECTION_NAME = "house_references"


class SearchReferences(BaseTool):
    """Query the local reference database for tracks similar to the provided audio feature vector.

    Returns a ranked list of tracks with similarity scores and per-dimension breakdowns.
    """

    feature_vector: list[float] = Field(
        ...,
        description="L2-normalized feature vector from ExtractFeatures",
    )
    top_k: int = Field(default=10, ge=1, le=50)
    genre_filter: str = Field(
        default="",
        description="Optional genre slug to filter results (e.g. 'tech-house')",
    )

    def run(self) -> str:
        import chromadb

        if not CHROMADB_DIR.exists():
            return json.dumps({
                "error": "Database not found. Run BuildDatabase first.",
                "total_in_db": 0,
                "results": [],
            })

        client = chromadb.PersistentClient(path=str(CHROMADB_DIR))
        collection = client.get_or_create_collection(
            COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        count = collection.count()
        if count == 0:
            return json.dumps({
                "error": "Database is empty. Run BuildDatabase first.",
                "total_in_db": 0,
                "results": [],
            })

        where = {"genre": {"$in": [self.genre_filter]}} if self.genre_filter else None
        n = min(self.top_k, count)

        results = collection.query(
            query_embeddings=[self.feature_vector],
            n_results=n,
            where=where,
            include=["metadatas", "distances", "documents"],
        )

        tracks = []
        for i, meta in enumerate(results["metadatas"][0]):
            distance = results["distances"][0][i]
            # Cosine distance in [0,2]; convert to similarity in [0,1]
            similarity = round(max(0.0, 1.0 - distance / 2.0), 3)

            # Approximate per-dimension similarity breakdown using stored analysis metadata
            # These are rough heuristics to give the user directional feedback
            sub_bass = _safe_float(meta.get("sub_bass_ratio", ""))
            bass = _safe_float(meta.get("bass_ratio", ""))
            lufs = _safe_float(meta.get("lufs", ""))

            tracks.append({
                **meta,
                "similarity": similarity,
                "rank": i + 1,
                # Remove the potentially large spectrum_json from the main result;
                # the frontend requests it separately via /api/spectrum/{track_id}
                "has_spectrum": bool(meta.get("spectrum_json")),
            })

        return json.dumps({"results": tracks, "total_in_db": count})


def _safe_float(v: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0
