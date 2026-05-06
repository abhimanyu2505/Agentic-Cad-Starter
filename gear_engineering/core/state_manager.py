"""
state_manager.py
================
Single-responsibility module that owns the canonical DesignState.

DesignState is the persistent, session-level record of:
  - components:           list of component dicts (the assembly graph nodes)
  - relationships:        list of constraint dicts (the assembly graph edges)
  - metadata:             kinematic telemetry and synthesis info
  - conversation_history: list of {role, content} dicts for LLM context

This module is the single source of truth for state shape.
app.py and the pipeline only interact with state through these helpers.
"""

from __future__ import annotations

import copy
from typing import List, Dict, Any, Optional


# ---------------------------------------------------------------------------
# State shape definition
# ---------------------------------------------------------------------------

_EMPTY: Dict[str, Any] = {
    "components": [],
    "relationships": [],
    "metadata": {},
    "conversation_history": [],
    "last_intent": None,      # last successfully-typed intent dict (for follow-up merging)
    "current_task": None,     # {type, parameters, missing, status}
}

_MAX_HISTORY_FOR_LLM = 6  # Number of chat turns (user+assistant pairs) sent to LLM


def init_task_state() -> dict:
    """Return a fresh, empty task state for the conversation engine."""
    return {
        "type":       None,
        "parameters": {},
        "status":     "incomplete",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def empty_state() -> Dict[str, Any]:
    """Return a fresh, empty design state."""
    return copy.deepcopy(_EMPTY)


def from_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coerce an arbitrary dict into a valid state shape.
    Fills missing keys with defaults so callers never get KeyErrors.
    """
    state = copy.deepcopy(_EMPTY)
    state["components"]           = data.get("components", [])
    state["relationships"]        = data.get("relationships", [])
    state["metadata"]             = data.get("metadata", {})
    state["conversation_history"] = data.get("conversation_history", [])
    state["last_intent"]          = data.get("last_intent", None)
    state["current_task"]         = data.get("current_task", None)
    return state


def to_dict(state: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copy of the state (safe for serialisation / history)."""
    return copy.deepcopy(state)


def add_message(
    state: Dict[str, Any],
    role: str,
    content: str,
) -> Dict[str, Any]:
    """
    Append a chat message to the state's conversation history.
    Mutates state in-place and returns it (for chaining).
    role must be one of: 'user', 'assistant', 'system'
    """
    state.setdefault("conversation_history", []).append({
        "role":    role,
        "content": content,
    })
    return state


def get_llm_context(state: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Return the last N (user + assistant) messages from conversation_history
    in the format expected by the OpenAI messages list.

    Only 'user' and 'assistant' roles are included (not internal 'system'
    entries stored for display-only purposes).
    """
    history = state.get("conversation_history", [])
    # Filter to LLM-visible roles only
    llm_msgs = [
        msg for msg in history
        if msg.get("role") in ("user", "assistant")
    ]
    # Return the last N messages (most recent context window)
    return llm_msgs[-_MAX_HISTORY_FOR_LLM:]


def has_components(state: Dict[str, Any]) -> bool:
    """True if the state contains at least one component."""
    return bool(state.get("components"))


def set_last_intent(state: Dict[str, Any], intent: dict) -> Dict[str, Any]:
    """
    Persist the most recent successfully-parsed intent so follow-up
    parameter-only inputs (e.g. '120mm long') can be merged with it.
    """
    state["last_intent"] = copy.deepcopy(intent)
    return state


def get_last_intent(state: Dict[str, Any]) -> Optional[dict]:
    """Return the last stored intent dict, or None."""
    return state.get("last_intent")


# ---------------------------------------------------------------------------
# Structured intent memory (current_task)
# ---------------------------------------------------------------------------

def set_current_task(
    state: Dict[str, Any],
    task_type: str,
    parameters: dict = None,
    missing: list = None,
    confirmed: bool = False,
    status: str = None,
) -> Dict[str, Any]:
    """
    Set the active design task.  Called when the user expresses a clear
    component intent (even before all parameters are known).

    task_type  : 'shaft', 'gear', 'gearbox', 'bearing', etc.
    parameters : partial or full parameter dict extracted so far.
    status     : 'incomplete' or 'complete'. Defaults from confirmed.
    """
    base_parameters = {}
    try:
        try:
            from gear_engineering.core.component_schemas import COMPONENT_SCHEMAS
        except ImportError:
            from core.component_schemas import COMPONENT_SCHEMAS
        schema = COMPONENT_SCHEMAS.get(task_type, {})
        base_parameters = {field: None for field in schema.get("required", [])}
    except Exception:
        base_parameters = {}
    base_parameters.update(copy.deepcopy(parameters or {}))

    state["current_task"] = {
        "type":       task_type,
        "parameters": base_parameters,
        "missing":    list(missing or []),
        "status":     status or ("complete" if confirmed else "incomplete"),
        "confirmed":  confirmed,
    }
    return state


def get_current_task(state: Dict[str, Any]) -> Optional[dict]:
    """Return the active task dict, or None."""
    return state.get("current_task")


def update_current_task_params(
    state: Dict[str, Any],
    new_params: dict,
) -> Dict[str, Any]:
    """
    Merge new_params into the current_task's parameters dict.
    Creates a current_task shell if none exists.
    """
    if state.get("current_task") is None:
        state["current_task"] = {
            "type": "unknown",
            "parameters": {},
            "missing": [],
            "status": "incomplete",
            "confirmed": False,
        }
    state["current_task"]["parameters"].update(new_params)
    return state


def confirm_current_task(state: Dict[str, Any]) -> Dict[str, Any]:
    """Mark the current task as confirmed (user has chosen from clarification options)."""
    if state.get("current_task"):
        state["current_task"]["confirmed"] = True
        state["current_task"].setdefault("status", "incomplete")
    return state


def set_current_task_status(state: Dict[str, Any], status: str) -> Dict[str, Any]:
    """Set current_task.status when an active task exists."""
    if state.get("current_task"):
        state["current_task"]["status"] = status
        state["current_task"]["confirmed"] = status == "complete"
    return state


def set_current_task_missing(state: Dict[str, Any], missing: list) -> Dict[str, Any]:
    """Set current_task.missing and derive incomplete/complete status."""
    if state.get("current_task"):
        state["current_task"]["missing"] = list(missing or [])
        set_current_task_status(state, "incomplete" if missing else "complete")
    return state


def clear_current_task(state: Dict[str, Any]) -> Dict[str, Any]:
    """Clear the active task after generation or reset."""
    state["current_task"] = None
    return state


# ---------------------------------------------------------------------------
# Parameter-only input detection
# ---------------------------------------------------------------------------

_PARAM_PATTERNS = [
    r"\d+\s*mm",            # 120mm, 20 mm
    r"\d+\s*cm",            # 5cm
    r"\d+\s*nm",            # 10 Nm (torque)
    r"\d+\s*rpm",           # 1500 RPM
    r"diameter[\s:]+\d+",   # diameter: 20
    r"length[\s:]+\d+",     # length: 120
    r"radius[\s:]+\d+",     # radius: 15
    r"teeth[\s:]+\d+",      # teeth: 40
    r"module[\s:]+\d+",     # module: 2
    r"width[\s:]+\d+",      # width: 50
    r"height[\s:]+\d+",     # height: 30
    r"thickness[\s:]+\d+",  # thickness: 10
    r"speed[\s:]+\d+",      # speed: 1500
    r"torque[\s:]+\d+",     # torque: 10
    r"^\d+\s*$",            # bare number
]

_PARAM_ONLY_WORDS = {
    "yes", "ok", "sure", "fine", "correct", "that\'s right",
    "make it", "set to", "use",
}

import re as _re


def is_parameter_only_input(text: str) -> bool:
    """
    Returns True when the user's message looks like a parameter value
    rather than a new design intent.

    Examples that return True:
      '120mm'  |  'diameter 20'  |  '1500 rpm and 10 Nm'  |  'make it 50mm'
    Examples that return False:
      'Create a shaft'  |  'Design a gearbox'  |  'Add a gear'
    """
    t = text.strip().lower()

    # Very short pure-number strings
    if _re.match(r'^\d+(\.\d+)?\s*(mm|cm|nm|rpm|m)?$', t):
        return True

    # Convenience phrases
    if any(t.startswith(w) for w in _PARAM_ONLY_WORDS):
        return True

    # At least one numeric+unit pattern, and no strong design verb
    _DESIGN_VERBS = [
        "create", "design", "build", "generate", "make a", "add",
        "new ", "gearbox", "shaft", "gear", "bearing", "flange",
        "coupling", "housing", "bolt", "nut", "plate",
    ]
    has_unit   = any(_re.search(p, t) for p in _PARAM_PATTERNS)
    has_design = any(v in t for v in _DESIGN_VERBS)

    return has_unit and not has_design


def component_summary(state: Dict[str, Any]) -> str:
    """
    Compact human-readable summary of the current state for LLM prompts.
    Avoids dumping the entire raw JSON (prevents token overflow).

    Example output:
        gear_1 (gear: M2.0, 20T), shaft_A (shaft: L=50mm, D=10mm), ...
    """
    lines = []
    for comp in state.get("components", []):
        ctype = comp.get("type", "?")
        cid   = comp.get("id",   "?")
        if ctype == "gear":
            detail = f"M{comp.get('module', '?')}, {comp.get('teeth', '?')}T"
        elif ctype == "shaft":
            detail = f"L={comp.get('length', '?')}mm, D={comp.get('diameter', '?')}mm"
        elif ctype == "bearing":
            detail = (
                f"ID={comp.get('inner_diameter', '?')}mm, "
                f"OD={comp.get('outer_diameter', '?')}mm"
            )
        elif ctype in ("flange", "plate"):
            detail = f"D={comp.get('diameter', comp.get('length', '?'))}mm"
        elif ctype in ("bolt", "nut"):
            detail = f"D={comp.get('diameter', '?')}mm"
        elif ctype in ("box", "housing", "bracket"):
            detail = (
                f"{comp.get('length', '?')}×"
                f"{comp.get('width', '?')}×"
                f"{comp.get('height', '?')}mm"
            )
        else:
            detail = ""
        lines.append(f"{cid} ({ctype}: {detail})" if detail else f"{cid} ({ctype})")

    rels = state.get("relationships", [])
    rel_summary = f"{len(rels)} relationships" if rels else "no relationships"
    comp_list = ", ".join(lines) if lines else "none"
    return f"Components [{len(lines)}]: {comp_list}. {rel_summary.capitalize()}."
