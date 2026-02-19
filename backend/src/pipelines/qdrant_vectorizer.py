import os
import sys
import json
import hashlib

import requests


def chunk_text(text, chunk_size=1000, overlap=100):
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def pseudo_embedding(text, dims=384):
    """Deterministic fallback embedding for wiring + smoke tests."""
    vector = [0.0] * dims
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], "big") % dims
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[idx] += sign

    norm = sum(v * v for v in vector) ** 0.5
    if norm > 0:
        vector = [v / norm for v in vector]
    return vector


def qdrant_headers():
    api_key = os.environ.get("IDMS_QDRANT_API_KEY", "").strip()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    return headers


def ensure_collection(base_url, collection):
    url = f"{base_url}/collections/{collection}"
    r = requests.get(url, timeout=10, headers=qdrant_headers())
    if r.status_code == 200:
        return

    payload = {
        "vectors": {
            "size": 384,
            "distance": "Cosine"
        }
    }
    r = requests.put(url, json=payload, timeout=15, headers=qdrant_headers())
    r.raise_for_status()


def upsert_points(base_url, collection, points):
    url = f"{base_url}/collections/{collection}/points?wait=true"
    payload = {"points": points}
    r = requests.put(url, json=payload, timeout=30, headers=qdrant_headers())
    r.raise_for_status()
    return r.json()


def index_document(doc_id, content, metadata):
    base_url = os.environ.get("IDMS_QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
    collection = os.environ.get("IDMS_QDRANT_COLLECTION", "idms_docs")

    chunks = chunk_text(content)
    if not chunks:
        return {"status": "success", "doc_id": doc_id, "chunks_indexed": 0}

    ensure_collection(base_url, collection)

    points = []
    for idx, chunk in enumerate(chunks):
        point_id_seed = f"{doc_id}:{idx}"
        point_id = int(hashlib.sha256(point_id_seed.encode("utf-8")).hexdigest()[:16], 16)
        points.append(
            {
                "id": point_id,
                "vector": pseudo_embedding(chunk),
                "payload": {
                    "doc_id": doc_id,
                    "chunk_index": idx,
                    "chunk_text": chunk,
                    "category": metadata.get("category"),
                    "entity": metadata.get("entity"),
                    "status": metadata.get("status"),
                },
            }
        )

    api_result = upsert_points(base_url, collection, points)
    return {
        "status": "success",
        "doc_id": doc_id,
        "collection": collection,
        "chunks_indexed": len(points),
        "api": api_result,
    }


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "message": "Usage: qdrant_vectorizer.py <doc_id> <content> [metadata_json]"}))
        sys.exit(1)

    doc_id = sys.argv[1]
    content = sys.argv[2]
    metadata = {}

    if len(sys.argv) >= 4:
        try:
            metadata = json.loads(sys.argv[3])
        except json.JSONDecodeError:
            metadata = {}

    try:
        result = index_document(doc_id, content, metadata)
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
