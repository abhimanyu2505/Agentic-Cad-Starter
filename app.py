"""
Agentic CAD System — Conversational Engineering Assistant
=========================================================
Clean 3-column layout: Chat | 3D Viewer | Properties
Stateful multi-turn design session with LLM context threading.
"""

import base64
import json
import os
import sys

import streamlit as st
import trimesh

# ---------------------------------------------------------------------------
# Package path resolution (allows running directly with `streamlit run app.py`)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "gear_engineering"))


def _load_local_env_once() -> None:
    """Load OPENAI_API_KEY from local .env files when Docker has not provided it."""
    if os.getenv("OPENAI_API_KEY"):
        return
    for rel_path in (".env", os.path.join("gear_engineering", ".env")):
        env_path = os.path.join(os.path.dirname(__file__), rel_path)
        if not os.path.exists(env_path):
            continue
        with open(env_path, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if key == "OPENAI_API_KEY" and not os.getenv(key):
                    os.environ[key] = value.strip().strip('"').strip("'")
                    return


_load_local_env_once()

from gear_engineering.main_pipeline import run_agentic_pipeline, recompile_assembly
from gear_engineering.core.llm_client import is_openai_configured
from gear_engineering.core.component_schemas import COMPONENT_SCHEMAS
from gear_engineering.core.state_manager import (
    empty_state, get_llm_context, add_message, has_components,
    set_last_intent, is_parameter_only_input,
)
from gear_engineering.ui_state import UIState

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agentic CAD",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Session state init ───────────────────────────────────────────────────────
UIState.init()

api_key_missing = not is_openai_configured()
if api_key_missing and not st.session_state.openai_key_notice_shown:
    st.session_state.messages.append({
        "role": "system",
        "content": (
            "OPENAI_API_KEY is not configured. Add it to `.env` or "
            "`gear_engineering/.env`, then restart the app."
        ),
    })
    st.session_state.openai_key_notice_shown = True

_THEMES = {
    "light": {
        "app_bg": "#eef1f5",
        "panel_bg": "#ffffff",
        "panel_soft": "#f7f8fa",
        "text": "#24292f",
        "muted": "#6b7280",
        "border": "#d8dde6",
        "accent": "#1f6feb",
        "accent_soft": "#eaf2ff",
        "danger_bg": "#fff1f2",
        "danger": "#b42318",
        "shadow": "0 10px 24px rgba(15, 23, 42, 0.08)",
        "viewer_bg": "#ffffff",
    },
    "dark": {
        "app_bg": "#101418",
        "panel_bg": "#171c22",
        "panel_soft": "#202630",
        "text": "#e6edf3",
        "muted": "#9aa4b2",
        "border": "#303844",
        "accent": "#58a6ff",
        "accent_soft": "#10243d",
        "danger_bg": "#341b20",
        "danger": "#ff8b8b",
        "shadow": "0 14px 30px rgba(0, 0, 0, 0.30)",
        "viewer_bg": "#151a20",
    },
}
theme = _THEMES.get(st.session_state.get("theme_mode", "light"), _THEMES["light"])

# ── CSS ───────────────────────────────────────────────────────────────────────
css = """
<style>
/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }

/* Fixed full-height layout — no page scroll */
html, body { overflow: hidden !important; height: 100vh !important; }
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main, section.main,
.block-container,
[data-testid="stBottom"] { overflow: hidden !important; }

[data-testid="stAppViewContainer"] {
  background: {theme["app_bg"]} !important;
  color: {theme["text"]} !important;
  height: 100vh !important;
}

/* Tight block spacing */
[data-testid="block-container"] {
  padding: 4px 8px !important;
  margin: 0 !important;
  max-width: 100% !important;
}
[data-testid="stVerticalBlock"]   { gap: 4px !important; }
[data-testid="stHorizontalBlock"] { gap: 6px !important; }
.main > div:first-child           { padding-top: 0 !important; }
section[data-testid="stMain"] > div { padding-top: 0 !important; }

/* Chat bubbles */
.user-bubble {
  background: {theme["panel_bg"]}; border: 1px solid {theme["border"]};
  border-radius: 12px 12px 4px 12px;
  padding: 8px 12px; margin: 4px 0 4px 32px;
  font-size: 12px; color: {theme["text"]}; line-height: 1.5;
  box-shadow: {theme["shadow"]};
}
.assistant-bubble {
  background: {theme["panel_bg"]}; border: 1px solid {theme["accent"]};
  border-radius: 12px 12px 12px 4px;
  padding: 8px 12px; margin: 4px 32px 4px 0;
  font-size: 12px; color: {theme["text"]}; line-height: 1.5;
  box-shadow: {theme["shadow"]};
}
.sys-bubble {
  background: {theme["panel_soft"]}; border: 1px solid {theme["border"]};
  border-radius: 6px; padding: 5px 10px; margin: 2px 0;
  font-size: 11px; color: {theme["muted"]}; font-style: italic;
}
.error-bubble {
  background: {theme["danger_bg"]}; border: 1px solid {theme["danger"]};
  border-radius: 6px; padding: 6px 10px; margin: 2px 0;
  font-size: 11px; color: {theme["danger"]};
}

/* Metric strip */
.metric-row { display:flex; gap:8px; flex-wrap:wrap; margin:4px 0 6px; }
.metric-card {
  background:{theme["panel_bg"]}; border:1px solid {theme["border"]}; border-radius:6px;
  padding:6px 12px; min-width:80px; flex:1;
}
.metric-card .lbl {
  font-size:9px; color:{theme["muted"]};
  text-transform:uppercase; letter-spacing:.08em;
}
.metric-card .val { font-size:1.05rem; font-weight:700; color:{theme["accent"]}; }

/* Inspector / property cards */
.prop-card {
  background:{theme["panel_bg"]}; border:1px solid {theme["border"]}; border-radius:8px;
  padding:10px 12px; margin-bottom:8px;
  font-size:12px; color:{theme["text"]};
  box-shadow:{theme["shadow"]};
}
.prop-card .prop-title {
  font-size:11px; font-weight:700; color:{theme["accent"]};
  text-transform:uppercase; letter-spacing:.06em; margin-bottom:6px;
}
.component-card {
  background:{theme["panel_bg"]};
  border:1px solid {theme["border"]};
  border-left:3px solid {theme["accent"]};
  border-radius:8px;
  padding:10px 12px;
  margin:7px 0;
  box-shadow:{theme["shadow"]};
}
.component-card .cid {
  font-size:12px;
  font-weight:700;
  color:{theme["text"]};
  overflow-wrap:anywhere;
}
.component-card .ctype {
  display:inline-block;
  margin-top:5px;
  padding:2px 7px;
  border-radius:999px;
  background:{theme["accent_soft"]};
  color:{theme["accent"]};
  font-size:10px;
  font-weight:700;
  text-transform:uppercase;
  letter-spacing:.05em;
}
.component-card .dims {
  margin-top:7px;
  color:{theme["muted"]};
  font-size:11px;
  line-height:1.45;
}
.inspector-title {
  font-size:13px;
  font-weight:800;
  color:{theme["text"]};
  margin: 0 0 4px 0;
}
.inspector-subtitle {
  font-size:11px;
  color:{theme["muted"]};
  margin-bottom:8px;
}

/* Buttons */
button[data-testid="baseButton-secondary"] {
  border-radius: 6px !important;
  background: {theme["panel_bg"]} !important;
  border-color: {theme["border"]} !important;
  color: {theme["text"]} !important;
  padding: 2px 8px !important;
  font-size: 12px !important;
}

div[data-testid="stTabs"] button {
  color: {theme["muted"]} !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
  color: {theme["accent"]} !important;
}
input, textarea, [data-baseweb="select"] > div {
  background: {theme["panel_bg"]} !important;
  color: {theme["text"]} !important;
  border-color: {theme["border"]} !important;
}
</style>
"""
for token, value in {
    '{theme["app_bg"]}': theme["app_bg"],
    '{theme["panel_bg"]}': theme["panel_bg"],
    '{theme["panel_soft"]}': theme["panel_soft"],
    '{theme["text"]}': theme["text"],
    '{theme["muted"]}': theme["muted"],
    '{theme["border"]}': theme["border"],
    '{theme["accent"]}': theme["accent"],
    '{theme["accent_soft"]}': theme["accent_soft"],
    '{theme["danger_bg"]}': theme["danger_bg"],
    '{theme["danger"]}': theme["danger"],
    '{theme["shadow"]}': theme["shadow"],
}.items():
    css = css.replace(token, value)
st.markdown(css, unsafe_allow_html=True)


# ── Cache helpers ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_glb_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


@st.cache_data(show_spinner=False)
def get_mesh_props(path: str) -> dict:
    try:
        mesh = trimesh.load(path, force="mesh")
        bb   = mesh.bounding_box.extents
        return {
            "vertices":  len(mesh.vertices),
            "triangles": len(mesh.faces),
            "bbox":      [round(float(x), 2) for x in bb],
            "volume":    round(float(mesh.volume), 3) if mesh.is_watertight else None,
        }
    except Exception:
        return {}


def build_viewer_html(comp_configs: list) -> str:
    tmpl = os.path.join(os.path.dirname(__file__), "ui", "three_viewer.html")
    with open(tmpl) as f:
        html = f.read()
    return html.replace(
        "__CONFIG__",
        json.dumps({"components": comp_configs}, separators=(",", ":")),
    )


# ── Formatting helpers ────────────────────────────────────────────────────────
def _fmt(v, d=0):
    try:    return f"{float(v):.{d}f}"
    except: return "—"


def _kinematics_html(meta: dict) -> str:
    metrics = [
        ("Input RPM",  _fmt(meta.get("input_speed_rpm",  0))),
        ("Output RPM", _fmt(meta.get("output_speed_rpm", 0))),
        ("Torque",     _fmt(meta.get("output_torque_nm", 0), 2) + " Nm"),
        ("Ratio",      f"{meta.get('target_ratio', '—')}:1"),
        ("Stages",     str(meta.get("num_stages", "—"))),
    ]
    cards = '<div class="metric-row">'
    for lbl, val in metrics:
        cards += (
            f'<div class="metric-card">'
            f'<div class="lbl">{lbl}</div>'
            f'<div class="val">{val}</div>'
            f'</div>'
        )
    return cards + "</div>"


def _component_detail_text(comp: dict) -> str:
    ctype = comp.get("type", "component")
    if ctype == "gear":
        return f"M{comp.get('module', '—')} · {comp.get('teeth', '—')} teeth · FW {comp.get('face_width', '—')}mm"
    if ctype == "shaft":
        return f"L {comp.get('length', '—')}mm · D {comp.get('diameter', '—')}mm"
    if ctype == "bolt":
        return f"{comp.get('thread_type', 'M')}{comp.get('diameter', '—')} · L {comp.get('length', '—')}mm · P {comp.get('pitch', '—')}"
    if ctype == "bearing":
        return f"ID {comp.get('inner_diameter', '—')}mm · OD {comp.get('outer_diameter', '—')}mm · W {comp.get('width', '—')}mm"
    if ctype in ("plate", "housing"):
        return f"{comp.get('length', '—')} x {comp.get('width', '—')} x {comp.get('height', comp.get('thickness', '—'))}mm"
    if ctype == "flange":
        return f"OD {comp.get('diameter', '—')}mm · T {comp.get('thickness', '—')}mm"
    if ctype == "cylinder":
        return f"R {comp.get('radius', '—')}mm · H {comp.get('height', '—')}mm"
    return ", ".join(
        f"{k}: {v}" for k, v in comp.items()
        if k not in ("id", "type", "extracted_parameters")
        and isinstance(v, (int, float, str))
    ) or "No dimensional data"


# ─────────────────────────────────────────────────────────────────────────────
# THREE-COLUMN LAYOUT
#   col_chat      — Chat (left)
#   col_viewer    — 3D Viewer (centre)
#   col_inspector — Scrollable engineering inspector (right)
# ─────────────────────────────────────────────────────────────────────────────
col_chat, col_viewer, col_inspector = st.columns([0.9, 2.1, 0.95], gap="small")


# ══════════════════════════════════════════════════════════════════════════════
# LEFT — Chat Panel
# ══════════════════════════════════════════════════════════════════════════════
with col_chat:
    # Header row
    hdr_l, hdr_r = st.columns([3, 1])
    with hdr_l:
        st.markdown("### ⚙️ Agentic CAD")
        comp_count = len(st.session_state.design_state.get("components", []))
        st.caption(
            f"{'🟢 Active · ' + str(comp_count) + ' components' if comp_count else '⬜ No active design'}"
        )
    with hdr_r:
        if st.button("＋ New", help="Start a new design", use_container_width=True):
            load_glb_b64.clear()
            get_mesh_props.clear()
            UIState.reset()
            st.rerun()
        if st.session_state.history:
            if st.button("↩ Undo", help="Revert to previous state", use_container_width=True):
                UIState.pop_history()
                load_glb_b64.clear()
                get_mesh_props.clear()
                st.rerun()

    st.markdown("---")

    # Chat history
    chat_container = st.container(height=400)
    with chat_container:
        if not st.session_state.messages:
            st.markdown(
                '<div class="sys-bubble">Describe what to design or modify…</div>',
                unsafe_allow_html=True,
            )
        for msg in st.session_state.messages:
            role    = msg["role"]
            content = msg["content"]
            if role == "user":
                st.markdown(
                    f'<div class="user-bubble">🧑 {content}</div>',
                    unsafe_allow_html=True,
                )
            elif role == "assistant":
                st.markdown(
                    f'<div class="assistant-bubble">🤖 {content}</div>',
                    unsafe_allow_html=True,
                )
            elif role == "error":
                st.markdown(
                    f'<div class="error-bubble">⚠️ {content}</div>',
                    unsafe_allow_html=True,
                )
            elif role == "system":
                st.markdown(
                    f'<div class="sys-bubble">{content}</div>',
                    unsafe_allow_html=True,
                )

    # ── Prompt input ──────────────────────────────────────────────────────
    pending = st.session_state.pop("_pending_prompt", None)
    prompt  = st.chat_input(
        "Describe what to design or modify…",
        disabled=api_key_missing,
    )
    if pending and not prompt:
        prompt = pending

    clarification_choice = None
    if st.session_state.clarification_options:
        st.markdown("<div style='font-size:12px;color:#666;margin-bottom:4px;'>Please clarify:</div>", unsafe_allow_html=True)
        for opt in st.session_state.clarification_options:
            if st.button(f"→ {opt}", use_container_width=True):
                clarification_choice = opt
                prompt = opt
                st.session_state.clarification_options = []
                st.session_state.clarification_type = None

    if prompt:
        # Record in UI message list
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Record in design state's conversation history (for LLM context)
        add_message(st.session_state.design_state, "user", prompt)

        # Determine pipeline context
        had_components_before = has_components(st.session_state.design_state)
        previous = st.session_state.design_state
        conversation_ctx = get_llm_context(st.session_state.design_state)

        with st.spinner("🔧 Synthesising…"):
            load_glb_b64.clear()
            get_mesh_props.clear()
            try:
                result = run_agentic_pipeline(
                    prompt,
                    previous_state=previous,
                    pending_parameters=st.session_state.pending_parameters,
                    last_failed_intent=st.session_state.last_failed_intent,
                    conversation_history=conversation_ctx,
                    generation_mode=st.session_state.get("generation_mode", "minimal"),
                    clarification_choice=clarification_choice,
                )
            except Exception as e:
                result = {"status": "error", "message": str(e)}

        if result.get("status") == "success":
            st.session_state.pipeline_result = result
            n_comp = len(result.get("components", []))
            if n_comp == 0:
                st.session_state.messages.append({
                    "role":    "assistant",
                    "content": (
                        "I couldn't generate any geometry from that prompt. "
                        "Try being more specific — e.g. "
                        "*'Create a shaft 100mm long and 15mm diameter'*."
                    ),
                })
            else:
                action = "Updated" if had_components_before else "Generated"
                n_glb  = len([
                    p for p in result.get("glb_paths", {}).values()
                    if os.path.exists(p["path"])
                ])
                comps = result.get("components", [])
                warnings = result.get("metadata", {}).get("engineering_warnings", [])
                warn_note = (
                    f" ⚠️ {len(warnings)} engineering warning(s) below."
                    if warnings else ""
                )
                assistant_reply = (
                    f"{action} assembly · **{n_comp} component(s)** · "
                    f"{n_glb} mesh(es) exported.{warn_note}"
                )
                add_message(
                    st.session_state.design_state, "assistant", assistant_reply
                )
                st.session_state.messages.append({
                    "role": "assistant", "content": assistant_reply,
                })
                UIState.apply_pipeline_result(result)
                if comps:
                    set_last_intent(st.session_state.design_state, comps[0])

        elif result.get("status") in ("question", "missing_parameters"):
            missing_fields = result.get("missing", result.get("missing_fields", []))
            st.session_state.pending_parameters  = missing_fields
            st.session_state.last_failed_intent  = result.get("intent")
            missing_str = ", ".join(missing_fields)
            comp_type   = (result.get("intent") or {}).get("type", "component")
            guidance    = result.get("guidance", "")
            question    = result.get("question")
            reply = (
                question or
                f"I need a bit more info for the **{comp_type}**. "
                f"Please provide: **{missing_str}**."
                + (f"\n\n💡 {guidance}" if guidance else "")
            )
            add_message(st.session_state.design_state, "assistant", reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})

        elif result.get("status") == "clarification":
            st.session_state.clarification_options = result["options"]
            st.session_state.clarification_type = result["type"]
            msg = result.get("message", "Please clarify your intent.")
            add_message(st.session_state.design_state, "assistant", msg)
            st.session_state.messages.append({"role": "assistant", "content": msg})

        else:
            err = result.get("message", "Unknown pipeline error.")
            st.session_state.pipeline_result = result
            st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {err}"})

        st.rerun()

    # ── Engineering telemetry (collapsible) ───────────────────────────────
    res = st.session_state.pipeline_result
    if res and res.get("status") == "success":
        meta     = res.get("metadata", {})
        warnings = meta.get("engineering_warnings", [])
        if warnings:
            for w in warnings:
                st.markdown(
                    f'<div class="error-bubble">🚨 {w}</div>',
                    unsafe_allow_html=True,
                )
        with st.expander("📊 Kinematic Telemetry", expanded=False):
            st.markdown(_kinematics_html(meta), unsafe_allow_html=True)
            if meta:
                st.json(meta, expanded=False)

# ══════════════════════════════════════════════════════════════════════════════
# CENTRE — 3D Viewer
# ══════════════════════════════════════════════════════════════════════════════
with col_viewer:
    glb_paths = st.session_state.glb_paths
    available = {
        cid: info for cid, info in glb_paths.items()
        if os.path.exists(info["path"])
    }

    if not available:
        st.markdown(
            '<div style="height:680px;display:flex;align-items:center;'
            f'justify-content:center;background:{theme["viewer_bg"]};border-radius:12px;'
            f'border:1px solid {theme["border"]};box-shadow:{theme["shadow"]};">'
            f'<span style="color:{theme["muted"]};font-size:13px;letter-spacing:2px;">'
            'NO ASSEMBLY LOADED</span></div>',
            unsafe_allow_html=True,
        )
    else:
        comp_configs = []
        for cid, info in available.items():
            try:
                b64 = load_glb_b64(info["path"])
            except Exception:
                b64 = ""
            comp_configs.append({
                "id":        cid,
                "type":      info["type"],
                "visible":   True,
                "glb_b64":   b64,
                "opacity":   1.0,
                "wireframe": False,
            })
        viewer_html = build_viewer_html(comp_configs)
        st.components.v1.html(viewer_html, height=700, scrolling=False)


# ══════════════════════════════════════════════════════════════════════════════
# RIGHT — Scrollable Engineering Inspector
# ══════════════════════════════════════════════════════════════════════════════
with col_inspector:
    st.markdown('<div class="inspector-title">Engineering Inspector</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="inspector-subtitle">Parameters, exports, history, and workspace preferences.</div>',
        unsafe_allow_html=True,
    )

    inspector = st.container(height=700)
    with inspector:
        comps = st.session_state.design_state.get("components", [])
        rels = st.session_state.design_state.get("relationships", [])
        type_counts = {}
        for comp in comps:
            ctype = comp.get("type", "?")
            type_counts[ctype] = type_counts.get(ctype, 0) + 1

        st.markdown(
            '<div class="metric-row">'
            f'<div class="metric-card"><div class="lbl">Components</div><div class="val">{len(comps)}</div></div>'
            f'<div class="metric-card"><div class="lbl">Relations</div><div class="val">{len(rels)}</div></div>'
            f'<div class="metric-card"><div class="lbl">Types</div><div class="val">{len(type_counts)}</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )

        tab_props, tab_kin, tab_export, tab_history, tab_profile = st.tabs([
            "Properties", "Kinematics", "Export", "History", "Profile"
        ])

        with tab_props:
            if not comps:
                st.markdown(
                    '<div class="prop-card"><div class="prop-title">No Components</div>'
                    '<span>Generate a component to inspect its dimensions.</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown('<div class="prop-title">Component Stack</div>', unsafe_allow_html=True)
                for comp in comps:
                    st.markdown(
                        '<div class="component-card">'
                        f'<div class="cid">{comp.get("id", "component")}</div>'
                        f'<span class="ctype">{comp.get("type", "unknown")}</span>'
                        f'<div class="dims">{_component_detail_text(comp)}</div>'
                        '</div>',
                        unsafe_allow_html=True,
                    )

                comp_ids = [c.get("id", f"comp_{i}") for i, c in enumerate(comps)]
                selected_id = st.selectbox("Edit component", options=comp_ids, key="inspector_prop_component")
                comp_idx = next((i for i, c in enumerate(comps) if c.get("id") == selected_id), None)
                if comp_idx is not None:
                    comp = comps[comp_idx]
                    comp_type = comp.get("type", "unknown")
                    schema = COMPONENT_SCHEMAS.get(comp_type, {})
                    editable = [
                        field for field in schema.get("required", []) + schema.get("optional", [])
                        if field != "thread_type"
                    ] or [
                        "module", "teeth", "face_width", "length", "diameter",
                        "pitch", "width", "height", "wall_thickness", "thickness",
                        "inner_diameter", "outer_diameter", "radius",
                    ]

                    st.markdown(
                        f'<div class="prop-card"><div class="prop-title">{selected_id}</div>'
                        f'<span>{comp_type} parameter controls</span></div>',
                        unsafe_allow_html=True,
                    )
                    with st.form(key=f"inspector_edit_form_{selected_id}"):
                        new_params = {}
                        for key in editable:
                            if key in comp and isinstance(comp[key], (int, float)):
                                label = key.replace("_", " ").capitalize()
                                if isinstance(comp[key], int):
                                    new_params[key] = st.number_input(
                                        label,
                                        value=int(comp[key]),
                                        step=1,
                                        key=f"inspector_{selected_id}_{key}",
                                    )
                                else:
                                    new_params[key] = st.number_input(
                                        label,
                                        value=float(comp[key]),
                                        step=0.5,
                                        format="%.3f" if key == "pitch" else "%.1f",
                                        key=f"inspector_{selected_id}_{key}",
                                    )
                        if "thread_type" in comp:
                            thread_value = str(comp.get("thread_type", "M")).upper()
                            new_params["thread_type"] = st.selectbox(
                                "Thread type",
                                ["M", "UNC", "UNF"],
                                index=["M", "UNC", "UNF"].index(thread_value)
                                if thread_value in ["M", "UNC", "UNF"] else 0,
                                key=f"inspector_{selected_id}_thread_type",
                            )
                        submitted = st.form_submit_button("Apply changes", type="primary", use_container_width=True)

                    if submitted and new_params:
                        UIState.push_history()
                        st.session_state.design_state["components"][comp_idx].update(new_params)
                        with st.spinner(f"Rebuilding {selected_id}..."):
                            res = recompile_assembly(st.session_state.design_state, "parametric_edit")
                        if res.get("status") == "success":
                            st.session_state.design_state["metadata"] = res.get("metadata", {})
                            st.session_state.glb_paths = res.get("glb_paths", {})
                            st.session_state.pipeline_result = res
                            load_glb_b64.clear()
                            get_mesh_props.clear()
                            st.success("Rebuilt.")
                        else:
                            st.error(res.get("message", "Rebuild failed."))
                        st.rerun()

        with tab_kin:
            meta = st.session_state.design_state.get("metadata", {})
            if meta:
                st.markdown(_kinematics_html(meta), unsafe_allow_html=True)
                st.json(meta, expanded=False)
            else:
                st.markdown(
                    '<div class="prop-card"><div class="prop-title">No Kinematics</div>'
                    '<span>Kinematic telemetry appears for gearbox and driven assemblies.</span></div>',
                    unsafe_allow_html=True,
                )

        with tab_export:
            result = st.session_state.pipeline_result or {}
            export_paths = result.get("export_paths", {})
            step_path = export_paths.get("step", "outputs/agentic_assembly_output.step")
            if os.path.exists(step_path):
                with open(step_path, "rb") as f:
                    st.download_button("STEP assembly", f, file_name="agentic_assembly_output.step", use_container_width=True)
            else:
                st.caption("No assembly export is available yet.")
            for label, key, ext in [
                ("STL components", "stl", "stl"),
                ("GLB components", "glb", "glb"),
                ("STEP components", "component_step", "step"),
            ]:
                paths = export_paths.get(key, {})
                if paths:
                    st.markdown(f"**{label}**")
                    for cid, path in sorted(paths.items()):
                        if os.path.exists(path):
                            with open(path, "rb") as f:
                                st.download_button(
                                    f"{cid}.{ext}",
                                    f,
                                    file_name=f"{cid}.{ext}",
                                    key=f"dl_{key}_{cid}",
                                    use_container_width=True,
                                )

        with tab_history:
            st.caption(f"Undo snapshots: {len(st.session_state.history)}")
            for i, msg in enumerate(st.session_state.messages[-10:], 1):
                st.markdown(
                    f'<div class="prop-card"><div class="prop-title">{i}. {msg.get("role")}</div>'
                    f'<span>{msg.get("content")}</span></div>',
                    unsafe_allow_html=True,
                )

        with tab_profile:
            selected_theme = st.radio(
                "Theme",
                options=["light", "dark"],
                index=0 if st.session_state.get("theme_mode", "light") == "light" else 1,
                horizontal=True,
                key="theme_mode",
            )
            st.selectbox(
                "Generation Mode",
                options=["minimal", "realistic"],
                index=0 if st.session_state.get("generation_mode", "minimal") == "minimal" else 1,
                help="Minimal creates only requested components. Realistic adds requested mechanical support only where appropriate.",
                key="generation_mode",
            )
            st.markdown(
                '<div class="prop-card"><div class="prop-title">Workspace</div>'
                f'<span>{selected_theme.capitalize()} mode · engineering inspector enabled</span></div>',
                unsafe_allow_html=True,
            )
