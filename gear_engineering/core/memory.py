"""
memory.py
=========
Simple JSON-backed design memory for caching successful plans.

All writes go to outputs/memory_db.json (never the repo root).
"""

import json
import os

from utils.logger import log

_DB_FILE = os.path.join("outputs", "memory_db.json")


def _load_db() -> list:
    if not os.path.exists(_DB_FILE):
        return []
    try:
        with open(_DB_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_db(data: list) -> None:
    os.makedirs(os.path.dirname(_DB_FILE), exist_ok=True)
    with open(_DB_FILE, "w") as f:
        json.dump(data, f, indent=2)


def log_success(prompt: str, plan_graph: list, score: str = "valid") -> None:
    """Persist a successful execution to the local JSON memory bank."""
    db = _load_db()
    db.append({
        "status":          "success",
        "score":           score,
        "prompt":          prompt.lower(),
        "execution_graph": plan_graph,
    })
    _save_db(db)
    log("memory", f"Design saved to memory (score={score}).")


def log_failure(prompt: str, error_message: str, plan_graph: list = None) -> None:
    """Persist a failure entry for diagnostics."""
    db = _load_db()
    db.append({
        "status":          "error",
        "prompt":          prompt.lower(),
        "execution_graph": plan_graph or [{"component": "unknown"}],
        "error_message":   error_message,
    })
    _save_db(db)
    log("memory", "Failure recorded in memory.")


def get_similar_design(prompt: str) -> dict:
    """Retrieve the most recent exact-match cached design."""
    log("memory", f"Querying cache for: '{prompt}'")
    db = _load_db()
    prompt_lower = prompt.lower()

    for entry in reversed(db):
        if entry.get("status") == "success" and entry.get("prompt") == prompt_lower:
            log("memory", f"Cache hit (score={entry.get('score', '?')}).")
            return {"cached_hits": 1, "plan": entry.get("execution_graph")}

    log("memory", "No exact cache match found.")
    return {"cached_hits": 0, "plan": None}
