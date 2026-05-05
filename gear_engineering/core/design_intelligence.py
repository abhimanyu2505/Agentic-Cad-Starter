"""
design_intelligence.py
======================
Mechanical feasibility validator for CAD plans.

Checks components, relationships, and synthesis metadata
and returns a list of engineering warning strings.
No geometry is modified here — this is a pure validation pass.
"""

import math
from typing import Dict, List, Tuple

from utils.logger import log


def validate_cad_plan(plan: Dict) -> Tuple[Dict, List[str]]:
    """
    Validate the mechanical feasibility of components in a CAD plan.

    Returns (plan, warnings) where warnings is a list of human-readable
    engineering alert strings. The plan is returned unchanged.
    """
    warnings: List[str] = []
    components = plan.get("components", [])
    flow_type = plan.get("metadata", {}).get("flow_type")
    is_gearbox_flow = flow_type == "gearbox" or bool(plan.get("metadata", {}).get("target_ratio"))

    for comp in components:
        comp_type = comp.get("type", "")

        if comp_type == "gear":
            teeth = comp.get("teeth", 0)
            if teeth < 12:
                warnings.append(
                    f"Gear Warning: {teeth} teeth is below the 12-tooth minimum. "
                    "Risk of undercutting."
                )

        elif comp_type == "shaft":
            length   = comp.get("length", 0)
            diameter = comp.get("diameter", 0)
            if diameter <= 0:
                warnings.append("Shaft Warning: Diameter must be greater than 0.")
                continue

            ld_ratio = length / diameter
            if ld_ratio > 20:
                warnings.append(
                    f"Shaft Warning: L/D ratio={ld_ratio:.1f} exceeds 20:1 — "
                    "high risk of deflection."
                )

            torque_nm = (
                comp.get("input_torque")
                or comp.get("output_torque_nm")
                or plan.get("metadata", {}).get("output_torque_nm", 0)
            )
            if torque_nm:
                d_m = diameter / 1000.0
                shear_mpa = (16.0 * float(torque_nm)) / (math.pi * d_m ** 3) / 1e6
                if shear_mpa > 50.0:
                    warnings.append(
                        f"Engineering Alert: {torque_nm:.1f} Nm on {diameter}mm shaft → "
                        f"shear stress {shear_mpa:.1f} MPa (limit 50 MPa). "
                        "Risk of shaft failure."
                    )

    # Role validation
    inputs  = [c for c in components if c.get("role") == "input"]
    outputs = [c for c in components if c.get("role") == "output"]

    if is_gearbox_flow and len(inputs) == 0:
        warnings.append(
            "System Warning: No 'input' component defined. "
            "Assembly is statically kinematic."
        )
    elif len(inputs) > 1:
        warnings.append(
            "System Warning: Multiple 'input' components — "
            "kinematic propagation may be ambiguous."
        )

    if is_gearbox_flow and len(outputs) == 0:
        warnings.append(
            "System Warning: No 'output' component defined."
        )

    # Mesh relationship validation
    relationships = plan.get("relationships", [])
    comp_map      = {c.get("id"): c for c in components if "id" in c}

    for rel in relationships:
        if rel.get("type") in ("mesh", "meshing"):
            c1 = comp_map.get(rel.get("from_id"))
            c2 = comp_map.get(rel.get("to_id"))
            if not c1 or not c2:
                continue
            if c1.get("type") != "gear" or c2.get("type") != "gear":
                warnings.append(
                    f"Mesh Warning: Cannot mesh '{rel.get('from_id')}' ↔ "
                    f"'{rel.get('to_id')}' — both must be gears."
                )
                continue
            m1, m2 = c1.get("module", 2.0), c2.get("module", 2.0)
            if abs(m1 - m2) > 0.001:
                warnings.append(
                    f"Mesh Warning: Incompatible modules M{m1} ↔ M{m2} — "
                    "gears will jam mechanically."
                )

    # Synthesis ratio accuracy check
    metadata       = plan.get("metadata", {})
    target_ratio   = metadata.get("target_ratio")
    ratio_error    = metadata.get("ratio_error_pct")

    if target_ratio is not None and ratio_error is not None:
        if ratio_error > 2.0:
            warnings.append(
                f"Ratio Accuracy Warning: achieved {metadata.get('actual_ratio'):.4f}:1 "
                f"vs target {target_ratio}:1 — error {ratio_error:.2f}%. "
                "Consider relaxing max_gear_teeth for a closer match."
            )
        else:
            log("intelligence",
                f"Synthesis OK — actual ratio {metadata.get('actual_ratio')}:1 "
                f"({ratio_error}% error), "
                f"output {metadata.get('output_speed_rpm')} RPM "
                f"@ {metadata.get('output_torque_nm')} Nm, "
                f"{metadata.get('num_stages')} stage(s).")

    if warnings:
        for w in warnings:
            log("intelligence", f"[WARNING] {w}")

    return plan, warnings
