#!/usr/bin/env python3
"""TrueRecall Gems Curator — extracts key facts, decisions, preferences, actions, and status
changes from raw conversation turns stored in memories_tr and stores them to gems_tr."""

import json, os, sys, uuid, logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.qdrant_client import scroll, search, upsert, create_collection
from shared.embedder import embed
from shared.groq_client import chat

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gems")

STATE_FILE = Path.home() / ".openclaw/true-recall-gems/curator_state.json"
USER_ID = os.getenv("USER_ID", "user")

EXTRACT_PROMPT = """Extract key information from this conversation. Only extract genuinely important information — skip small talk, acknowledgments, and filler.

Categories:
- FACT: technical details, configurations, credentials, important facts
- DECISION: decisions made, approaches chosen
- PREFERENCE: user preferences, working style, how they like things done
- ACTION: tasks to complete, action items
- STATUS: project completions, milestones, status changes

Format each gem as: [CATEGORY] gem text
One per line. If nothing important, output: NONE

Conversation:
{turns_text}"""


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"gems_offset": None, "gems_processed": 0, "gems_extracted": 0}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def parse_gems(response: str) -> list[dict]:
    gems = []
    categories = {"FACT", "DECISION", "PREFERENCE", "ACTION", "STATUS"}
    for line in response.splitlines():
        line = line.strip()
        if not line or line == "NONE":
            continue
        for cat in categories:
            if line.startswith(f"[{cat}]"):
                text = line[len(f"[{cat}]"):].strip()
                if len(text) > 10:
                    gems.append({"category": cat.lower(), "gem_text": text})
                break
    return gems


def run():
    create_collection("gems_tr")
    state = load_state()
    offset = state.get("gems_offset")
    total_processed = state.get("gems_processed", 0)
    total_extracted = state.get("gems_extracted", 0)

    log.info(f"Starting gems curator. Offset: {offset}, processed so far: {total_processed}")

    while True:
        result = scroll("memories_tr", limit=20, offset=offset)
        points = result.get("points", [])
        next_offset = result.get("next_page_offset")

        if not points:
            log.info("No more turns to process.")
            break

        # Filter out system turns and very short content
        turns = [p for p in points
                 if p["payload"].get("role") != "system"
                 and len(p["payload"].get("content", "")) >= 30]

        if turns:
            turns_text = "\n".join(
                f"{p['payload'].get('role','?').capitalize()}: {p['payload'].get('content','')[:300]}"
                for p in turns
            )
            turn_ids = [str(p["id"]) for p in turns]

            try:
                response = chat(EXTRACT_PROMPT.format(turns_text=turns_text))
                gems = parse_gems(response)
                log.info(f"Batch of {len(turns)} turns → {len(gems)} gems extracted")

                stored = 0
                for gem in gems:
                    try:
                        vec = embed(gem["gem_text"])
                        # Dedup check
                        existing = search("gems_tr", vec, limit=1)
                        if existing and existing[0]["score"] > 0.9:
                            log.debug(f"Skipping duplicate gem (score={existing[0]['score']:.3f}): {gem['gem_text'][:60]}")
                            continue
                        payload = {
                            "gem_text": gem["gem_text"],
                            "category": gem["category"],
                            "user_id": USER_ID,
                            "source_turns": turn_ids,
                            "extracted_at": datetime.now(timezone.utc).isoformat(),
                        }
                        upsert("gems_tr", str(uuid.uuid4()), vec, payload)
                        stored += 1
                        log.info(f"  [{gem['category'].upper()}] {gem['gem_text'][:80]}")
                    except Exception as e:
                        log.warning(f"Failed to store gem: {e}")

                total_extracted += stored
            except Exception as e:
                log.error(f"Groq/extraction error: {e}")

        total_processed += len(points)
        state["gems_offset"] = next_offset
        state["gems_processed"] = total_processed
        state["gems_extracted"] = total_extracted
        save_state(state)

        if not next_offset:
            log.info("Reached end of memories_tr.")
            break

        offset = next_offset

    log.info(f"Done. Processed {total_processed} turns, extracted {total_extracted} gems total.")


if __name__ == "__main__":
    run()
