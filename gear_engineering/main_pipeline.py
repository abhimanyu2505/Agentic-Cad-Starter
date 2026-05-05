"""
main_pipeline.py
================
Agentic CAD — main orchestration pipeline.

Routing priority:
  A. Explicit parameter completion   — user answered a follow-up Q
  B. Implicit parameter merging      — parameter-only reply (e.g. '120mm long')
  C. Continuation delta              — modification on existing design
  D. Gearbox hard-lock              — ALWAYS synthesizer, NEVER LLM
  E. Intent clarification           — ambiguous single-word prompts
  F. Fresh LLM plan
  G. Scoped deterministic fallback  — only parses detected component type

generation_mode:
  'minimal'  (default) — generate only what the user asked, no auto-injection
  'realistic'          — full mechanical realism (shafts, bearings auto-added)

All debug outputs → outputs/
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

from core.intent import extract_intents
from core.planner import build_execution_graph
from core.memory import log_success, log_failure, get_similar_design
from core.component_schemas import (
    COMPONENT_SCHEMAS,
    detect_component,
    missing_parameters,
    question_for,
)
from utils.logger import log
from core.router import route_node, is_cadquery_available
from assembly.assembly_builder import build_assembly


# ---------------------------------------------------------------------------
# Keyword helpers
# ---------------------------------------------------------------------------

_GEARBOX_KEYWORDS = [
    "gearbox", "gear box", "gear ratio", "reduction", "speed ratio",
    "rpm target", "output rpm", "gear train", "transmission design",
    "target ratio", "speed reducer",
]


def _is_gearbox_request(prompt: str) -> bool:
    return any(kw in prompt.lower() for kw in _GEARBOX_KEYWORDS)


def _parse_gearbox_params(prompt: str) -> dict:
    params = {
        "target_ratio":    None,
        "input_speed_rpm": 1500.0,
        "input_torque":    1.0,
        "max_stages":      3,
        "max_gear_teeth":  120,
    }
    ratio_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?::\s*1|x\s*reduction|[- ]to[- ]1|:1|ratio)",
        prompt, re.IGNORECASE,
    )
    if ratio_match:
        params["target_ratio"] = float(ratio_match.group(1))
    rpm_match = re.search(r"(\d+(?:\.\d+)?)\s*rpm", prompt, re.IGNORECASE)
    if rpm_match:
        params["input_speed_rpm"] = float(rpm_match.group(1))
    torque_match = re.search(r"(\d+(?:\.\d+)?)\s*nm", prompt, re.IGNORECASE)
    if torque_match:
        params["input_torque"] = float(torque_match.group(1))
    stage_words = {"one": 1, "two": 2, "three": 3, "single": 1, "double": 2, "dual": 2}
    for word, val in stage_words.items():
        if word in prompt.lower():
            params["max_stages"] = val
            break
    stage_match = re.search(r"(\d)\s*[- ]?stage", prompt, re.IGNORECASE)
    if stage_match:
        params["max_stages"] = int(stage_match.group(1))
    return params


_RESET_KEYWORDS = [
    "new design", "restart", "create a new gearbox", "start over", "reset design",
]


def _is_reset_request(prompt: str) -> bool:
    return any(kw in prompt.lower() for kw in _RESET_KEYWORDS)


# ---------------------------------------------------------------------------
# Deterministic fallback parser
# ---------------------------------------------------------------------------

def _deterministic_parse_scoped(prompt: str, scoped_type: str = None) -> list:
    """
    Rule-based component extractor as a last resort when the LLM fails.
    If scoped_type is provided, it only attempts to parse that specific component type.
    """
    p = prompt.lower()
    components = []

    # Shaft
    if "shaft" in p and (scoped_type is None or scoped_type == "shaft"):
        length = 75.0
        diameter = 15.0
        m = re.search(r"(\d+(?:\.\d+)?)\s*mm\s*long", p)
        if m:
            length = float(m.group(1))
        m = re.search(r"diameter\s*(?:of\s*)?(\d+(?:\.\d+)?)", p)
        if m:
            diameter = float(m.group(1))
        m = re.search(r"(\d+(?:\.\d+)?)\s*mm\s*diameter", p)
        if m:
            diameter = float(m.group(1))
        components.append({
            "id": "shaft_1", "type": "shaft",
            "length": length, "diameter": diameter,
        })

    # Gear
    if "gear" in p and "gearbox" not in p and (scoped_type is None or scoped_type == "gear"):
        module = 2.0
        teeth  = 20
        m = re.search(r"module\s*(\d+(?:\.\d+)?)", p)
        if m:
            module = float(m.group(1))
        m = re.search(r"(\d+)\s*teeth", p)
        if m:
            teeth = int(m.group(1))
        components.append({
            "id": f"gear_{len(components) + 1}", "type": "gear",
            "module": module, "teeth": teeth,
        })

    # Bearing
    if "bearing" in p and (scoped_type is None or scoped_type == "bearing"):
        id_  = 20.0
        od   = 40.0
        w    = 10.0
        m = re.search(r"(\d+(?:\.\d+)?)\s*mm\s*inner", p)
        if m:
            id_ = float(m.group(1))
        m = re.search(r"(\d+(?:\.\d+)?)\s*mm\s*outer", p)
        if m:
            od = float(m.group(1))
        components.append({
            "id": "bearing_1", "type": "bearing",
            "inner_diameter": id_, "outer_diameter": od, "width": w,
        })

    # Bolt
    if "bolt" in p and (scoped_type is None or scoped_type == "bolt"):
        dia = 6.0
        length = 30.0
        m = re.search(r"m(\d+)", p)
        if m:
            dia = float(m.group(1))
        components.append({
            "id": "bolt_1", "type": "bolt",
            "diameter": dia, "length": length,
        })

    # Flange
    if "flange" in p and (scoped_type is None or scoped_type == "flange"):
        dia = 80.0
        thick = 10.0
        m = re.search(r"(\d+(?:\.\d+)?)\s*mm", p)
        if m:
            dia = float(m.group(1))
        components.append({
            "id": "flange_1", "type": "flange",
            "diameter": dia, "thickness": thick,
        })

    # Generic cylinder / box / cone / sphere
    if "cylinder" in p and (scoped_type is None or scoped_type == "cylinder"):
        rad = 25.0
        h   = 50.0
        m = re.search(r"radius\s*(\d+(?:\.\d+)?)", p)
        if m:
            rad = float(m.group(1))
        m = re.search(r"height\s*(\d+(?:\.\d+)?)", p)
        if m:
            h = float(m.group(1))
        components.append({
            "id": "cylinder_1", "type": "cylinder",
            "radius": rad, "height": h,
        })

    if ("box" in p or "cube" in p) and (scoped_type is None or scoped_type == "box"):
        components.append({
            "id": "box_1", "type": "box",
            "length": 50.0, "width": 50.0, "height": 50.0,
        })

    return components


# ---------------------------------------------------------------------------
# LLM output validation & normalisation
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS: dict = {
    "gear":     ["module", "teeth"],
    "shaft":    ["length", "diameter"],
    "bolt":     ["diameter", "length", "thread_type", "pitch"],
    "flange":   ["diameter", "thickness"],
    "plate":    ["length", "width"],
    "nut":      ["diameter"],
    "bearing":  ["inner_diameter", "outer_diameter", "width"],
    "coupling": ["length", "diameter"],
    "bracket":  ["length", "width", "height"],
    "housing":  ["length", "width", "height"],
    "cylinder": ["radius", "height"],
    "box":      ["length", "width", "height"],
    "cone":     ["diameter", "height"],
    "sphere":   ["radius"],
}

_DEFAULTS: dict = {
    "module": 2.0, "teeth": 20, "pressure_angle": 20.0,
    "length": 50.0, "diameter": 15.0, "width": 50.0, "height": 50.0,
    "thickness": 10.0, "radius": 25.0,
    "inner_diameter": 20.0, "outer_diameter": 40.0,
}

_GUIDANCE: dict = {
    "gear":     "e.g. 'Create a module 2 gear with 30 teeth'",
    "shaft":    "e.g. 'Create a shaft 100mm long and 15mm diameter'",
    "gearbox":  "e.g. 'Design a 4:1 gearbox at 1500 RPM with 10 Nm'",
    "bolt":     "e.g. 'Add an M6 bolt 30mm long'",
    "bearing":  "e.g. 'Add a bearing with 20mm inner and 40mm outer diameter'",
    "flange":   "e.g. 'Create a flange 80mm diameter 10mm thick'",
    "default":  (
        "Try: 'Create a shaft 100mm long' or "
        "'Design a 4:1 gearbox at 1500 RPM'"
    ),
}

_TASK_REQUIRED_FIELDS: dict = {
    **{name: schema["required"] for name, schema in COMPONENT_SCHEMAS.items()},
    # Gear-pair remains a relationship task built from two gear schemas.
    "gear_pair": ["module", "teeth_1", "teeth_2"],
}

_LEGACY_TASK_REQUIRED_FIELDS: dict = {
    "gear": ["module", "teeth"],
    "gear_pair": ["module", "teeth_1", "teeth_2"],
    "shaft": ["length", "diameter"],
    "bolt": ["diameter", "length", "thread_type", "pitch"],
    "flange": ["diameter", "thickness"],
    "plate": ["length", "width"],
    "bearing": ["inner_diameter", "outer_diameter", "width"],
    "housing": ["length", "width", "height"],
    "cylinder": ["radius", "height"],
    "box": ["length", "width", "height"],
    "cone": ["diameter", "height"],
    "sphere": ["radius"],
}

_PARAM_ALIASES = {
    "teeth": "teeth",
    "tooth": "teeth",
    "module": "module",
    "length": "length",
    "long": "length",
    "diameter": "diameter",
    "dia": "diameter",
    "width": "width",
    "height": "height",
    "thickness": "thickness",
    "thick": "thickness",
    "radius": "radius",
    "inner": "inner_diameter",
    "outer": "outer_diameter",
    "pitch": "pitch",
    "thread": "thread_type",
}


def _relationship_type(rel: dict) -> str:
    """Normalise relationship aliases for validation and layout."""
    rel_type = rel.get("type")
    return "meshing" if rel_type == "mesh" else rel_type


def _normalise_relationships(relationships: list) -> list:
    rels = []
    for rel in relationships or []:
        clean = dict(rel)
        clean["type"] = _relationship_type(clean)
        rels.append(clean)
    return rels


def _detect_task_type(prompt: str, clarification_choice: str = None) -> str:
    text = (clarification_choice or prompt or "").lower()
    if "gear pair" in text or ("meshing" in text and "gear" in text):
        return "gear_pair"
    if _is_gearbox_request(text):
        return "gearbox"
    return detect_component(text)


def _extract_task_parameters(prompt: str, task_type: str = None) -> dict:
    """Small deterministic extractor for question-flow parameters."""
    p = (prompt or "").lower()
    params = {}

    for name, value in re.findall(
        r"(module|teeth|tooth|length|long|diameter|dia|width|height|"
        r"thickness|thick|radius|inner|outer|pitch)\s*(?:of|:|=)?\s*"
        r"(\d+(?:\.\d+)?)",
        p,
    ):
        key = _PARAM_ALIASES.get(name)
        if key:
            params[key] = float(value)

    unit_patterns = [
        (r"(\d+(?:\.\d+)?)\s*mm\s*long", "length"),
        (r"(\d+(?:\.\d+)?)\s*mm\s*diameter", "diameter"),
        (r"(\d+(?:\.\d+)?)\s*mm\s*inner", "inner_diameter"),
        (r"(\d+(?:\.\d+)?)\s*mm\s*outer", "outer_diameter"),
        (r"(\d+(?:\.\d+)?)\s*mm\s*wide", "width"),
        (r"(\d+(?:\.\d+)?)\s*mm\s*pitch", "pitch"),
        (r"(\d+(?:\.\d+)?)\s*mm\s*thick", "thickness"),
        (r"module\s*(\d+(?:\.\d+)?)", "module"),
    ]
    for pattern, key in unit_patterns:
        match = re.search(pattern, p)
        if match:
            params[key] = float(match.group(1))

    teeth_values = [int(v) for v in re.findall(r"(\d+)\s*(?:teeth|tooth)", p)]
    if task_type == "gear_pair":
        if len(teeth_values) >= 1:
            params["teeth_1"] = teeth_values[0]
        if len(teeth_values) >= 2:
            params["teeth_2"] = teeth_values[1]
        ratio_match = re.search(r"(\d+)\s*(?::|-to-)\s*(\d+)", p)
        if ratio_match and "teeth_1" not in params and "teeth_2" not in params:
            params["teeth_1"] = int(ratio_match.group(1)) * 20
            params["teeth_2"] = int(ratio_match.group(2)) * 20
    elif teeth_values:
        params["teeth"] = teeth_values[0]

    thread_match = re.search(r"\b(M|UNC|UNF)\s*(\d+(?:\.\d+)?)?\b", prompt or "", re.IGNORECASE)
    if thread_match and task_type == "bolt":
        params["thread_type"] = thread_match.group(1).upper()
        if thread_match.group(2) and "diameter" not in params:
            params["diameter"] = float(thread_match.group(2))

    bare_numbers = [float(v) for v in re.findall(r"\b\d+(?:\.\d+)?\b", p)]
    if task_type == "gear_pair" and bare_numbers:
        missing_teeth = [f for f in ("teeth_1", "teeth_2") if f not in params]
        for field, value in zip(missing_teeth, bare_numbers):
            params[field] = int(value)

    if "teeth" in params:
        params["teeth"] = int(params["teeth"])
    if task_type == "cylinder" and "diameter" in params and "radius" not in params:
        params["radius"] = float(params["diameter"]) / 2.0
    if task_type == "bolt" and "thread_type" not in params and "metric" in p:
        params["thread_type"] = "M"
    return params


def _map_bare_numbers_to_missing(prompt: str, missing: list, extracted: dict) -> dict:
    """Map terse answers like '2 and 30' onto the active missing fields."""
    numbers = [float(v) for v in re.findall(r"\b\d+(?:\.\d+)?\b", prompt or "")]
    additions = {}
    open_fields = [field for field in missing if field not in extracted]
    for field, value in zip(open_fields, numbers):
        if field in ("teeth", "teeth_1", "teeth_2", "hole_count"):
            additions[field] = int(value)
        else:
            additions[field] = value
    return additions


def _missing_for_task(task_type: str, parameters: dict) -> list:
    if task_type in COMPONENT_SCHEMAS:
        return missing_parameters(task_type, parameters)
    required = _TASK_REQUIRED_FIELDS.get(task_type, [])
    return [field for field in required if parameters.get(field) is None]


def _question_for_missing(task_type: str, missing: list) -> str:
    if task_type in COMPONENT_SCHEMAS:
        return question_for(task_type, missing)
    readable = ", ".join(field.replace("_", " ") for field in missing)
    examples = {
        "gear_pair": "Please provide the shared module and both gear tooth counts.",
        "gear": "Please provide the module and tooth count.",
        "shaft": "Please provide the length and diameter.",
        "bolt": "Please provide bolt diameter, length, thread type, and pitch.",
        "bearing": "Please provide inner diameter, outer diameter, and width.",
    }
    return examples.get(task_type, f"Please provide: {readable}.")


def _component_from_task(task: dict) -> dict:
    task_type = task.get("type")
    params = dict(task.get("parameters", {}))
    if task_type == "gear_pair":
        module = float(params["module"])
        teeth_1 = int(params["teeth_1"])
        teeth_2 = int(params["teeth_2"])
        center_distance = module * (teeth_1 + teeth_2) / 2.0
        return {
            "components": [
                {
                    "id": "gear_1", "type": "gear", "module": module,
                    "teeth": teeth_1, "pressure_angle": 20.0,
                    "face_width": 8.0 * module,
                    "center_distance": center_distance,
                },
                {
                    "id": "gear_2", "type": "gear", "module": module,
                    "teeth": teeth_2, "pressure_angle": 20.0,
                    "face_width": 8.0 * module,
                    "center_distance": center_distance,
                },
            ],
            "relationships": [{
                "type": "meshing",
                "from_id": "gear_2",
                "to_id": "gear_1",
                "distance": center_distance,
            }],
            "metadata": {"intent_type": "gear_pair", "generation_path": "deterministic"},
        }

    comp = {"id": f"{task_type}_1", "type": task_type}
    comp.update(params)
    if task_type == "gear" and "face_width" not in comp:
        comp["face_width"] = 8.0 * float(comp["module"])
    return {
        "components": [comp],
        "relationships": [],
        "metadata": {"intent_type": task_type, "generation_path": "deterministic"},
    }


def _validate_generation_result(plan: dict, task: dict = None) -> tuple:
    """Post-generation structural checks that return (valid, errors)."""
    errors = []
    components = plan.get("components", [])
    relationships = plan.get("relationships", [])
    if task and task.get("type") == "gear_pair":
        gears = [c for c in components if c.get("type") == "gear"]
        if len(gears) != 2 or len(components) != 2:
            errors.append("Gear pair must generate exactly two gears.")
        modules = {float(g.get("module", -1)) for g in gears}
        if len(modules) != 1:
            errors.append("Gear pair must use the same module on both gears.")
        has_mesh = any(
            r.get("type") in ("mesh", "meshing")
            and {r.get("from_id"), r.get("to_id")} == {"gear_1", "gear_2"}
            for r in relationships
        )
        if not has_mesh:
            errors.append("Gear pair must include a meshing relationship.")
    return not errors, errors


def _validate_and_fill_components(components: list) -> tuple:
    """
    Validate every component for required fields.
    For each missing field: apply a sensible default and record a warning.
    Returns (cleaned_components, warning_strings).
    """
    warnings = []
    cleaned  = []

    for comp in components:
        ctype = comp.get("type")
        if not ctype:
            warnings.append(
                "A component was returned without a 'type' field and was skipped."
            )
            continue

        required = _REQUIRED_FIELDS.get(ctype, [])
        for field in required:
            if field not in comp or comp[field] is None:
                default = _DEFAULTS.get(field)
                if default is not None:
                    comp[field] = default
                    warnings.append(
                        f"[{ctype}] Missing '{field}' — using default {default}."
                    )
                else:
                    warnings.append(
                        f"[{ctype}] Missing required field '{field}' and no default exists."
                    )

        # Ensure id is set
        if not comp.get("id"):
            comp["id"] = f"{ctype}_{len(cleaned) + 1}"

        cleaned.append(comp)

    return cleaned, warnings


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Ambiguity detection
# ---------------------------------------------------------------------------

_AMBIGUOUS_TERMS = {
    "shaft": [
        "Basic shaft only",
        "Shaft with bearings at ends",
        "Shaft with a mounted gear",
    ],
    "gear": [
        "Single spur gear",
        "Gear pair (two meshing gears)",
        "Gear mounted on a shaft",
    ],
    "bearing": [
        "Single ball bearing",
        "Bearing pair for a shaft",
    ],
    "gearbox": [
        "Simple gearbox (need ratio)",
        "Multi-stage gearbox (need ratio + stages)",
    ],
}

_SINGLE_WORD_THRESHOLD = 5  # words; below this may be ambiguous


def _is_ambiguous(prompt: str) -> tuple:
    """
    Returns (True, component_type, options) if the prompt is ambiguous,
    otherwise (False, None, []).
    A prompt is ambiguous when it names exactly one component type with
    no numeric parameters and no clarifying adjectives.
    """
    p    = prompt.strip().lower()
    words = p.split()
    # Only check short prompts with no numbers
    if len(words) > _SINGLE_WORD_THRESHOLD:
        return False, None, []
    import re
    if re.search(r'\d', p):
        return False, None, []
    for comp_type, options in _AMBIGUOUS_TERMS.items():
        if comp_type in p:
            return True, comp_type, options
    return False, None, []


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_agentic_pipeline(
    prompt_text: str,
    previous_state: dict = None,
    pending_parameters: list = None,
    last_failed_intent: dict = None,
    conversation_history: list = None,
    generation_mode: str = "minimal",
    clarification_choice: str = None,
) -> dict:
    """Run strict CAD pipeline: intent detection -> parameter completion -> generation."""
    log("system", f"Incoming prompt: '{prompt_text}' [mode={generation_mode}]")

    from core.llm_client import MissingParametersError
    from core.state_manager import (
        empty_state, get_current_task, set_current_task,
        update_current_task_params, set_current_task_status,
        set_current_task_missing, clear_current_task, set_last_intent,
    )

    state = previous_state if previous_state is not None else empty_state()
    effective_prompt = clarification_choice or prompt_text
    ai_plan: dict = {}
    plan_graph: list = []
    ai_relationships: list = []

    try:
        # STAGE 1 — Intent detection
        active_task = get_current_task(state)
        if pending_parameters and last_failed_intent and not active_task:
            task_type = last_failed_intent.get("type", "component")
            set_current_task(
                state,
                task_type,
                {k: v for k, v in last_failed_intent.items() if k not in ("id", "type")},
                missing=pending_parameters,
                status="incomplete",
            )
            active_task = get_current_task(state)

        if clarification_choice:
            task_type = _detect_task_type(effective_prompt, clarification_choice)
            if active_task and active_task.get("type") == "gear" and task_type is None:
                task_type = "gear"
            if task_type:
                set_current_task(
                    state,
                    task_type,
                    active_task.get("parameters", {}) if active_task else {},
                    status="incomplete",
                )
                active_task = get_current_task(state)
            log("planner", f"intent_detected={task_type or 'unknown'} source=clarification")

        if not active_task:
            task_type = _detect_task_type(effective_prompt)
            if task_type:
                set_current_task(state, task_type, status="incomplete")
                active_task = get_current_task(state)
            else:
                is_ambig, ambig_type, ambig_options = _is_ambiguous(effective_prompt)
                if is_ambig:
                    set_current_task(state, ambig_type, status="incomplete")
                    log("planner", f"intent_detected={ambig_type} status=clarification")
                    return {
                        "status": "clarification",
                        "type": ambig_type,
                        "options": ambig_options,
                        "message": f"What kind of **{ambig_type}** would you like to create?",
                    }
            log("planner", f"intent_detected={task_type or 'llm_delta_or_plan'}")
        else:
            log("planner", f"intent_detected={active_task.get('type')} source=current_task")

        # Gearbox hard-lock remains deterministic, but asks before generation.
        if active_task and active_task.get("type") == "gearbox":
            gb_params = _parse_gearbox_params(effective_prompt)
            active_task["parameters"].update({k: v for k, v in gb_params.items() if v is not None})
            if active_task["parameters"].get("target_ratio") is None:
                active_task["missing"] = ["target_ratio"]
                active_task["status"] = "incomplete"
                return {
                    "status": "question",
                    "question": "What target ratio should the gearbox achieve? For example: 4:1.",
                    "missing": ["target_ratio"],
                    "intent": {"type": "gearbox", "parameters": active_task["parameters"]},
                }
            set_current_task_status(state, "complete")
            log("planner", f"parameters_extracted={active_task['parameters']}")

            from core.gearbox_synthesizer import synthesize_gearbox
            from core.design_intelligence import validate_cad_plan
            params = active_task["parameters"]
            generation_mode = "realistic"
            log("planner", "generation_path=synthesizer intent=gearbox")
            ai_plan = synthesize_gearbox(
                target_ratio=float(params["target_ratio"]),
                input_speed_rpm=float(params.get("input_speed_rpm", 1500.0)),
                input_torque=float(params.get("input_torque", 1.0)),
                max_stages=int(params.get("max_stages", 3)),
                max_gear_teeth=int(params.get("max_gear_teeth", 120)),
            )
            ai_plan.setdefault("metadata", {})["flow_type"] = "gearbox"
            ai_plan["relationships"] = _normalise_relationships(ai_plan.get("relationships", []))
            ai_plan, eng_warns = validate_cad_plan(ai_plan)
            if eng_warns:
                ai_plan.setdefault("metadata", {})["engineering_warnings"] = eng_warns
            plan_graph = ai_plan.get("components", [])

        elif active_task and active_task.get("type") in _TASK_REQUIRED_FIELDS:
            # STAGE 2 — Parameter completion
            current_missing = (
                active_task.get("missing")
                or _missing_for_task(active_task.get("type"), active_task.get("parameters", {}))
            )
            extracted = _extract_task_parameters(effective_prompt, active_task.get("type"))
            extracted.update(_map_bare_numbers_to_missing(effective_prompt, current_missing, extracted))
            update_current_task_params(state, extracted)
            active_task = get_current_task(state)
            missing = _missing_for_task(active_task.get("type"), active_task.get("parameters", {}))
            log("planner", f"parameters_extracted={extracted} accumulated={active_task.get('parameters', {})}")
            if missing:
                set_current_task_missing(state, missing)
                active_task = get_current_task(state)
                return {
                    "status": "question",
                    "question": _question_for_missing(active_task.get("type"), missing),
                    "missing": missing,
                    "intent": {
                        "type": active_task.get("type"),
                        "parameters": active_task.get("parameters", {}),
                        "missing": active_task.get("missing", []),
                        "status": active_task.get("status", "incomplete"),
                    },
                }

            # STAGE 3 — Generation
            set_current_task_missing(state, [])
            set_current_task_status(state, "complete")
            log("planner", f"generation_path=deterministic intent={active_task.get('type')}")
            ai_plan = _component_from_task(active_task)
            ai_plan["relationships"] = _normalise_relationships(ai_plan.get("relationships", []))
            plan_graph = ai_plan.get("components", [])

        elif state.get("components") and not _is_reset_request(effective_prompt):
            # Existing completed design: use a strict delta path, not fresh intent.
            from core.llm_client import generate_cad_delta
            from core.state_merger import apply_delta
            log("planner", "generation_path=llm_delta")
            delta = generate_cad_delta(
                effective_prompt,
                state,
                conversation_history=conversation_history,
            )
            delta["relationships"] = _normalise_relationships(delta.get("relationships", []))
            if delta.get("components"):
                delta["components"], val_warns = _validate_and_fill_components(delta["components"])
                if val_warns:
                    log("planner", f"validation_notes={val_warns}")
            merged = apply_delta(state, delta)
            plan_graph = merged["components"]
            ai_relationships = _normalise_relationships(merged["relationships"])
            ai_plan = {"metadata": state.get("metadata", {}), "relationships": ai_relationships}

        else:
            # Last resort: LLM plan only when deterministic intent detection cannot classify.
            log("planner", "generation_path=llm_plan")
            try:
                from core.llm_client import generate_cad_plan
                from core.design_intelligence import validate_cad_plan
                ai_plan = generate_cad_plan(
                    effective_prompt,
                    conversation_history=conversation_history,
                )
                raw_components = ai_plan.get("components", [])
                cleaned, val_warns = _validate_and_fill_components(raw_components)
                ai_plan["components"] = cleaned
                ai_plan["relationships"] = _normalise_relationships(ai_plan.get("relationships", []))
                if val_warns:
                    ai_plan.setdefault("metadata", {}).setdefault("validation_notes", []).extend(val_warns)
                ai_plan, eng_warns = validate_cad_plan(ai_plan)
                if eng_warns:
                    ai_plan.setdefault("metadata", {})["engineering_warnings"] = eng_warns
                plan_graph = ai_plan.get("components", [])
            except MissingParametersError as mpe:
                comp_type = mpe.intent.get("type", "component")
                return {
                    "status": "question",
                    "question": _question_for_missing(comp_type, mpe.missing_fields),
                    "missing": mpe.missing_fields,
                    "intent": mpe.intent,
                }

        # Post-generation validation before enrichment/compile.
        valid, validation_errors = _validate_generation_result(ai_plan, get_current_task(state))
        if not valid:
            return {
                "status": "error",
                "message": "Generated plan failed validation.",
                "errors": validation_errors,
            }

        if get_current_task(state) and get_current_task(state).get("type") in COMPONENT_SCHEMAS:
            generation_mode = "minimal"

        from assembly.mechanical_enricher import enrich_components
        ai_rels = _normalise_relationships(ai_plan.get("relationships", ai_relationships))
        plan_graph, ai_relationships = enrich_components(
            plan_graph, ai_rels, generation_mode=generation_mode
        )

        if get_current_task(state) and get_current_task(state).get("type") == "gear_pair":
            log("planner", "optimizer_skipped intent=gear_pair")
        else:
            from assembly.component_optimizer import optimize_components
            plan_graph, ai_relationships, _ = optimize_components(
                plan_graph, ai_relationships
            )
        ai_relationships = _normalise_relationships(ai_relationships)

        compiled_plan = {
            "components": plan_graph,
            "relationships": ai_relationships,
            "metadata": ai_plan.get("metadata", {}),
        }
        compiled_plan["metadata"]["generation_mode"] = generation_mode
        valid, validation_errors = _validate_generation_result(compiled_plan, get_current_task(state))
        if not valid:
            return {
                "status": "error",
                "message": "Compiled plan failed validation.",
                "errors": validation_errors,
            }

        result = recompile_assembly(compiled_plan, effective_prompt)
        if result.get("status") == "success":
            if plan_graph:
                set_last_intent(state, plan_graph[0])
            clear_current_task(state)
        return result

    except MissingParametersError as mpe:
        comp_type = mpe.intent.get("type", "component")
        log("planner", f"missing_parameters={mpe.missing_fields} intent={comp_type}")
        return {
            "status": "question",
            "question": _question_for_missing(comp_type, mpe.missing_fields),
            "missing": mpe.missing_fields,
            "intent": mpe.intent,
        }
    except Exception as exc:
        import traceback
        traceback.print_exc()
        log_failure(prompt_text, str(exc))
        return {
            "status":  "error",
            "message": (
                f"Something went wrong: {exc}. "
                f"Try: {_GUIDANCE['default']}"
            ),
        }


# ---------------------------------------------------------------------------
# Fast-path recompile (parametric edit — no LLM call)
# ---------------------------------------------------------------------------

def recompile_assembly(design_state: dict, prompt_text: str = "recompile") -> dict:
    """
    Rebuild the assembly from a (possibly mutated) design state dict
    without calling the LLM.
    """
    from core.llm_client import MissingParametersError

    os.makedirs("outputs", exist_ok=True)

    try:
        plan_graph       = design_state.get("components", [])
        ai_relationships = design_state.get("relationships", [])
        metadata         = design_state.get("metadata", {})
        score = "warning" if metadata.get("engineering_warnings") else "valid"

        if not plan_graph:
            return {
                "status":  "error",
                "message": (
                    "No components to build. "
                    f"Try: {_GUIDANCE['default']}"
                ),
            }

        compiled_components = []
        for idx, node in enumerate(plan_graph):
            comp_type = node.get("type", "unknown")
            if comp_type == "unknown":
                log("router",
                    f"Skipping component {idx} with unknown type.")
                continue

            log("router",
                f"Routing {idx+1}/{len(plan_graph)} → [{comp_type.upper()}]")
            try:
                result = route_node(node, prompt_text)
                node["extracted_parameters"] = result["node"].get(
                    "extracted_parameters", {}
                )
                compiled_components.append({"node": node, "solid": result["solid"]})
            except Exception as route_err:
                log("error",
                    f"Routing failed for '{comp_type}' ({route_err}) — skipping.")

        if not compiled_components:
            return {
                "status":  "error",
                "message": (
                    "All components failed to generate. "
                    "Check parameter values and try again."
                ),
            }

        # Debug compound export
        if is_cadquery_available():
            import cadquery as cq
            try:
                debug_comp = cq.Compound.makeCompound([
                    c["solid"].val() for c in compiled_components
                    if c["solid"] is not None
                ])
                cq.exporters.export(
                    debug_comp, "outputs/debug_enriched_components.step"
                )
            except Exception:
                pass

        if not is_cadquery_available():
            raise ImportError(
                "CadQuery is unavailable. "
                "Please run via Docker (docker-compose up)."
            )

        log("system", "Building assembly…")
        master_assembly = build_assembly(compiled_components, ai_relationships)

        step_filename = "outputs/agentic_assembly_output.step"
        master_assembly.save(step_filename)
        log("system", f"STEP → {step_filename}")

        # Per-component GLB export
        import trimesh
        import trimesh.exchange.gltf as tgltf
        import cadquery as cq

        glb_paths = {}
        export_paths = {
            "step": step_filename,
            "stl": {},
            "glb": {},
            "component_step": {},
        }
        for comp in compiled_components:
            solid     = comp["solid"]
            comp_id   = comp["node"].get("id")
            comp_type = comp["node"].get("type", "unknown")
            if solid and comp_id:
                stl_path = f"outputs/{comp_id}.stl"
                comp_step_path = f"outputs/{comp_id}.step"
                glb_path = f"outputs/{comp_id}.glb"
                try:
                    cq.exporters.export(solid, comp_step_path)
                    cq.exporters.export(solid, stl_path)
                    mesh = trimesh.load(stl_path, force="mesh")
                    try:
                        mesh = mesh.simplify_quadratic_decimation(50000)
                    except Exception:
                        pass
                    glb_data = tgltf.export_glb(trimesh.Scene([mesh]))
                    with open(glb_path, "wb") as f:
                        f.write(glb_data)
                    glb_paths[comp_id] = {"path": glb_path, "type": comp_type}
                    export_paths["stl"][comp_id] = stl_path
                    export_paths["glb"][comp_id] = glb_path
                    export_paths["component_step"][comp_id] = comp_step_path
                    log("system", f"GLB → {glb_path}")
                except Exception as e:
                    log("error", f"GLB export failed for {comp_id}: {e}")

        # Housing is a realistic-mode enrichment only.
        if metadata.get("generation_mode") == "realistic" or metadata.get("flow_type") == "gearbox":
            from assembly.housing_generator import generate_housing
            try:
                generate_housing(master_assembly)
                if os.path.exists("outputs/housing.glb"):
                    glb_paths["housing"] = {
                        "path": "outputs/housing.glb", "type": "housing"
                    }
                    export_paths["glb"]["housing"] = "outputs/housing.glb"
            except Exception as he:
                log("error", f"Housing generation skipped: {he}")

        log_success(prompt_text, plan_graph, score)

        return {
            "status":        "success",
            "metadata":      metadata,
            "components":    plan_graph,
            "relationships": ai_relationships,
            "glb_paths":     glb_paths,
            "export_paths":   export_paths,
        }

    except MissingParametersError as mpe:
        return {
            "status":         "missing_parameters",
            "intent":         mpe.intent,
            "missing_fields": mpe.missing_fields,
        }
    except Exception as exc:
        log("error", f"recompile_assembly failed: {exc}")
        log_failure(prompt_text, str(exc))
        return {
            "status":  "error",
            "message": (
                f"Assembly generation failed: {exc}. "
                "Try adjusting parameters or starting a new design."
            ),
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log("system", "Agentic CAD — CLI mode")
    examples = [
        "Create a shaft of length 50mm and a module 2 gear mounted to it",
        "I need a generic bolt",
        "Design a 4:1 gearbox at 1500 RPM with 10 Nm",
    ]
    for i, ex in enumerate(examples, 1):
        log("system", f"  {i}. {ex}")

    try:
        user_input = input("\n>> ").strip()
    except EOFError:
        user_input = ""

    if not user_input:
        user_input = "Create a shaft of length 75.5mm and a module 2 gear mounted to it"
        log("system", f"No input. Using default: '{user_input}'")

    result = run_agentic_pipeline(user_input)
    log("system", f"Pipeline result: status={result.get('status')}")
