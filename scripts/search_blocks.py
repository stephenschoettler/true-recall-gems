#!/usr/bin/env python3
"""Search topic_blocks_tr. Usage: python3 search_blocks.py "query" [--user-id X] [--limit 5]"""
import argparse, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.embedder import embed
from shared.qdrant_client import search

parser = argparse.ArgumentParser(description="Search TrueRecall Blocks")
parser.add_argument("query", help="Search query")
parser.add_argument("--user-id", default=None)
parser.add_argument("--limit", type=int, default=5)
args = parser.parse_args()

must = []
if args.user_id: must.append({"key": "user_id", "match": {"value": args.user_id}})
filters = {"must": must} if must else None

vector = embed(args.query)
results = search("topic_blocks_tr", vector, limit=args.limit, filters=filters)

if not results:
    print("No blocks found.")
    sys.exit(0)

for r in results:
    p = r["payload"]
    print(f"[{r['score']:.3f}] [{p.get('topic_title','?').upper()}]")
    print(f"  {p.get('summary','')}")
    print(f"  Turns: {p.get('turn_count',0)} | Last seen: {p.get('last_seen','')[:10]}")
    print()
