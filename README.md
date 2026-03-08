# 🧠 TrueRecall: 💎 Gems & 🧱 Blocks

> Curation addons for [TrueRecall Base](https://gitlab.com/mdkrush/openclaw-true-recall-base) — built on top of the real-time memory capture daemon.

## 🏗️ Three-Tier Architecture

```
true-recall-base (REQUIRED)
├── Core: Watcher daemon
└── Stores: memories_tr (raw turns, 1024-dim Cosine)
│
├──▶ true-recall-gems (THIS REPO — ADDON)
│    ├── Curator extracts key facts/decisions/preferences/actions/status
│    └── Stores distilled gems → gems_tr
│
└──▶ true-recall-blocks (THIS REPO — ADDON)
     ├── Clusters turns by topic using semantic similarity
     └── Stores narrative summaries → topic_blocks_tr

Note: Gems and Blocks are independent addons. Both require Base.
You can run one or both — they don't interfere with each other.
```

## ✅ Requirements

- **TrueRecall Base** running and capturing turns to `memories_tr`
- **Qdrant** (local or remote) — same instance used by Base
- **Ollama** with `snowflake-arctic-embed2` model loaded (1024-dim)
- **Any OpenAI-compatible LLM API** — Groq (free tier), OpenAI, Together, OpenRouter, local Ollama, etc.

## 🚀 Quick Install

```bash
chmod +x install.sh
./install.sh
```

The installer:
1. Prompts for Qdrant/Ollama/LLM config
2. Writes `gems.env` with all env vars
3. Creates `gems_tr` and `topic_blocks_tr` Qdrant collections
4. Installs and enables systemd timers (runs every 15 minutes)
5. Does a test run of the gems curator

## 🔧 Manual Install

```bash
# Write your config
cat > ~/.openclaw/true-recall-gems/gems.env << ENV
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://localhost:11434
EMBEDDING_MODEL=snowflake-arctic-embed2
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
USER_ID=your_user_id
ENV

# Install systemd timers
cp systemd/*.service systemd/*.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now gems-curator.timer
systemctl --user enable --now blocks-curator.timer
```

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |
| `EMBEDDING_MODEL` | `snowflake-arctic-embed2` | Embedding model (1024-dim) |
| `LLM_API_KEY` | — | API key for your LLM provider (required) |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible base URL |
| `LLM_MODEL` | `gpt-4o-mini` | Model name for your provider |
| `USER_ID` | `user` | User identifier for filtering |

> 💡 **Provider examples:** Groq (`https://api.groq.com/openai/v1`), OpenAI (`https://api.openai.com/v1`), Together (`https://api.together.xyz/v1`), OpenRouter (`https://openrouter.ai/api/v1`), local Ollama (`http://localhost:11434/v1`)

## 🧠 How It Works

### 💎 Gems (`curator/gems_curator.py`)

Runs every 15 minutes via systemd timer. For each batch of ~20 new turns:

1. Scrolls `memories_tr` from last cursor position
2. Filters out system messages and very short content
3. Sends batch to LLM with extraction prompt
4. Parses response into categorized gems (FACT / DECISION / PREFERENCE / ACTION / STATUS)
5. Embeds each gem via Ollama Arctic Embed2
6. Deduplication: skips gems with cosine similarity > 0.9 to any existing gem
7. Stores unique gems to `gems_tr`

📍 State tracked in: `~/.openclaw/true-recall-gems/curator_state.json`

### 🧱 Blocks (`blocks/blocks_curator.py`)

Runs every 15 minutes via systemd timer. For each batch of ~50 new turns:

1. Embeds each turn via Ollama
2. Greedy clustering by cosine similarity (threshold: 0.72)
3. Clusters with ≥ 3 turns → sent to LLM for title + summary
4. Near-duplicate check (score > 0.85 = update existing block)
5. Stores new/updated blocks to `topic_blocks_tr`

📍 State tracked in: `~/.openclaw/true-recall-gems/blocks_state.json`

## 🔍 Searching

```bash
# Search gems
python3 scripts/search_gems.py "VoxClaw voice interface"
python3 scripts/search_gems.py "API keys" --category fact --user-id myuser
python3 scripts/search_gems.py "tasks to do" --category action --limit 10

# Search blocks
python3 scripts/search_blocks.py "memory system architecture"
python3 scripts/search_blocks.py "PR review process"
```

## 🗄️ Qdrant Collections

| Collection | Contents | Dimensions |
|------------|----------|------------|
| `memories_tr` | Raw conversation turns (from Base) | 1024 |
| `gems_tr` | Distilled facts/decisions/preferences/actions | 1024 |
| `topic_blocks_tr` | Topic cluster summaries | 1024 |

## 🙏 Credits

Built on **TrueRecall Base** by [mdkrush](https://gitlab.com/mdkrush/openclaw-true-recall-base) — the real-time memory capture daemon that makes this possible.

## 📄 License

MIT
