import requests, os
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

def scroll(collection, limit=20, offset=None, filters=None):
    body = {"limit": limit, "with_payload": True, "with_vector": False}
    if offset: body["offset"] = offset
    if filters: body["filter"] = filters
    r = requests.post(f"{QDRANT_URL}/collections/{collection}/points/scroll", json=body, timeout=10)
    r.raise_for_status()
    return r.json()["result"]

def search(collection, vector, limit=5, filters=None):
    body = {"vector": vector, "limit": limit, "with_payload": True}
    if filters: body["filter"] = filters
    r = requests.post(f"{QDRANT_URL}/collections/{collection}/points/search", json=body, timeout=10)
    r.raise_for_status()
    return r.json()["result"]

def upsert(collection, point_id, vector, payload):
    r = requests.put(f"{QDRANT_URL}/collections/{collection}/points",
        json={"points": [{"id": point_id, "vector": vector, "payload": payload}]}, timeout=10)
    r.raise_for_status()

def create_collection(collection, size=1024):
    r = requests.put(f"{QDRANT_URL}/collections/{collection}",
        json={"vectors": {"size": size, "distance": "Cosine"}}, timeout=10)
    if r.status_code not in (200, 409): r.raise_for_status()
    print(f"Collection '{collection}' ready.")
