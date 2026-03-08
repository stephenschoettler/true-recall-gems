import requests, os
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def chat(prompt: str, model: str = "llama-3.1-8b-instant", max_tokens: int = 1000) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.2, "max_tokens": max_tokens},
        timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()
