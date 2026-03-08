import requests, os
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "snowflake-arctic-embed2")

def embed(text: str) -> list:
    r = requests.post(f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": text[:4000]}, timeout=60)
    r.raise_for_status()
    return r.json()["embedding"]
