#!/usr/bin/env python3
"""Search gems_tr. Usage: python3 search_gems.py "query" [--user-id X] [--category fact] [--limit 5]"""
import argparse, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.embedder import embed
from shared.qdrant_client import search

parser = argparse.ArgumentParser(description="Search TrueRecall Gems")
parser.add_argument("query", help="Search query")
parser.add_argument("--user-id", default=None)
parser.add_argument("--category", default=None, choices=["fact","decision","preference","action","status"])
parser.add_argument("--limit", type=int, default=5)
args = parser.parse_args()

must = []
if args.user_id: must.append({"key": "user_id", "match": {"value": args.user_id}})
if args.category: must.append({"key": "category", "match": {"value": args.category}})
filters = {"must": must} if must else None

vector = embed(args.query)
results = search("gems_tr", vector, limit=args.limit, filters=filters)

if not results:
    print("No gems found.")
    sys.exit(0)

for r in results:
    p = r["payload"]
    print(f"[{r['score']:.3f}] [{p.get('category','?').upper()}] {p.get('gem_text','')}")
