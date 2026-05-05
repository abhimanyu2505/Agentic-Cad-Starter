"""
State Merger — deterministic merge engine.

Applies an LLM-generated *delta* onto the existing design state.
The LLM only produces incremental changes; this module is the
authoritative source of truth for the design graph.

Delta format (from LLM):
{
    "action": "add" | "modify" | "remove",
    "components": [...],
    "relationships": [...]
}
"""

import uuid
import copy
from typing import Dict, List, Optional
from utils.logger import log


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_delta(previous_state: dict, delta: dict) -> dict:
    """
    Merge a delta onto the existing design state and return a new state.
    Never mutates previous_state.

    Returns merged state dict with keys: components, relationships, metadata.
    Raises ValueError on validation failure.
    """
    state = copy.deepcopy(previous_state)
    action = delta.get("action", "add").lower()
    delta_comps = delta.get("components", [])
    delta_rels  = delta.get("relationships", [])

    # Ensure all delta components have unique IDs, non-conflicting with existing
    existing_ids = {c["id"] for c in state.get("components", []) if "id" in c}
    delta_comps  = _ensure_unique_ids(delta_comps, existing_ids)

    if action == "add":
        state = _merge_add(state, delta_comps, delta_rels)
    elif action == "modify":
        state = _merge_modify(state, delta_comps, delta_rels)
    elif action == "remove":
        state = _merge_remove(state, delta_comps, delta_rels)
    else:
        raise ValueError(f"Unknown delta action: '{action}'. Must be add | modify | remove.")

    # Validate merged state
    _validate(state)
    return state


def empty_state() -> dict:
    return {"components": [], "relationships": [], "metadata": {}}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _ensure_unique_ids(components: List[dict], existing_ids: set) -> List[dict]:
    result = []
    for comp in components:
        c = copy.deepcopy(comp)
        if "id" not in c or not c["id"]:
            c["id"] = f"{c.get('type','comp')}_{uuid.uuid4().hex[:6]}"
        # Avoid ID collisions with existing components
        while c["id"] in existing_ids:
            c["id"] = f"{c['id']}_{uuid.uuid4().hex[:4]}"
        existing_ids.add(c["id"])
        result.append(c)
    return result


def _merge_add(state: dict, new_comps: List[dict], new_rels: List[dict]) -> dict:
    """Append new components and relationships. Skip duplicate IDs."""
    existing_ids = {c["id"] for c in state["components"] if "id" in c}
    for comp in new_comps:
        if comp.get("id") not in existing_ids:
            state["components"].append(comp)
            existing_ids.add(comp["id"])
            log("merger", f"Added component: {comp['id']} ({comp.get('type')})")
        else:
            log("merger", f"Skipped duplicate ID: {comp['id']}")

    # Add relationships — avoid exact duplicates
    existing_rels = {
        (r["type"], r["from_id"], r["to_id"])
        for r in state["relationships"]
    }
    for rel in new_rels:
        key = (rel.get("type"), rel.get("from_id"), rel.get("to_id"))
        if key not in existing_rels:
            state["relationships"].append(rel)
            existing_rels.add(key)
    return state


def _merge_modify(state: dict, modified_comps: List[dict], new_rels: List[dict]) -> dict:
    """Update parameters of existing components in-place."""
    comp_map = {c["id"]: c for c in state["components"] if "id" in c}
    for mod in modified_comps:
        cid = mod.get("id")
        if cid and cid in comp_map:
            comp_map[cid].update({k: v for k, v in mod.items() if k != "id"})
            log("merger", f"Modified component: {cid}")
        else:
            # ID not found — treat as an add
            log("merger", f"Modify target '{cid}' not found, adding as new component.")
            state["components"].append(mod)
    # Add any new relationships that came with the modify
    return _merge_add(state, [], new_rels)


def _merge_remove(state: dict, target_comps: List[dict], target_rels: List[dict]) -> dict:
    """Remove components and their associated relationships."""
    remove_ids = {c["id"] for c in target_comps if "id" in c}
    state["components"] = [c for c in state["components"] if c.get("id") not in remove_ids]

    # Remove any relationship referencing a removed component
    state["relationships"] = [
        r for r in state["relationships"]
        if r.get("from_id") not in remove_ids and r.get("to_id") not in remove_ids
    ]

    # Remove explicitly specified relationships
    explicit_keys = {(r.get("type"), r.get("from_id"), r.get("to_id")) for r in target_rels}
    state["relationships"] = [
        r for r in state["relationships"]
        if (r.get("type"), r.get("from_id"), r.get("to_id")) not in explicit_keys
    ]
    log("merger", f"Removed {len(remove_ids)} component(s) and associated relationships.")
    return state


def _validate(state: dict) -> None:
    """
    Basic graph integrity check.
    - All relationship IDs must reference existing components.
    - Warn (don't raise) on dangling relationships.
    """
    comp_ids = {c["id"] for c in state.get("components", []) if "id" in c}
    warnings = []
    valid_rels = []
    for rel in state.get("relationships", []):
        fid = rel.get("from_id")
        tid = rel.get("to_id")
        if fid not in comp_ids or tid not in comp_ids:
            warnings.append(f"Dangling relationship {rel.get('type')} {fid}→{tid} — removed.")
        else:
            valid_rels.append(rel)

    if warnings:
        for w in warnings:
            log("merger", f"[WARNING] {w}")
    state["relationships"] = valid_rels
