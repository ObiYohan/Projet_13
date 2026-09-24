"""Check that /api/v1/vector-search finds the expected opening for a few questions.

A question passes when the expected ECO code is among the top-k results.
Run from the repository root, with the stack up and the openings loaded:
    python scripts/eval_vector_search.py [--url http://localhost:8000] [--top-k 3]
Exit code 1 if at least one question fails.
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

QUESTIONS = [
    ("Which opening is called the Cadillac of chess openings?", "B90"),
    ("Gambit où les blancs jouent f4 pour ouvrir la colonne f", "C30"),
    ("Ouverture où les noirs sacrifient un pion pour une pression durable à l'aile dame", "A57"),
]


def search(base_url: str, query: str, top_k: int) -> list[dict]:
    # No videos: they don't affect the ranking and would spend YouTube quota.
    params = urllib.parse.urlencode({"query": query, "top_k": top_k, "with_videos": "false"})
    with urllib.request.urlopen(f"{base_url}/api/v1/vector-search?{params}", timeout=60) as response:
        return json.load(response)["results"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    passed = 0
    for question, expected in QUESTIONS:
        results = search(args.url, question, args.top_k)
        found = [r["eco_code"] for r in results]
        ok = expected in found
        passed += ok
        print(f"[{'OK' if ok else 'KO'}] {question}")
        print(f"     attendu {expected}, obtenu : " + ", ".join(
            f"{r['eco_code']} {r.get('opening_name_fr') or r['opening_name']} ({r['score']:.2f})" for r in results))

    print(f"\n{passed}/{len(QUESTIONS)} questions réussies (top {args.top_k})")
    return 0 if passed == len(QUESTIONS) else 1


if __name__ == "__main__":
    sys.exit(main())
