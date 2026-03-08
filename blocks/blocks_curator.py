#!/usr/bin/env python3
"""TrueRecall Blocks Curator — clusters conversation turns by topic and stores
narrative summaries as topic blocks in topic_blocks_tr."""

import json, os, sys, uuid, logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.qdrant_client import scroll, search, upsert, create_collection
from shared.embedder import embed
from shared.groq_client import chat

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("blocks")

STATE_FILE = Path.home() / ".openclaw/true-recall-gems/blocks_state.json"
USER_ID = os.getenv("USER_ID", "user")

SUMMARIZE_PROMPT = """Summarize this conversation cluster into a topic block.

Output format (exactly):
TITLE: <2-5 word topic title>
SUMMARY: <2-3 sentences describing what was discussed, decided, or done>

Conversation:
{turns_text}"""


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"blocks_offset": None, "blocks_processed": 0, "blocks_stored": 0}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def cosine_sim(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def cluster_turns(turns_with_embeddings, threshold=0.72) -> list:
    clusters = []
    for turn, emb in turns_with_embeddings:
        placed = False
        for cluster in clusters:
            if cosine_sim(emb, cluster["centroid"]) >= threshold:
                cluster["turns"].append(turn)
                n = len(cluster["turns"])
                cluster["centroid"] = [(c * (n - 1) + e) / n
                                       for c, e in zip(cluster["centroid"], emb)]
                placed = True
                break
        if not placed:
            clusters.append({"turns": [turn], "centroid": list(emb)})
    return clusters


def parse_summary(response: str) -> tuple[str, str]:
    title, summary = "", ""
    for line in response.splitlines():
        if line.startswith("TITLE:"):
            title = line[6:].strip()
        elif line.startswith("SUMMARY:"):
            summary = line[8:].strip()
    return title, summary


def run():
    create_collection("topic_blocks_tr")
    state = load_state()
    offset = state.get("blocks_offset")
    total_processed = state.get("blocks_processed", 0)
    total_stored = state.get("blocks_stored", 0)

    log.info(f"Starting blocks curator. Offset: {offset}")

    while True:
        result = scroll("memories_tr", limit=50, offset=offset)
        points = result.get("points", [])
        next_offset = result.get("next_page_offset")

        if not points:
            log.info("No more turns to process.")
            break

        # Filter and embed each turn
        valid = [p for p in points
                 if p["payload"].get("role") != "system"
                 and len(p["payload"].get("content", "")) >= 30]

        if len(valid) >= 3:
            log.info(f"Embedding {len(valid)} turns for clustering...")
            turns_with_emb = []
            for p in valid:
                try:
                    vec = embed(p["payload"]["content"])
                    turns_with_emb.append((p, vec))
                except Exception as e:
                    log.warning(f"Embed failed for turn {p['id']}: {e}")

            clusters = cluster_turns(turns_with_emb)
            log.info(f"Found {len(clusters)} clusters from {len(turns_with_emb)} turns")

            for cluster in clusters:
                if len(cluster["turns"]) < 3:
                    continue
                turns = cluster["turns"]
                turns_text = "\n".join(
                    f"{t['payload'].get('role','?').capitalize()}: {t['payload'].get('content','')[:300]}"
                    for t in turns
                )
                timestamps = [t["payload"].get("timestamp", "") for t in turns if t["payload"].get("timestamp")]
                first_seen = min(timestamps) if timestamps else ""
                last_seen = max(timestamps) if timestamps else ""

                try:
                    response = chat(SUMMARIZE_PROMPT.format(turns_text=turns_text))
                    title, summary = parse_summary(response)
                    if not title or not summary:
                        continue

                    block_text = f"{title}: {summary}"
                    block_vec = embed(block_text)

                    # Check for near-duplicate blocks
                    existing = search("topic_blocks_tr", block_vec, limit=1)
                    if existing and existing[0]["score"] > 0.85:
                        # Update existing block
                        existing_id = existing[0]["id"]
                        payload = existing[0]["payload"]
                        payload["last_seen"] = last_seen
                        payload["turn_count"] = payload.get("turn_count", 0) + len(turns)
                        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                        upsert("topic_blocks_tr", existing_id, block_vec, payload)
                        log.info(f"  Updated block: {title}")
                    else:
                        payload = {
                            "topic_title": title,
                            "summary": summary,
                            "source_turn_ids": [str(t["id"]) for t in turns],
                            "turn_count": len(turns),
                            "user_id": USER_ID,
                            "first_seen": first_seen,
                            "last_seen": last_seen,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                        upsert("topic_blocks_tr", str(uuid.uuid4()), block_vec, payload)
                        total_stored += 1
                        log.info(f"  New block: {title} ({len(turns)} turns)")

                except Exception as e:
                    log.error(f"Block summarization error: {e}")

        total_processed += len(points)
        state["blocks_offset"] = next_offset
        state["blocks_processed"] = total_processed
        state["blocks_stored"] = total_stored
        save_state(state)

        if not next_offset:
            log.info("Reached end of memories_tr.")
            break
        offset = next_offset

    log.info(f"Done. Processed {total_processed} turns, stored {total_stored} blocks total.")


if __name__ == "__main__":
    run()
