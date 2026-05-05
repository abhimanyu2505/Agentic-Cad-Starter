"""
Agentic CAD System — Conversational Engineering Assistant
ChatGPT-style interface · Stateful design memory · WebGL CAD viewer
"""

import base64
import json
import os
import sys

import streamlit as st
import trimesh

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "gear_engineering"))
from gear_engineering.main_pipeline import run_agentic_pipeline, recompile_assembly
from gear_engineering.core.state_merger import empty_state

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agentic CAD",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Hide default Streamlit header / footer */
#MainMenu, footer, header { visibility: hidden; }

/* Disable page scroll — fixed layout */
html, body {
  overflow: hidden !important;
  height: 100vh !important;
}
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main,
section.main,
.block-container,
[data-testid="stBottom"] {
  overflow: hidden !important;
}
[data-testid="stAppViewContainer"] {
  background: #f5f6f8 !important;
  color: #333333 !important;
  height: 100vh !important;
}

/* Remove ALL default block padding and margin */
[data-testid="block-container"] {
  padding: 4px 8px !important;
  margin: 0 !important;
  max-width: 100% !important;
}
[data-testid="stVerticalBlock"] { gap: 4px !important; }
[data-testid="stHorizontalBlock"] { gap: 6px !important; }

/* Remove top dead space */
.main > div:first-child { padding-top: 0 !important; }
section[data-testid="stMain"] > div { padding-top: 0 !important; }

/* Chat message bubbles */
.user-bubble {
  background: #ffffff; border: 1px solid #e0e0e0;
  border-radius: 12px 12px 4px 12px;
  padding: 8px 12px; margin: 4px 0 4px 40px;
  font-size: 12px; color: #333333; line-height: 1.4;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.assistant-bubble {
  background: #ffffff; border: 1px solid #2196f3;
  border-radius: 12px 12px 12px 4px;
  padding: 8px 12px; margin: 4px 40px 4px 0;
  font-size: 12px; color: #333333; line-height: 1.4;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.sys-bubble {
  background: #fdfdfd; border: 1px solid #e0e0e0;
  border-radius: 6px; padding: 5px 10px; margin: 3px 0;
  font-size: 11px; color: #555555; font-style: italic;
}
.error-bubble {
  background: #fff4f4; border: 1px solid #ffcdd2;
  border-radius: 6px; padding: 6px 10px; margin: 3px 0;
  font-size: 11px; color: #d32f2f;
}
/* Metric strip */
.metric-row { display:flex; gap:8px; flex-wrap:wrap; margin:4px 0 6px; }
.metric-card {
  background:#ffffff; border:1px solid #e0e0e0; border-radius:6px;
  padding:6px 12px; min-width:90px; flex:1;
}
.metric-card .lbl { font-size:9px; color:#757575; text-transform:uppercase; letter-spacing:.08em; }
.metric-card .val { font-size:1.1rem; font-weight:700; color:#2196f3; }

/* Buttons */
button[data-testid="baseButton-secondary"] {
  border-radius: 6px !important;
  background: #ffffff !important;
  border-color: #e0e0e0 !important;
  color: #333333 !important;
  padding: 2px 8px !important;
  font-size: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session state initialisation ──────────────────────────────────────────────
if "messages"     not in st.session_state: st.session_state.messages     = []
if "design_state" not in st.session_state: st.session_state.design_state = empty_state()
if "glb_paths"    not in st.session_state: st.session_state.glb_paths    = {}
if "pipeline_result" not in st.session_state: st.session_state.pipeline_result = None
if "pending_parameters" not in st.session_state: st.session_state.pending_parameters = None
if "last_failed_intent" not in st.session_state: st.session_state.last_failed_intent = None
if "history"          not in st.session_state: st.session_state.history          = []


# ── Caching helpers ───────────────────────────────────────────────────────────
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
    return html.replace("__CONFIG__", json.dumps({"components": comp_configs}, separators=(",", ":")))


# ── Helpers ───────────────────────────────────────────────────────────────────
def _fmt(v, d=0):
    try:    return f"{float(v):.{d}f}"
    except: return "—"

def _kinematics_html(meta: dict) -> str:
    metrics = [
        ("Input RPM",  _fmt(meta.get("input_speed_rpm",  0))),
        ("Output RPM", _fmt(meta.get("output_speed_rpm", 0))),
        ("Torque",     _fmt(meta.get("output_torque_nm", 0), 2) + " Nm"),
        ("Ratio",      f"{meta.get('target_ratio','—')}:1"),
        ("Stages",     str(meta.get("num_stages", "—"))),
    ]
    cards = '<div class="metric-row">'
    for lbl, val in metrics:
        cards += f'<div class="metric-card"><div class="lbl">{lbl}</div><div class="val">{val}</div></div>'
    return cards + "</div>"

EXAMPLE_PROMPTS = [
    "Design a 4:1 gearbox at 1500 RPM with 10 Nm",
    "Design a 6:1 gearbox at 3000 RPM with 25 Nm",
    "Create a shaft 120mm long, diameter 20mm, with a module 3 gear (30 teeth)",
    "Add a flange with 15mm thickness to the current assembly",
    "Add a coupling between the existing shafts",
]


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT — Sidebar (Editing) | Main (Chat + Viewer)
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🛠️ Parametric Editing")
    comps = st.session_state.design_state.get("components", [])
    if not comps:
        st.info("No active components.")
    else:
        comp_ids = [c.get("id") for c in comps if "id" in c]
        selected_id = st.selectbox("Select Component", options=comp_ids)
        if selected_id:
            # Find component
            comp_idx = next((i for i, c in enumerate(comps) if c.get("id") == selected_id), None)
            if comp_idx is not None:
                comp = comps[comp_idx]
                st.markdown(f"**Type:** `{comp.get('type')}`")
                
                # Editable parameters
                editable_keys = ["length", "diameter", "module", "teeth", "width", "thickness", "inner_diameter", "outer_diameter"]
                new_params = {}
                for k in editable_keys:
                    if k in comp:
                        val = comp[k]
                        if isinstance(val, (int, float)):
                            if isinstance(val, int):
                                new_params[k] = st.number_input(k.capitalize(), value=val, step=1)
                            else:
                                new_params[k] = st.number_input(k.capitalize(), value=float(val), step=0.1)

                if st.button("Apply Changes", use_container_width=True, type="primary"):
                    # Push history
                    st.session_state.history.append({
                        "messages": list(st.session_state.messages),
                        "design_state": dict(st.session_state.design_state),
                        "glb_paths": dict(st.session_state.glb_paths),
                        "pipeline_result": st.session_state.pipeline_result
                    })
                    # Update component
                    for k, v in new_params.items():
                        st.session_state.design_state["components"][comp_idx][k] = v
                    
                    # Fast rebuild
                    with st.spinner(f"Rebuilding {selected_id}..."):
                        try:
                            res = recompile_assembly(st.session_state.design_state, "parametric_edit")
                            if res.get("status") == "success":
                                st.session_state.design_state["metadata"] = res.get("metadata", {})
                                st.session_state.glb_paths = res.get("glb_paths", {})
                                st.session_state.pipeline_result = res
                                st.success("Rebuilt successfully!")
                            else:
                                st.error(res.get("message", "Rebuild failed"))
                        except Exception as e:
                            st.error(f"Error: {e}")
                    st.rerun()

col_chat, col_viewer = st.columns([1, 2.5], gap="small")

# ══════════════════════════════════════════════════════════════════════════════
# LEFT — Chat Panel
# ══════════════════════════════════════════════════════════════════════════════
with col_chat:
    # Header + controls
    hdr_l, hdr_r = st.columns([3, 1])
    with hdr_l:
        st.markdown("### ⚙️ Agentic CAD")
        comp_count = len(st.session_state.design_state.get("components", []))
        st.caption(f"{'🟢 Active design · ' + str(comp_count) + ' components' if comp_count else '⬜ No active design'}")
    with hdr_r:
        if st.button("＋ New", help="Start a new design", use_container_width=True):
            st.session_state.history.append({
                "messages": list(st.session_state.messages),
                "design_state": dict(st.session_state.design_state),
                "glb_paths": dict(st.session_state.glb_paths),
                "pipeline_result": st.session_state.pipeline_result
            })
            st.session_state.messages     = []
            st.session_state.design_state = empty_state()
            st.session_state.glb_paths    = {}
            st.session_state.pipeline_result = None
            st.session_state.pending_parameters = None
            st.session_state.last_failed_intent = None
            load_glb_b64.clear()
            get_mesh_props.clear()
            st.rerun()
        if st.session_state.history:
            if st.button("↩ Undo", help="Revert to previous state", use_container_width=True):
                prev = st.session_state.history.pop()
                st.session_state.messages = prev["messages"]
                st.session_state.design_state = prev["design_state"]
                st.session_state.glb_paths = prev["glb_paths"]
                st.session_state.pipeline_result = prev["pipeline_result"]
                st.session_state.pending_parameters = None
                st.session_state.last_failed_intent = None
                st.rerun()

    st.markdown("---")

    # Example prompts (collapsed by default)
    with st.expander("📋 Example Prompts", expanded=comp_count == 0):
        for ex in EXAMPLE_PROMPTS:
            if st.button(ex, key=f"ex_{ex[:20]}", use_container_width=True):
                st.session_state["_pending_prompt"] = ex
                st.rerun()

    # Chat history
    chat_container = st.container(height=380)
    with chat_container:
        if not st.session_state.messages:
            st.markdown('<div class="sys-bubble">Enter a prompt below to begin synthesis…</div>',
                        unsafe_allow_html=True)
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f'<div class="user-bubble">🧑 {msg["content"]}</div>',
                            unsafe_allow_html=True)
            elif msg["role"] == "assistant":
                st.markdown(f'<div class="assistant-bubble">🤖 {msg["content"]}</div>',
                            unsafe_allow_html=True)
            elif msg["role"] == "error":
                st.markdown(f'<div class="error-bubble">⚠️ {msg["content"]}</div>',
                            unsafe_allow_html=True)
            elif msg["role"] == "system":
                st.markdown(f'<div class="sys-bubble">{msg["content"]}</div>',
                            unsafe_allow_html=True)

    # ── Prompt input ──────────────────────────────────────────────────────────
    pending = st.session_state.pop("_pending_prompt", None)
    prompt  = st.chat_input("Describe what to design or modify…")
    if pending and not prompt:
        prompt = pending

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Determine if this is continuation or fresh
        previous = st.session_state.design_state if st.session_state.design_state.get("components") else None
        
        # Grab parameter state
        pending_params = st.session_state.pending_parameters
        failed_intent = st.session_state.last_failed_intent

        with st.spinner("🔧 Synthesising…"):
            load_glb_b64.clear()
            get_mesh_props.clear()
            try:
                result = run_agentic_pipeline(
                    prompt, 
                    previous_state=previous,
                    pending_parameters=pending_params,
                    last_failed_intent=failed_intent
                )
            except Exception as e:
                result = {"status": "error", "message": str(e)}

        if result.get("status") == "success":
            # Clear parameter state on success
            st.session_state.pending_parameters = None
            st.session_state.last_failed_intent = None

            n_comp = len(result.get("components", []))
            
            if n_comp == 0:
                err = "Unsupported geometry or failed plan generation"
                st.session_state.messages.append({"role": "error", "content": err})
            else:
                # Push current state to history before updating
                st.session_state.history.append({
                    "messages": list(st.session_state.messages[:-1]),  # exclude the current prompt
                    "design_state": dict(st.session_state.design_state),
                    "glb_paths": dict(st.session_state.glb_paths),
                    "pipeline_result": st.session_state.pipeline_result
                })
                # Update persisted design state
                st.session_state.design_state = {
                    "components":    result.get("components", []),
                    "relationships": result.get("relationships", []),
                    "metadata":      result.get("metadata", {}),
                }
                st.session_state.glb_paths       = result.get("glb_paths", {})
                st.session_state.pipeline_result = result

                n_glb  = len([p for p in result.get("glb_paths", {}).values()
                              if os.path.exists(p["path"])])
                action = "Updated" if previous else "Generated"
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": (
                        f"{action} assembly · **{n_comp} components** · {n_glb} meshes exported.\n"
                        f"{'Continuation: added/modified components on existing design.' if previous else 'Fresh design synthesised.'}"
                    )
                })
        
        elif result.get("status") == "missing_parameters":
            # Save state to allow the user to provide missing info
            st.session_state.pending_parameters = result["missing_fields"]
            st.session_state.last_failed_intent = result["intent"]
            
            missing_str = ", ".join(result["missing_fields"])
            st.session_state.messages.append({
                "role": "assistant", 
                "content": f"I need a few more details to create the **{result['intent'].get('type', 'component')}**. Please provide: **{missing_str}**."
            })

        else:
            err = result.get("message", "Unknown error")
            st.session_state.messages.append({"role": "error", "content": err})

        st.rerun()

    # ── Kinematic Telemetry (collapsible) ─────────────────────────────────────
    res = st.session_state.pipeline_result
    if res and res.get("status") == "success":
        meta = res.get("metadata", {})
        
        # Display Engineering Warnings
        warnings = meta.get("engineering_warnings", [])
        if warnings:
            for w in warnings:
                st.markdown(f'<div class="error-bubble">🚨 {w}</div>', unsafe_allow_html=True)
                
        with st.expander("📊 Kinematic Telemetry", expanded=False):
            st.markdown(_kinematics_html(meta), unsafe_allow_html=True)
            if meta:
                st.json(meta, expanded=False)


# ══════════════════════════════════════════════════════════════════════════════
# RIGHT — 3D CAD Viewer
# ══════════════════════════════════════════════════════════════════════════════
with col_viewer:
    glb_paths = st.session_state.glb_paths
    available = {cid: info for cid, info in glb_paths.items()
                 if os.path.exists(info["path"])}

    if not available:
        st.markdown(
            '<div style="height:680px;display:flex;align-items:center;justify-content:center;'
            'background:#ffffff;border-radius:12px;border:1px solid #e0e0e0;">'
            '<span style="color:#757575;font-size:14px;letter-spacing:2px;">NO ASSEMBLY LOADED</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        # Build component config for Three.js
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
