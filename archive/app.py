"""
Agentic CAD — Production Engineering Workspace
===============================================
3-panel layout: Chat+Nav (left) | 3D Viewer (centre) | Parametric Editor (right)
Deterministic conversational engine. No LLM for flow control.
"""

import base64
import html
import json
import os
import sys

import streamlit as st
import trimesh

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "gear_engineering"))


def _load_local_env_once() -> None:
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
    set_last_intent, is_parameter_only_input, clear_current_task,
)
from gear_engineering.ui_state import UIState

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agentic CAD",
    layout="wide",
    initial_sidebar_state="collapsed",
)

UIState.init()

# ── One-time API key notice ───────────────────────────────────────────────────
if not is_openai_configured() and not st.session_state.openai_key_notice_shown:
    st.session_state.messages.append({
        "role": "system",
        "content": "OPENAI_API_KEY not configured — LLM delta path disabled. "
                   "Deterministic conversation engine is fully active.",
    })
    st.session_state.openai_key_notice_shown = True

# ── Design tokens ─────────────────────────────────────────────────────────────
T = {
    "bg":          "#f5f6f8",
    "panel":       "#ffffff",
    "border":      "#e0e4ea",
    "text":        "#1a1d23",
    "muted":       "#6b7280",
    "accent":      "#1976d2",
    "accent_soft": "#e3f0fd",
    "success":     "#1b7a3e",
    "success_bg":  "#edfaf3",
    "danger":      "#c0392b",
    "danger_bg":   "#fdf2f2",
    "warn":        "#b45309",
    "warn_bg":     "#fffbeb",
    "shadow":      "0 1px 4px rgba(0,0,0,0.08)",
    "shadow_md":   "0 4px 16px rgba(0,0,0,0.10)",
}

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── Reset & base ── */
*, *::before, *::after {{ box-sizing: border-box; }}
html, body {{ overflow: hidden !important; height: 100vh !important; margin: 0; }}
body {{ font-family: 'Inter', system-ui, -apple-system, sans-serif !important; }}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"] {{
    display: none !important;
}}

/* ── App container ── */
[data-testid="stAppViewContainer"] {{
    background: {T["bg"]} !important;
    height: 100vh !important;
    overflow: hidden !important;
}}
[data-testid="stMain"], section.main {{
    overflow: hidden !important;
    padding: 0 !important;
}}
[data-testid="block-container"] {{
    padding: 0 !important;
    max-width: 100% !important;
}}
[data-testid="stVerticalBlock"]   {{ gap: 0 !important; }}
[data-testid="stHorizontalBlock"] {{ gap: 0 !important; align-items: stretch !important; }}

/* ── Panel base ── */
.cad-panel {{
    background: {T["panel"]};
    border-right: 1px solid {T["border"]};
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}}
.cad-panel-right {{
    background: {T["panel"]};
    border-left: 1px solid {T["border"]};
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}}

/* ── Panel header ── */
.panel-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 14px;
    height: 48px;
    border-bottom: 1px solid {T["border"]};
    flex-shrink: 0;
    background: {T["panel"]};
}}
.panel-title {{
    font-size: 12px;
    font-weight: 700;
    color: {T["text"]};
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}
.panel-badge {{
    font-size: 10px;
    font-weight: 600;
    color: {T["accent"]};
    background: {T["accent_soft"]};
    padding: 2px 8px;
    border-radius: 10px;
}}

/* ── Chat messages ── */
.chat-scroll {{
    flex: 1;
    overflow-y: auto;
    padding: 12px 12px 4px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    scroll-behavior: smooth;
}}
.chat-scroll::-webkit-scrollbar {{ width: 4px; }}
.chat-scroll::-webkit-scrollbar-track {{ background: transparent; }}
.chat-scroll::-webkit-scrollbar-thumb {{ background: {T["border"]}; border-radius: 4px; }}

.msg-user {{
    align-self: flex-end;
    max-width: 88%;
    background: {T["accent"]};
    color: #fff;
    border-radius: 14px 14px 3px 14px;
    padding: 8px 12px;
    font-size: 12.5px;
    line-height: 1.5;
    word-break: break-word;
}}
.msg-ai {{
    align-self: flex-start;
    max-width: 92%;
    background: {T["panel"]};
    color: {T["text"]};
    border: 1px solid {T["border"]};
    border-radius: 3px 14px 14px 14px;
    padding: 8px 12px;
    font-size: 12.5px;
    line-height: 1.5;
    word-break: break-word;
    box-shadow: {T["shadow"]};
}}
.msg-ai.question {{
    border-color: {T["accent"]};
    background: {T["accent_soft"]};
}}
.msg-system {{
    align-self: center;
    font-size: 11px;
    color: {T["muted"]};
    font-style: italic;
    padding: 2px 8px;
}}
.msg-error {{
    align-self: flex-start;
    max-width: 92%;
    background: {T["danger_bg"]};
    color: {T["danger"]};
    border: 1px solid {T["danger"]};
    border-radius: 6px;
    padding: 7px 11px;
    font-size: 12px;
}}
.msg-success {{
    align-self: flex-start;
    max-width: 92%;
    background: {T["success_bg"]};
    color: {T["success"]};
    border: 1px solid #a7f3d0;
    border-radius: 6px;
    padding: 7px 11px;
    font-size: 12px;
}}
.msg-warn {{
    align-self: flex-start;
    max-width: 92%;
    background: {T["warn_bg"]};
    color: {T["warn"]};
    border: 1px solid #fcd34d;
    border-radius: 6px;
    padding: 7px 11px;
    font-size: 12px;
}}

/* ── Chat input area ── */
.chat-input-area {{
    padding: 8px 10px;
    border-top: 1px solid {T["border"]};
    flex-shrink: 0;
    background: {T["panel"]};
}}

/* ── Component tree ── */
.tree-section {{
    flex-shrink: 0;
    border-top: 1px solid {T["border"]};
    max-height: 220px;
    overflow-y: auto;
}}
.tree-section::-webkit-scrollbar {{ width: 4px; }}
.tree-section::-webkit-scrollbar-thumb {{ background: {T["border"]}; border-radius: 4px; }}
.tree-header {{
    padding: 8px 14px 6px;
    font-size: 10px;
    font-weight: 700;
    color: {T["muted"]};
    text-transform: uppercase;
    letter-spacing: 0.1em;
    background: {T["bg"]};
    border-bottom: 1px solid {T["border"]};
    position: sticky;
    top: 0;
}}
.tree-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    cursor: pointer;
    border-bottom: 1px solid {T["border"]}18;
    transition: background 0.12s;
    font-size: 12px;
    color: {T["text"]};
}}
.tree-item:hover {{ background: {T["accent_soft"]}; }}
.tree-item.active {{ background: {T["accent_soft"]}; border-left: 3px solid {T["accent"]}; }}
.tree-dot {{
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}}
.tree-id {{ font-weight: 600; flex: 1; }}
.tree-type {{
    font-size: 10px;
    color: {T["muted"]};
    background: {T["bg"]};
    padding: 1px 6px;
    border-radius: 8px;
}}

/* ── Right panel scroll ── */
.right-scroll {{
    flex: 1;
    overflow-y: auto;
    padding: 12px;
}}
.right-scroll::-webkit-scrollbar {{ width: 4px; }}
.right-scroll::-webkit-scrollbar-thumb {{ background: {T["border"]}; border-radius: 4px; }}

/* ── Property cards ── */
.prop-section {{
    font-size: 10px;
    font-weight: 700;
    color: {T["muted"]};
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 14px 0 6px;
}}
.prop-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 0;
    border-bottom: 1px solid {T["border"]}60;
    font-size: 12px;
}}
.prop-label {{ color: {T["muted"]}; }}
.prop-value {{ color: {T["text"]}; font-weight: 500; font-family: 'SF Mono', monospace; font-size: 11px; }}

/* ── Metric strip ── */
.metric-strip {{
    display: flex;
    gap: 6px;
    padding: 10px 12px;
    border-bottom: 1px solid {T["border"]};
    flex-shrink: 0;
}}
.metric-card {{
    flex: 1;
    background: {T["bg"]};
    border: 1px solid {T["border"]};
    border-radius: 6px;
    padding: 6px 8px;
    text-align: center;
}}
.metric-lbl {{ font-size: 9px; color: {T["muted"]}; text-transform: uppercase; letter-spacing: 0.08em; }}
.metric-val {{ font-size: 15px; font-weight: 700; color: {T["accent"]}; }}

/* ── Tabs ── */
div[data-testid="stTabs"] {{
    flex-shrink: 0;
}}
div[data-testid="stTabs"] > div:first-child {{
    border-bottom: 1px solid {T["border"]};
    gap: 0;
    padding: 0 8px;
}}
div[data-testid="stTabs"] button {{
    font-size: 11px !important;
    font-weight: 500 !important;
    color: {T["muted"]} !important;
    padding: 8px 10px !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
}}
div[data-testid="stTabs"] button[aria-selected="true"] {{
    color: {T["accent"]} !important;
    border-bottom-color: {T["accent"]} !important;
}}
div[data-testid="stTabContent"] {{
    padding: 0 !important;
    overflow-y: auto;
    flex: 1;
}}

/* ── Buttons ── */
button[data-testid="baseButton-secondary"] {{
    border-radius: 6px !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    border-color: {T["border"]} !important;
    color: {T["text"]} !important;
    background: {T["panel"]} !important;
    padding: 4px 10px !important;
}}
button[data-testid="baseButton-secondary"]:hover {{
    background: {T["bg"]} !important;
    border-color: {T["accent"]} !important;
}}
button[data-testid="baseButton-primary"] {{
    border-radius: 6px !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    background: {T["accent"]} !important;
    color: #fff !important;
    padding: 4px 12px !important;
}}

/* ── Sliders ── */
[data-testid="stSlider"] {{
    padding: 0 !important;
}}
[data-testid="stSlider"] label {{
    font-size: 11px !important;
    color: {T["muted"]} !important;
    font-weight: 500 !important;
    margin-bottom: 2px !important;
}}
[data-testid="stSlider"] [data-baseweb="slider"] {{
    margin-top: 4px !important;
}}

/* ── Inputs ── */
input, textarea, [data-baseweb="select"] > div {{
    background: {T["panel"]} !important;
    color: {T["text"]} !important;
    border-color: {T["border"]} !important;
    font-size: 12px !important;
}}

/* ── Spinner ── */
[data-testid="stSpinner"] {{ color: {T["accent"]} !important; }}

/* ── Warning/error banners ── */
.eng-warn {{
    background: {T["warn_bg"]};
    border: 1px solid #fcd34d;
    border-left: 3px solid {T["warn"]};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 11px;
    color: {T["warn"]};
    margin: 4px 0;
}}

/* ── Empty state ── */
.empty-state {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: {T["muted"]};
    font-size: 12px;
    gap: 8px;
    padding: 24px;
    text-align: center;
}}
.empty-icon {{ font-size: 32px; opacity: 0.4; }}

/* ── Task progress indicator ── */
.task-progress {{
    background: {T["accent_soft"]};
    border: 1px solid {T["accent"]}40;
    border-radius: 6px;
    padding: 8px 12px;
    margin: 6px 12px;
    font-size: 11px;
    color: {T["accent"]};
    flex-shrink: 0;
}}
.task-progress .task-type {{
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: 10px;
}}
.task-params {{
    margin-top: 4px;
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
}}
.param-chip {{
    background: {T["accent"]};
    color: #fff;
    border-radius: 10px;
    padding: 1px 7px;
    font-size: 10px;
    font-weight: 500;
}}
.param-chip.missing {{
    background: {T["border"]};
    color: {T["muted"]};
}}
</style>
""", unsafe_allow_html=True)


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
        raw = f.read()
    return raw.replace(
        "__CONFIG__",
        json.dumps({"components": comp_configs}, separators=(",", ":")),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────
_TYPE_COLOR = {
    "gear": "#e53935", "shaft": "#78909c", "bearing": "#fb8c00",
    "housing": "#546e7a", "flange": "#1976d2", "bolt": "#6d4c41",
    "nut": "#8d6e63", "coupling": "#7b1fa2", "bracket": "#00695c",
    "plate": "#2e7d32", "cylinder": "#0097a7", "box": "#f57c00",
    "cone": "#c62828", "sphere": "#4527a0",
}

def _safe(text: str) -> str:
    """HTML-escape user content before injecting into markup."""
    return html.escape(str(text))


def _fmt(v, d=0):
    try:    return f"{float(v):.{d}f}"
    except: return "—"


def _component_dims(comp: dict) -> str:
    ctype = comp.get("type", "")
    if ctype == "gear":
        return f"M{comp.get('module','—')} · {comp.get('teeth','—')}T · {comp.get('face_width', comp.get('thickness','—'))}mm"
    if ctype == "shaft":
        return f"L {comp.get('length','—')}mm · Ø{comp.get('diameter','—')}mm"
    if ctype == "bolt":
        return f"Ø{comp.get('diameter','—')} · L{comp.get('length','—')}mm"
    if ctype == "bearing":
        return f"ID{comp.get('inner_diameter','—')} · OD{comp.get('outer_diameter','—')} · W{comp.get('width','—')}mm"
    if ctype == "flange":
        return f"Ø{comp.get('diameter','—')}mm · T{comp.get('thickness','—')}mm"
    if ctype in ("plate", "housing", "bracket"):
        return f"{comp.get('length','—')}×{comp.get('width','—')}×{comp.get('height', comp.get('thickness','—'))}mm"
    if ctype == "cylinder":
        return f"R{comp.get('radius','—')}mm · H{comp.get('height','—')}mm"
    return ", ".join(
        f"{k}:{v}" for k, v in comp.items()
        if k not in ("id","type","extracted_parameters") and isinstance(v,(int,float,str))
    ) or "—"


from typing import Optional

def _task_progress_html(task: Optional[dict]) -> str:
    if not task or task.get("type") is None:
        return ""
    from gear_engineering.core.component_registry import CONVERSATION_SCHEMAS
    schema = CONVERSATION_SCHEMAS.get(task["type"], {})
    required = schema.get("required", [])
    params   = task.get("parameters", {})
    chips = []
    for p in required:
        val = params.get(p)
        if val is not None:
            chips.append(f'<span class="param-chip">{_safe(p)}: {_safe(str(val))}</span>')
        else:
            chips.append(f'<span class="param-chip missing">{_safe(p)}: ?</span>')
    chips_html = "".join(chips)
    return (
        f'<div class="task-progress">'
        f'<div class="task-type">⚙ Building: {_safe(task["type"])}</div>'
        f'<div class="task-params">{chips_html}</div>'
        f'</div>'
    )


def _kinematics_html(meta: dict) -> str:
    items = [
        ("Input RPM",  _fmt(meta.get("input_speed_rpm",  0))),
        ("Output RPM", _fmt(meta.get("output_speed_rpm", 0))),
        ("Torque",     _fmt(meta.get("output_torque_nm", 0), 2) + " Nm"),
        ("Ratio",      f"{meta.get('target_ratio','—')}:1"),
        ("Stages",     str(meta.get("num_stages", "—"))),
    ]
    cards = []
    for lbl, val in items:
        cards.append(
            f'<div class="metric-card">'
            f'<div class="metric-lbl">{lbl}</div>'
            f'<div class="metric-val">{val}</div>'
            f'</div>'
        )
    return f'<div style="display:flex;gap:6px;padding:10px 0;">{"".join(cards)}</div>'


# ── 3-column layout ───────────────────────────────────────────────────────────
col_left, col_center, col_right = st.columns([1, 2.6, 1], gap="small")


# ══════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — Chat + Component Tree
# ══════════════════════════════════════════════════════════════════════════════
with col_left:
    st.markdown('<div class="cad-panel">', unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    comp_count = len(st.session_state.design_state.get("components", []))
    st.markdown(
        f'<div class="panel-header">'
        f'<span class="panel-title">⚙ Agentic CAD</span>'
        f'<span class="panel-badge">{comp_count} comp{"s" if comp_count != 1 else ""}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Action buttons ────────────────────────────────────────────────────────
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("＋ New", use_container_width=True, help="Start a new design"):
            load_glb_b64.clear()
            get_mesh_props.clear()
            UIState.reset()
            st.rerun()
    with btn_col2:
        undo_disabled = not st.session_state.history
        if st.button("↩ Undo", use_container_width=True, disabled=undo_disabled, help="Undo last action"):
            UIState.pop_history()
            load_glb_b64.clear()
            get_mesh_props.clear()
            st.rerun()

    # ── Active task progress ──────────────────────────────────────────────────
    current_task = st.session_state.design_state.get("current_task")
    if current_task and current_task.get("type"):
        st.markdown(_task_progress_html(current_task), unsafe_allow_html=True)

    # ── Chat messages ─────────────────────────────────────────────────────────
    chat_html_parts = []
    if not st.session_state.messages:
        chat_html_parts.append(
            '<div class="msg-system">Describe what you want to design…<br>'
            '<small>Try: "design a gear" or "create a shaft"</small></div>'
        )
    for msg in st.session_state.messages:
        role    = msg["role"]
        content = _safe(msg["content"])
        if role == "user":
            chat_html_parts.append(f'<div class="msg-user">{content}</div>')
        elif role == "assistant":
            # Detect question messages for special styling
            is_q = msg.get("is_question", False)
            cls  = "msg-ai question" if is_q else "msg-ai"
            chat_html_parts.append(f'<div class="{cls}">{content}</div>')
        elif role == "error":
            chat_html_parts.append(f'<div class="msg-error">⚠ {content}</div>')
        elif role == "success":
            chat_html_parts.append(f'<div class="msg-success">✓ {content}</div>')
        elif role == "warn":
            chat_html_parts.append(f'<div class="msg-warn">⚠ {content}</div>')
        elif role == "system":
            chat_html_parts.append(f'<div class="msg-system">{content}</div>')

    chat_html = (
        '<div class="chat-scroll" id="chat-scroll">'
        + "".join(chat_html_parts)
        + '</div>'
        # Auto-scroll to bottom
        + '<script>var el=document.getElementById("chat-scroll");'
        + 'if(el)el.scrollTop=el.scrollHeight;</script>'
    )
    st.markdown(chat_html, unsafe_allow_html=True)

    # ── Clarification buttons ─────────────────────────────────────────────────
    clarification_choice = None
    if st.session_state.clarification_options:
        st.markdown(
            '<div style="padding:4px 10px;font-size:11px;color:#666;">Choose one:</div>',
            unsafe_allow_html=True,
        )
        for opt in st.session_state.clarification_options:
            if st.button(f"→ {opt}", use_container_width=True, key=f"clarify_{opt}"):
                clarification_choice = opt
                st.session_state.clarification_options = []
                st.session_state.clarification_type = None

    # ── Chat input ────────────────────────────────────────────────────────────
    st.markdown('<div class="chat-input-area">', unsafe_allow_html=True)
    pending = st.session_state.pop("_pending_prompt", None)
    prompt  = st.chat_input("Type a design request…", key="main_chat_input")
    if pending and not prompt:
        prompt = pending
    if clarification_choice:
        prompt = clarification_choice
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Component tree ────────────────────────────────────────────────────────
    comps = st.session_state.design_state.get("components", [])
    if comps:
        tree_items = []
        for comp in comps:
            cid   = comp.get("id", "?")
            ctype = comp.get("type", "?")
            color = _TYPE_COLOR.get(ctype, "#9e9e9e")
            is_selected = st.session_state.get("selected_comp_id") == cid
            cls = "tree-item active" if is_selected else "tree-item"
            tree_items.append(
                f'<div class="{cls}">'
                f'<span class="tree-dot" style="background:{color}"></span>'
                f'<span class="tree-id">{_safe(cid)}</span>'
                f'<span class="tree-type">{_safe(ctype)}</span>'
                f'</div>'
            )
        st.markdown(
            '<div class="tree-section"><div class="tree-header">Component Tree</div>'
            + "".join(tree_items) + '</div>',
            unsafe_allow_html=True,
        )
        comp_ids = [c.get("id") for c in comps]
        selected_id = st.selectbox("Select Component", comp_ids, key="component_selector")
        st.session_state.selected_comp_id = selected_id

    st.markdown('</div>', unsafe_allow_html=True)


# ── Pipeline handler ──────────────────────────────────────────────────────────
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    add_message(st.session_state.design_state, "user", prompt)

    had_components_before = has_components(st.session_state.design_state)
    previous             = st.session_state.design_state
    conversation_ctx     = get_llm_context(st.session_state.design_state)

    with st.spinner("Synthesising…"):
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
            reply = "I couldn't generate any geometry. Try being more specific."
        else:
            action = "Updated" if had_components_before else "Generated"
            n_glb  = len([p for p in result.get("glb_paths", {}).values() if os.path.exists(p["path"])])
            warns  = result.get("metadata", {}).get("engineering_warnings", [])
            warn_note = f" ⚠ {len(warns)} engineering warning(s)." if warns else ""
            reply = f"{action} · {n_comp} component(s) · {n_glb} mesh(es) exported.{warn_note}"
        add_message(st.session_state.design_state, "assistant", reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        UIState.apply_pipeline_result(result)
        comps_out = result.get("components", [])
        if comps_out:
            set_last_intent(st.session_state.design_state, comps_out[0])

    elif result.get("status") in ("question", "missing_parameters"):
        missing_fields = result.get("missing", result.get("missing_fields", []))
        st.session_state.pending_parameters = missing_fields
        st.session_state.last_failed_intent = result.get("intent")
        question = result.get("question") or f"Please provide: {', '.join(missing_fields)}."
        add_message(st.session_state.design_state, "assistant", question)
        st.session_state.messages.append({"role": "assistant", "content": question, "is_question": True})

    elif result.get("status") == "clarification":
        st.session_state.clarification_options = result["options"]
        st.session_state.clarification_type    = result["type"]
        msg = result.get("message", "Please clarify your intent.")
        add_message(st.session_state.design_state, "assistant", msg)
        st.session_state.messages.append({"role": "assistant", "content": msg})

    else:
        err = result.get("message", "Unknown error.")
        st.session_state.pipeline_result = result
        st.session_state.messages.append({"role": "error", "content": err})

    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# CENTRE PANEL — 3D Viewer
# ══════════════════════════════════════════════════════════════════════════════
with col_center:
    glb_paths = st.session_state.glb_paths
    available = {cid: info for cid, info in glb_paths.items() if os.path.exists(info["path"])}

    if not available:
        st.markdown(
            f'<div style="height:680px;display:flex;align-items:center;justify-content:center;'
            f'background:{T["panel"]};border-radius:8px;border:1px solid {T["border"]};">'
            f'<span style="color:{T["muted"]};font-size:13px;letter-spacing:2px;">NO ASSEMBLY LOADED</span>'
            f'</div>',
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
                "id": cid, "type": info["type"],
                "visible": True, "glb_b64": b64,
                "opacity": 1.0, "wireframe": False,
            })
        st.components.v1.html(build_viewer_html(comp_configs), height=700, scrolling=False)


# ══════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL — Parametric Editor
# ══════════════════════════════════════════════════════════════════════════════
with col_right:
    st.markdown('<div class="cad-panel-right">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="panel-header"><span class="panel-title">Properties</span></div>',
        unsafe_allow_html=True,
    )

    all_comps = st.session_state.design_state.get("components", [])
    rels      = st.session_state.design_state.get("relationships", [])

    # Metric strip
    type_counts = {}
    for c in all_comps:
        type_counts[c.get("type","?")] = type_counts.get(c.get("type","?"), 0) + 1
    st.markdown(
        '<div class="metric-strip">'
        f'<div class="metric-card"><div class="metric-lbl">Components</div><div class="metric-val">{len(all_comps)}</div></div>'
        f'<div class="metric-card"><div class="metric-lbl">Relations</div><div class="metric-val">{len(rels)}</div></div>'
        f'<div class="metric-card"><div class="metric-lbl">Types</div><div class="metric-val">{len(type_counts)}</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    tab_props, tab_kin, tab_export, tab_history = st.tabs(["Properties", "Kinematics", "Export", "History"])

    with tab_props:
        if not all_comps:
            st.markdown(
                '<div class="empty-state"><div class="empty-icon">⚙</div>'
                '<span>Generate a component to inspect its properties.</span></div>',
                unsafe_allow_html=True,
            )
        else:
            comp_ids_right = [c.get("id", str(i)) for i, c in enumerate(all_comps)]
            sel = st.selectbox("Edit component", comp_ids_right, key="right_panel_selector")
            comp_idx = next((i for i, c in enumerate(all_comps) if c.get("id") == sel), None)

            if comp_idx is not None:
                comp      = all_comps[comp_idx]
                comp_type = comp.get("type", "unknown")

                # Property rows
                rows = []
                for k, v in comp.items():
                    if k in ("id", "type", "extracted_parameters"):
                        continue
                    if isinstance(v, (int, float, str)):
                        rows.append(f'<div class="prop-row"><span class="prop-label">{_safe(k)}</span><span class="prop-value">{_safe(str(v))}</span></div>')
                if rows:
                    st.markdown(
                        '<div class="prop-section">Dimensions</div>' + "".join(rows),
                        unsafe_allow_html=True,
                    )

                # Parametric sliders
                st.markdown('<div class="prop-section">Edit Parameters</div>', unsafe_allow_html=True)
                slider_map = {
                    "gear":   [("module", 0.5, 10.0, 0.5), ("teeth", 6, 120, 1), ("thickness", 1.0, 50.0, 0.5)],
                    "shaft":  [("length", 5.0, 500.0, 1.0), ("diameter", 1.0, 100.0, 0.5)],
                    "bolt":   [("diameter", 1.0, 30.0, 0.5), ("length", 5.0, 200.0, 1.0)],
                    "bearing":[("inner_diameter", 1.0, 100.0, 0.5), ("outer_diameter", 5.0, 200.0, 0.5), ("width", 1.0, 50.0, 0.5)],
                    "flange": [("diameter", 5.0, 300.0, 1.0), ("thickness", 1.0, 50.0, 0.5)],
                }
                sliders = slider_map.get(comp_type, [])
                new_params = {}
                current_values = {}
                for key, mn, mx, step in sliders:
                    current = comp.get(key)
                    if current is None:
                        continue
                    current_values[key] = current
                    if key == "teeth":
                        new_params[key] = st.slider(key.replace("_"," ").capitalize(), int(mn), int(mx), int(current), int(step), key=f"rp_{sel}_{key}")
                    else:
                        new_params[key] = st.slider(key.replace("_"," ").capitalize(), float(mn), float(mx), float(current), float(step), key=f"rp_{sel}_{key}")

                changed = any(current_values.get(k) != v for k, v in new_params.items())
                if changed and new_params:
                    UIState.push_history()
                    st.session_state.design_state["components"][comp_idx].update(new_params)
                    with st.spinner(f"Rebuilding {sel}…"):
                        res = recompile_assembly(st.session_state.design_state, "parametric_edit")
                    if res.get("status") == "success":
                        st.session_state.design_state["metadata"] = res.get("metadata", {})
                        st.session_state.glb_paths = res.get("glb_paths", {})
                        st.session_state.pipeline_result = res
                        load_glb_b64.clear()
                        get_mesh_props.clear()
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
                '<div class="empty-state"><div class="empty-icon">📊</div>'
                '<span>Kinematic data appears for gearbox assemblies.</span></div>',
                unsafe_allow_html=True,
            )

    with tab_export:
        result_exp = st.session_state.pipeline_result or {}
        export_paths = result_exp.get("export_paths", {})
        step_path = export_paths.get("step", "outputs/agentic_assembly_output.step")
        if os.path.exists(step_path):
            with open(step_path, "rb") as f:
                st.download_button("⬇ Export STEP", f, file_name="assembly.step", use_container_width=True)
        else:
            st.caption("No export available yet.")
        for label, key, ext in [("⬇ Export STL", "stl", "stl"), ("⬇ Export GLB", "glb", "glb")]:
            paths = export_paths.get(key, {})
            if paths:
                st.markdown(f"**{label}**")
                for cid, path in sorted(paths.items()):
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            st.download_button(f"{cid}.{ext}", f, file_name=f"{cid}.{ext}", key=f"dl_{key}_{cid}", use_container_width=True)

    with tab_history:
        st.caption(f"Undo snapshots: {len(st.session_state.history)}")
        for i, msg in enumerate(st.session_state.messages[-10:], 1):
            role    = msg.get("role", "")
            content = msg.get("content", "")
            st.markdown(
                f'<div class="prop-row"><span class="prop-label">{i}. {_safe(role)}</span>'
                f'<span class="prop-value" style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{_safe(content[:60])}</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown('</div>', unsafe_allow_html=True)
