import sys
import re
from core.intent import extract_intents
from core.planner import build_execution_graph

from core.memory import log_success, log_failure, get_similar_design
from utils.logger import log

from core.router import route_node, is_cadquery_available
from assembly.assembly_builder import build_assembly


# ---------------------------------------------------------------------------
# Gearbox request helpers
# ---------------------------------------------------------------------------

_GEARBOX_KEYWORDS = [
    "gearbox", "gear box", "gear ratio", "reduction", "speed ratio",
    "rpm target", "output rpm", "gear train", "transmission design",
    "target ratio",
]


def _is_gearbox_request(prompt: str) -> bool:
    """
    Returns True if the prompt appears to be a goal-driven gearbox design
    request rather than a direct component description.
    """
    prompt_lower = prompt.lower()
    return any(kw in prompt_lower for kw in _GEARBOX_KEYWORDS)


def _parse_gearbox_params(prompt: str) -> dict:
    """
    Extracts numeric gearbox design parameters from the prompt text using
    simple regex patterns. Returns sensible defaults for missing values.
    """
    params = {
        "target_ratio": None,
        "input_speed_rpm": 1500.0,
        "input_torque": 1.0,
        "max_stages": 3,
        "max_gear_teeth": 120,
    }

    # Target ratio: "4:1", "4.5:1", "ratio of 4", "4x reduction"
    ratio_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?::\s*1|x\s*reduction|[- ]to[- ]1|:1|ratio)", prompt, re.IGNORECASE
    )
    if ratio_match:
        params["target_ratio"] = float(ratio_match.group(1))

    # Input RPM: "1500 rpm", "at 1200rpm"
    rpm_match = re.search(r"(\d+(?:\.\d+)?)\s*rpm", prompt, re.IGNORECASE)
    if rpm_match:
        params["input_speed_rpm"] = float(rpm_match.group(1))

    # Torque: "5 Nm", "10nm"
    torque_match = re.search(r"(\d+(?:\.\d+)?)\s*nm", prompt, re.IGNORECASE)
    if torque_match:
        params["input_torque"] = float(torque_match.group(1))

    # Stages: "2 stage", "three stage"
    stage_words = {"one": 1, "two": 2, "three": 3, "single": 1, "double": 2, "dual": 2}
    for word, val in stage_words.items():
        if word in prompt.lower():
            params["max_stages"] = val
            break
    stage_match = re.search(r"(\d)\s*[- ]?stage", prompt, re.IGNORECASE)
    if stage_match:
        params["max_stages"] = int(stage_match.group(1))

    return params


# ---------------------------------------------------------------------------
# Continuation helpers
# ---------------------------------------------------------------------------

_RESET_KEYWORDS = ["new design", "restart", "create a new gearbox", "start over", "reset design"]

def _is_reset_request(prompt: str) -> bool:
    p = prompt.lower()
    return any(kw in p for kw in _RESET_KEYWORDS)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_agentic_pipeline(prompt_text: str, previous_state: dict = None, pending_parameters: list = None, last_failed_intent: dict = None):
    print("\n" + "="*50)
    print("   Startup-Level Agentic CAD Intelligence Platform   ")
    print("="*50 + "\n")
    log("system", f"Incoming Request Stream: '{prompt_text}'")

    from core.llm_client import MissingParametersError

    # Determine mode: continuation vs. fresh design
    is_continuation = (
        previous_state is not None
        and previous_state.get("components")
        and not _is_reset_request(prompt_text)
    )

    plan_graph = []
    ai_plan    = {}
    score      = "valid"
    ai_relationships = []

    try:
        # ==================================================================
        # PARAMETER COMPLETION FAST-PATH
        # ==================================================================
        if pending_parameters and last_failed_intent:
            log("system", "Parameter completion mode. Bypassing primary planner.")
            from core.llm_client import extract_parameters, CADPlan
            from pydantic import ValidationError

            # Extract just the missing values from the prompt
            extracted = extract_parameters(prompt_text, pending_parameters)
            log("planner", f"Extracted parameters: {extracted}")

            # Merge into the partial intent
            last_failed_intent.update(extracted)

            # Re-validate
            try:
                CADPlan(components=[last_failed_intent])
            except ValidationError as e:
                missing = [str(err["loc"][-1]) for err in e.errors() if err["type"] == "missing"]
                if missing:
                    raise MissingParametersError(last_failed_intent, list(set(missing)))

            # If valid, treat it as a delta 'add'
            delta = {
                "action": "add",
                "components": [last_failed_intent],
                "relationships": []
            }
            if previous_state:
                from core.state_merger import apply_delta
                merged_state = apply_delta(previous_state, delta)
                plan_graph = merged_state["components"]
                ai_relationships = merged_state["relationships"]
                ai_plan = {"metadata": previous_state.get("metadata", {}), "relationships": ai_relationships}
            else:
                plan_graph = [last_failed_intent]

        # ==================================================================
        # CONTINUATION MODE — LLM generates delta, system merges
        # ==================================================================
        elif is_continuation:
            log("system", f"Continuation mode. Existing components: {len(previous_state['components'])}")

            from core.llm_client import generate_cad_delta
            from core.state_merger import apply_delta

            delta = generate_cad_delta(prompt_text, previous_state)
            log("planner", f"LLM delta: action={delta['action']}, "
                           f"+{len(delta.get('components',[]))} comps, "
                           f"+{len(delta.get('relationships',[]))} rels. "
                           f"Reasoning: {delta.get('reasoning','—')}")

            merged_state = apply_delta(previous_state, delta)
            plan_graph       = merged_state["components"]
            ai_relationships = merged_state["relationships"]
            # Carry forward metadata from previous state
            ai_plan = {"metadata": previous_state.get("metadata", {}),
                       "relationships": ai_relationships}

        # ==================================================================
        # FRESH MODE — original phase 0 memory check + synthesizer/LLM
        # ==================================================================
        else:
            log("system", "Fresh design mode.")
            memory_result = get_similar_design(prompt_text)

            if memory_result.get("cached_hits", 0) > 0 and memory_result.get("plan"):
                plan_graph = memory_result["plan"]
                ai_plan    = {"metadata": {}}
                log("system", "Bypassing AI Layer. Proceeding with retrieved historical plan.")
            else:
                # ------------------------------------------------------------------
                # Phase 1: AI / Synthesis Execution Graph Planning
                # ------------------------------------------------------------------
                log("planner", "Analyzing request via AI Planning Layer...")
                from core.design_intelligence import validate_cad_plan

                try:
                    # --- Gearbox Synthesis Fast-Path ---
                    if _is_gearbox_request(prompt_text):
                        from core.gearbox_synthesizer import synthesize_gearbox

                        gb_params = _parse_gearbox_params(prompt_text)

                        if gb_params["target_ratio"] is None:
                            raise MissingParametersError(
                                {"type": "gearbox"}, 
                                ["target_ratio (e.g. '4:1' or '6x reduction')"]
                            )

                        log("planner", (
                            f"Gearbox synthesis mode activated — "
                            f"target_ratio={gb_params['target_ratio']}, "
                            f"input_speed={gb_params['input_speed_rpm']} RPM, "
                            f"input_torque={gb_params['input_torque']} Nm, "
                            f"max_stages={gb_params['max_stages']}"
                        ))

                        ai_plan = synthesize_gearbox(
                            target_ratio=gb_params["target_ratio"],
                            input_speed_rpm=gb_params["input_speed_rpm"],
                            input_torque=gb_params["input_torque"],
                            max_stages=gb_params["max_stages"],
                            max_gear_teeth=gb_params["max_gear_teeth"],
                        )

                    else:
                        # --- Normal LLM Path ---
                        from core.llm_client import generate_cad_plan, generate_primitive_plan
                        try:
                            ai_plan = generate_cad_plan(prompt_text)
                        except Exception as e:
                            log("planner", f"Primary planner failed or rejected non-mechanical intent: {e}")
                            log("planner", "Falling back to primitive geometry extraction...")
                            ai_plan = generate_primitive_plan(prompt_text)

                    # Design Intelligence Validation (shared by both paths)
                    ai_plan, warnings = validate_cad_plan(ai_plan)
                    if warnings:
                        score = "warning"
                        print("\n[DESIGN INTELLIGENCE WARNINGS]")
                        for w in warnings:
                            print(f" - {w}")
                        ai_plan.setdefault("metadata", {})["engineering_warnings"] = warnings

                    plan_graph = ai_plan.get("components", [])
                    log("planner", f"Plan graph resolved with {len(plan_graph)} component(s).")

                except Exception as ai_e:
                    log("error", f"AI Layer failed or unavailable ({ai_e}). Falling back to legacy NLP parsers...")
                    intents = extract_intents(prompt_text)
                    log("planner", f"Isolated operational node nouns: {intents}")
                    plan_graph = build_execution_graph(prompt_text, intents)

                    # Normalize legacy format to match new format for router
                    for node in plan_graph:
                        node["type"] = node.get("component", "unknown")


        # ------------------------------------------------------------------
        # Phase 1.5: Mechanical Enrichment
        # ------------------------------------------------------------------
        from assembly.mechanical_enricher import enrich_components
        ai_rels = ai_plan.get("relationships", []) if ai_plan else []
        plan_graph, ai_relationships = enrich_components(plan_graph, ai_rels)

        # ------------------------------------------------------------------
        # Phase 1.75: Component Optimization (deduplicate + bearing limit)
        # ------------------------------------------------------------------
        from assembly.component_optimizer import optimize_components
        plan_graph, ai_relationships, _ = optimize_components(plan_graph, ai_relationships)

        # ------------------------------------------------------------------
        # Phase 2 to 4: Compilation and Export
        # ------------------------------------------------------------------
        return recompile_assembly(
            {"components": plan_graph, "relationships": ai_relationships, "metadata": ai_plan.get("metadata", {})},
            prompt_text
        )

    except MissingParametersError as mpe:
        log("planner", f"Missing parameters: {mpe.missing_fields} for intent: {mpe.intent}")
        return {
            "status": "missing_parameters",
            "intent": mpe.intent,
            "missing_fields": mpe.missing_fields
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Pipeline fault execution sequence terminated unexpectedly: {e}"}

def recompile_assembly(design_state: dict, prompt_text: str = "recompile") -> dict:
    """
    Fast-path to rebuild the assembly from a modified state without calling the LLM.
    """
    from core.llm_client import MissingParametersError

    try:
        plan_graph = design_state.get("components", [])
        ai_relationships = design_state.get("relationships", [])
        metadata = design_state.get("metadata", {})
        score = "warning" if metadata.get("engineering_warnings") else "valid"

        compiled_components = []
        for idx, node in enumerate(plan_graph):
            comp_type = node.get("type", "unknown")
            if comp_type == "unknown":
                raise ValueError(
                    f"Planner failed extracting safe functional topology intents from '{prompt_text}'."
                )

            log("router", f"Routing node step {idx+1}/{len(plan_graph)} -> [{comp_type.upper()}] Subsystem Handler...")

            result = route_node(node, prompt_text)

            node["extracted_parameters"] = result["node"].get("extracted_parameters", {})
            compiled_components.append({"node": node, "solid": result["solid"]})

        # Debug export of all enriched solids before assembly
        if is_cadquery_available():
            import cadquery as cq
            try:
                debug_comp = cq.Compound.makeCompound([c["solid"].val() for c in compiled_components if c["solid"] is not None])
                cq.exporters.export(debug_comp, "outputs/debug_enriched_components.step")
                log("system", "Exported outputs/debug_enriched_components.step")
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Phase 3: Assembly Alignment Generation Subroutines
        # ------------------------------------------------------------------
        if not is_cadquery_available():
            raise ImportError(
                "CadQuery module bounds failed verification constraint. Launch via Docker Engine host."
            )

        log("system", "Fusing separated component geometry into native contiguous topological assembly structure...")
        master_assembly = build_assembly(compiled_components, ai_relationships)

        # Write output payloads out through B-Rep host boundary
        import os
        os.makedirs("outputs", exist_ok=True)
        step_filename = "outputs/agentic_assembly_output.step"
        master_assembly.save(step_filename)
        log("system", f"B-Rep assembly volume sequence safely written to host folder locally: {step_filename}")

        # Export individual GLBs for GUI visibility toggles
        import trimesh, trimesh.exchange.gltf as tgltf
        glb_paths = {}
        for comp in compiled_components:
            solid = comp["solid"]
            comp_id = comp["node"].get("id")
            comp_type = comp["node"].get("type", "unknown")
            if solid and comp_id:
                stl_path = f"outputs/{comp_id}.stl"
                glb_path = f"outputs/{comp_id}.glb"
                try:
                    # Step 1: export to STL via CadQuery
                    cq.exporters.export(solid, stl_path)
                    # Step 2: load with trimesh and simplify (optional, fail-safe)
                    mesh = trimesh.load(stl_path, force='mesh')
                    try:
                        mesh = mesh.simplify_quadratic_decimation(50000)
                    except Exception:
                        pass  # Simplification unavailable, skip gracefully
                    # Step 3: export as GLB
                    glb_data = tgltf.export_glb(trimesh.Scene([mesh]))
                    with open(glb_path, "wb") as f:
                        f.write(glb_data)
                    glb_paths[comp_id] = {"path": glb_path, "type": comp_type}
                    log("system", f"Exported {glb_path}")
                except Exception as e:
                    log("error", f"Failed to export GLB for {comp_id}: {e}")

        # ------------------------------------------------------------------
        # Phase 3.5: Housing Generation
        # ------------------------------------------------------------------
        from assembly.housing_generator import generate_housing
        generate_housing(master_assembly)
        glb_paths["housing"] = {"path": "outputs/housing.glb", "type": "housing"}

        # ------------------------------------------------------------------
        # Phase 4: Data Intercept & Cloud Trace
        # ------------------------------------------------------------------
        log("system", "Operation fulfilled completely. Piping operational matrices into isolated telemetry stream.")
        log_success(prompt_text, plan_graph, score)

        return {
            "status": "success",
            "metadata": metadata,
            "components": plan_graph,
            "relationships": ai_relationships,
            "glb_paths": glb_paths
        }

    except MissingParametersError as mpe:
        log("planner", f"Missing parameters: {mpe.missing_fields} for intent: {mpe.intent}")
        return {
            "status": "missing_parameters",
            "intent": mpe.intent,
            "missing_fields": mpe.missing_fields
        }

    except Exception as e:
        log("error", f"System Process Trap Invoked: {str(e)}")
        log("system", "Forwarding failure bounds explicitly up diagnostic backend channel.")
        log_failure(prompt_text, str(e))
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == "__main__":
    print("\nWelcome to the Agentic CAD Intelligence Platform.")
    print("Example robust prompts:")
    print(" -> 'Create a shaft of length 50mm and a module 2 gear mounted to it'")
    print(" -> 'I need a generic bolt'")
    print(" -> 'Design a 4:1 gearbox at 1500 RPM with 10 Nm'")

    try:
        user_input = input(">> ").strip()
    except EOFError:
        user_input = ""

    if not user_input:
        user_input = "Create a shaft of length 75.5mm and a module 2 gear mounted to it"
        print(f"(No active user terminal standard input detected. Utilizing automated agent cascade: '{user_input}')")

    run_agentic_pipeline(user_input)
