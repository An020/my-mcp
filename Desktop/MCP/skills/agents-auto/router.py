#!/usr/bin/env python3
"""
Universal Skill Auto-Router Engine (/agents-auto).
Scores user tasks against skills_index.json and dispatches optimal skills or enforces strict fallback.
"""

import sys
import json
import re
import math
from pathlib import Path

ROUTER_DIR = Path(__file__).resolve().parent
SKILLS_DIR = ROUTER_DIR.parent if ROUTER_DIR.name in ["scripts", "agents-auto"] else ROUTER_DIR
INDEX_PATH = ROUTER_DIR / "skills_index.json"
if not INDEX_PATH.exists():
    INDEX_PATH = SKILLS_DIR / "skills_index.json"
if not INDEX_PATH.exists():
    INDEX_PATH = Path("C:/Users/nguye/.claude/skills/skills_index.json")

CONFIDENCE_THRESHOLD = 0.18


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9_\-\.]+", text.lower())
    stop_words = {
        "the", "and", "for", "with", "this", "that", "from", "when", "your",
        "you", "use", "using", "all", "are", "have", "can", "will", "how",
        "what", "where", "which", "who", "why", "their", "they", "them",
        "make", "does", "please", "help", "want", "need", "like", "should"
    }
    return [w for w in words if w not in stop_words and len(w) >= 2]


def score_skill(query_tokens: list[str], skill: dict) -> float:
    if not query_tokens:
        return 0.0

    name_tokens = set(tokenize(skill.get("name", "")))
    desc_tokens = set(tokenize(skill.get("description", "")))
    kw_tokens = set(tokenize(" ".join(skill.get("keywords", []))))

    score = 0.0
    matched_any = False

    for qt in query_tokens:
        token_score = 0.0
        # Exact match on name or name parts
        if qt in name_tokens:
            token_score += 3.5
            matched_any = True
        elif any(qt in nt for nt in name_tokens):
            token_score += 2.0
            matched_any = True

        # Match in keywords
        if qt in kw_tokens:
            token_score += 1.8
            matched_any = True

        # Match in description
        if qt in desc_tokens:
            token_score += 1.2
            matched_any = True

        score += token_score

    if not matched_any:
        return 0.0

    # Normalize by query length with soft damping
    normalized = score / (math.sqrt(len(query_tokens)) * 4.0)
    return min(1.0, normalized)


def route_task(task_query: str, top_k: int = 2):
    if not INDEX_PATH.exists():
        return {
            "status": "error",
            "message": f"Skill index not found at {INDEX_PATH}"
        }

    try:
        index_data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        skills = index_data.get("skills", [])
    except Exception as e:
        return {"status": "error", "message": f"Failed to load index: {e}"}

    query_tokens = tokenize(task_query)
    scored = []

    for s in skills:
        sc = score_skill(query_tokens, s)
        scored.append((sc, s))

    scored.sort(key=lambda x: x[0], reverse=True)

    best_score = scored[0][0] if scored else 0.0
    recommendations = [s for sc, s in scored[:3]]

    # Strict fallback check
    if best_score < CONFIDENCE_THRESHOLD:
        return {
            "status": "insufficient",
            "task": task_query,
            "best_score": round(best_score, 3),
            "threshold": CONFIDENCE_THRESHOLD,
            "message": f"Insufficient skills for task: \"{task_query}\"",
            "recommendations": recommendations
        }

    # Select top matching skills (within 75% of best score, up to top_k)
    selected = []
    for sc, s in scored:
        if len(selected) >= top_k:
            break
        if sc >= CONFIDENCE_THRESHOLD and sc >= best_score * 0.70:
            selected.append({
                "name": s["name"],
                "score": round(sc, 3),
                "description": s["description"],
                "path": s["path"]
            })

    return {
        "status": "success",
        "task": task_query,
        "selected_skills": selected,
        "count": len(selected)
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: router.py \"<task description>\" [--json]")
        sys.exit(1)

    as_json = "--json" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--json"]
    query = " ".join(args)

    res = route_task(query)

    if as_json:
        print(json.dumps(res, indent=2))
    else:
        if res["status"] == "insufficient":
            print(f"\n>>> {res['message']}")
            print(f"(Best match score: {res['best_score']} < Threshold: {res['threshold']})\n")
            print("Recommended closest skills that may be adapted:")
            for i, r in enumerate(res["recommendations"], 1):
                print(f"  {i}. {r['name']} - {r['description']}")
        elif res["status"] == "success":
            print(f"\n>>> Selected {res['count']} optimal skill(s) for task: \"{query}\"")
            for i, s in enumerate(res["selected_skills"], 1):
                print(f"  {i}. [{s['name']}] (Score: {s['score']}) -> {s['description']}")
                print(f"     Path: {s['path']}")
            print(f"\n>>> Action: Spawning {res['count']} subagent(s) with corresponding skill protocols.")
        else:
            print(f"Error: {res.get('message')}")
