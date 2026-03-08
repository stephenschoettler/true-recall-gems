"""Generic OpenAI-compatible LLM client for extraction tasks.

Configure via environment variables:
  LLM_API_KEY      - API key (required)
  LLM_BASE_URL     - Base URL (default: https://api.groq.com/openai/v1)
  LLM_MODEL        - Model name (default: llama-3.1-8b-instant)

Works with: Groq, OpenAI, Together, OpenRouter, Ollama, any OpenAI-compatible API.
"""
import requests, os, time, logging
log = logging.getLogger(__name__)

API_KEY = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")  # GROQ_API_KEY for backward compat
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
MAX_RETRIES = 3

def chat(prompt: str, model: str = None, max_tokens: int = 1000) -> str:
    if not API_KEY:
        raise RuntimeError("LLM_API_KEY (or GROQ_API_KEY) not set")
    model = model or DEFAULT_MODEL
    for attempt in range(MAX_RETRIES + 1):
        r = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.2, "max_tokens": max_tokens},
            timeout=30)
        if r.status_code == 429:
            retry_after = float(r.headers.get("Retry-After", 2 ** (attempt + 1)))
            log.warning(f"Rate limited (429), retry {attempt+1}/{MAX_RETRIES} in {retry_after}s")
            if attempt < MAX_RETRIES:
                time.sleep(retry_after)
                continue
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    r.raise_for_status()
