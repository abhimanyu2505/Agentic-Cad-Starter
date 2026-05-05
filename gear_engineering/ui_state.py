"""
ui_state.py
===========
Centralises all Streamlit session_state initialisation and management.

Usage in app.py:
    from gear_engineering.ui_state import UIState
    UIState.init()          # call once at top of app.py
    UIState.push_history()  # snapshot before a mutation
    UIState.pop_history()   # undo
    UIState.reset()         # new design

This module does NOT import streamlit at module level so it can be
imported safely in tests without a running Streamlit context.
"""

from __future__ import annotations

from typing import Any, Dict


# ---------------------------------------------------------------------------
# Default values for every session key
# ---------------------------------------------------------------------------
_DEFAULTS: Dict[str, Any] = {
    "messages":            [],        # UI chat messages [{role, content}]
    "design_state":        None,      # set by init() after importing state_manager
    "glb_paths":           {},        # comp_id → {path, type}
    "pipeline_result":     None,      # last pipeline return value
    "pending_parameters":  None,      # list[str] of missing fields awaiting user input
    "last_failed_intent":  None,      # intent dict that triggered missing-param error
    "clarification_options": [],      # list[str] of disambiguation options
    "clarification_type":  None,      # component type being disambiguated
    "history":             [],        # undo stack: list of snapshots
    "_pending_prompt":     None,      # internal: prompt from example-button click
    "openai_key_notice_shown": False, # show missing-key startup notice once
    "theme_mode":          "light",   # UI theme: light | dark
}


# ---------------------------------------------------------------------------
# UIState manager
# ---------------------------------------------------------------------------

class UIState:
    """Static helper namespace — no instantiation needed."""

    @staticmethod
    def init() -> None:
        """
        Idempotently initialise every expected session_state key.
        Call exactly once at the top of app.py, after set_page_config.
        """
        import streamlit as st
        from gear_engineering.core.state_manager import empty_state

        for key, default in _DEFAULTS.items():
            if key not in st.session_state:
                if key == "design_state":
                    st.session_state[key] = empty_state()
                else:
                    # Use a fresh copy so mutable defaults aren't shared
                    import copy
                    st.session_state[key] = copy.deepcopy(default)

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------

    @staticmethod
    def push_history() -> None:
        """Save a deep copy of the current mutable state onto the undo stack."""
        import streamlit as st
        import copy
        st.session_state.history.append({
            "messages":        list(st.session_state.messages),
            "design_state":    copy.deepcopy(st.session_state.design_state),
            "glb_paths":       dict(st.session_state.glb_paths),
            "pipeline_result": st.session_state.pipeline_result,
        })

    @staticmethod
    def pop_history() -> bool:
        """
        Restore the most recent snapshot.
        Returns True if successful, False if history is empty.
        """
        import streamlit as st
        if not st.session_state.history:
            return False
        prev = st.session_state.history.pop()
        st.session_state.messages        = prev["messages"]
        st.session_state.design_state    = prev["design_state"]
        st.session_state.glb_paths       = prev["glb_paths"]
        st.session_state.pipeline_result = prev["pipeline_result"]
        st.session_state.pending_parameters = None
        st.session_state.last_failed_intent = None
        st.session_state.clarification_options = []
        st.session_state.clarification_type = None
        return True

    @staticmethod
    def reset() -> None:
        """Clear all state to a fresh empty design (saves current to history first)."""
        import streamlit as st
        from gear_engineering.core.state_manager import empty_state

        UIState.push_history()
        st.session_state.messages            = []
        st.session_state.design_state        = empty_state()
        st.session_state.glb_paths           = {}
        st.session_state.pipeline_result     = None
        st.session_state.pending_parameters  = None
        st.session_state.last_failed_intent  = None
        st.session_state.clarification_options = []
        st.session_state.clarification_type  = None

    @staticmethod
    def apply_pipeline_result(result: dict) -> None:
        """
        Merge a successful pipeline result into session state.
        Saves current state to history before applying.
        """
        import streamlit as st
        from gear_engineering.core.state_manager import from_dict, add_message

        UIState.push_history()

        # Update design state, preserving conversation history
        existing_history = st.session_state.design_state.get(
            "conversation_history", []
        )
        new_state = from_dict({
            "components":           result.get("components", []),
            "relationships":        result.get("relationships", []),
            "metadata":             result.get("metadata", {}),
            "conversation_history": existing_history,
        })
        st.session_state.design_state    = new_state
        st.session_state.glb_paths       = result.get("glb_paths", {})
        st.session_state.pipeline_result = result
        st.session_state.pending_parameters = None
        st.session_state.last_failed_intent = None
        st.session_state.clarification_options = []
        st.session_state.clarification_type = None
