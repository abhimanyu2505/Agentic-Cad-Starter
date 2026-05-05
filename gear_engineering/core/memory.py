import json
import os

DB_FILE = "memory_db.json"

def _load_db() -> list:
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def _save_db(data: list) -> None:
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

def log_success(prompt: str, plan_graph: list, score: str = "valid") -> None:
    """
    Logs a successful execution to the local JSON memory bank.
    score can be 'valid', 'adjusted', or 'warning'.
    """
    db = _load_db()
    entry = {
        "status": "success",
        "score": score,
        "prompt": prompt.lower(),
        "execution_graph": plan_graph
    }
    db.append(entry)
    _save_db(db)
    print(f"\n[MEMORY AGENT] Saved design to local memory (Score: {score})")

def log_failure(prompt: str, error_message: str, plan_graph: list = None) -> None:
    """
    Logs failures for diagnostic purposes.
    """
    db = _load_db()
    entry = {
        "status": "error",
        "prompt": prompt.lower(),
        "execution_graph": plan_graph or [{"component": "unknown"}],
        "error_message": error_message
    }
    db.append(entry)
    _save_db(db)
    print(f"\n[MEMORY AGENT] Saved failure to local memory")

def get_similar_design(prompt: str) -> dict:
    """
    Retrieves a past design based on simple keyword matching.
    """
    print(f"[MEMORY AGENT] Querying local memory for: '{prompt}'")
    db = _load_db()
    
    prompt_lower = prompt.lower()
    best_match = None
    
    for entry in reversed(db): # search newest first
        if entry.get("status") == "success" and entry.get("prompt") == prompt_lower:
            best_match = entry
            break
            
    if best_match:
        print(f"[MEMORY AGENT] Found exact match with score: {best_match.get('score', 'unknown')}")
        return {
            "cached_hits": 1,
            "plan": best_match.get("execution_graph")
        }
        
    print("[MEMORY AGENT] No exact historical precedent retrieved.")
    return {
        "cached_hits": 0, 
        "plan": None
    }

