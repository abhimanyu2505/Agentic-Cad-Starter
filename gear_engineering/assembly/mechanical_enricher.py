"""
mechanical_enricher.py
======================
Upgrades a raw component plan to a mechanically realistic assembly
by injecting shafts and bearings where needed.

GENERATION MODES
----------------
"minimal"  (default)
    Respect the user's intent exactly.
    Only enforce gear proportions (thickness, bore).
    Do NOT inject any shafts or bearings the user did not ask for.

"realistic"
    Full mechanical realism.
    Inject shafts for unmounted gears.
    Inject two bearings per shaft (at the shaft ends).
    Use this mode when the user explicitly asks for a "realistic" or
    "production-ready" assembly, or when the gearbox synthesizer is active.
"""

import copy
import uuid
from typing import Tuple, List, Dict
from utils.logger import log


def enrich_components(
    components: List[Dict],
    relationships: List[Dict],
    generation_mode: str = "minimal",
) -> Tuple[List[Dict], List[Dict]]:
    """
    Apply mechanical enrichment to a component/relationship plan.

    Parameters
    ----------
    components       : list of component dicts
    relationships    : list of relationship dicts
    generation_mode  : "minimal" (default) or "realistic"
    """
    enriched_components    = copy.deepcopy(components)
    enriched_relationships = copy.deepcopy(relationships)

    # ── Track existing component types ───────────────────────────────────────
    gear_ids:         list = []
    shaft_ids:        list = []
    gear_to_shaft_map: dict = {}

    comp_map = {c.get("id"): c for c in enriched_components if "id" in c}

    for comp in enriched_components:
        if "id" not in comp:
            comp["id"] = f"{comp.get('type', 'comp')}_{uuid.uuid4().hex[:6]}"
            comp_map[comp["id"]] = comp

        comp_type = comp.get("type")
        if comp_type == "gear":
            gear_ids.append(comp["id"])
            module = comp.get("module", 2.0)
            # Always enforce standard spur gear face width (safe in both modes).
            if "face_width" not in comp and "thickness" not in comp:
                comp["face_width"] = 8.0 * module
                log("enricher",
                    f"Enforced face_width ({comp['face_width']}mm) on '{comp['id']}'")
            if generation_mode == "realistic" and "bore_diameter" not in comp:
                comp["bore_diameter"] = 5.0 * module
        elif comp_type == "shaft":
            shaft_ids.append(comp["id"])

    # Track which gears are already mounted on a shaft
    for rel in enriched_relationships:
        if rel.get("type") in ("concentric", "mount"):
            fid = rel.get("from_id")
            tid = rel.get("to_id")
            if fid in gear_ids and tid in shaft_ids:
                gear_to_shaft_map[fid] = tid
            elif tid in gear_ids and fid in shaft_ids:
                gear_to_shaft_map[tid] = fid

    # ── MINIMAL MODE: stop here ──────────────────────────────────────────────
    if generation_mode != "realistic":
        log("enricher",
            f"Minimal mode: skipping shaft/bearing injection "
            f"({len(enriched_components)} components unchanged).")
        return enriched_components, enriched_relationships

    # ── REALISTIC MODE: inject shafts for unmounted gears ────────────────────
    log("enricher", "Realistic mode: injecting shafts and bearings.")

    for gid in gear_ids:
        if gid not in gear_to_shaft_map:
            gear_comp  = comp_map[gid]
            bore_dia   = gear_comp.get("bore_diameter", 10.0)
            thickness  = gear_comp.get("face_width", gear_comp.get("thickness", 16.0))

            shaft_dia  = bore_dia - 0.05
            bearing_w  = shaft_dia * 0.4
            shaft_length = thickness + (bearing_w * 2) + 10.0

            new_shaft_id = f"auto_shaft_{uuid.uuid4().hex[:6]}"
            new_shaft = {
                "id":       new_shaft_id,
                "type":     "shaft",
                "diameter": shaft_dia,
                "length":   shaft_length,
            }
            enriched_components.append(new_shaft)
            shaft_ids.append(new_shaft_id)
            comp_map[new_shaft_id] = new_shaft

            enriched_relationships.append({
                "type":    "concentric",
                "from_id": gid,
                "to_id":   new_shaft_id,
            })
            log("enricher",
                f"Injected shaft '{new_shaft_id}' for orphan gear '{gid}'")

    # ── REALISTIC MODE: inject 2 bearings per shaft ──────────────────────────
    for sid in shaft_ids:
        shaft_comp = comp_map[sid]
        s_dia = shaft_comp.get("diameter", 20.0)
        s_len = shaft_comp.get("length", 100.0)

        b_inner      = s_dia
        b_outer      = s_dia * 1.8
        b_width      = s_dia * 0.4
        offset_dist  = (s_len / 2.0) - (b_width / 2.0)

        for idx, offset in enumerate([offset_dist, -offset_dist]):
            bearing_id = f"bearing_{sid}_{idx + 1}"
            enriched_components.append({
                "id":             bearing_id,
                "type":           "bearing",
                "inner_diameter": b_inner,
                "outer_diameter": b_outer,
                "width":          b_width,
            })
            enriched_relationships.append({
                "type":    "concentric",
                "from_id": bearing_id,
                "to_id":   sid,
            })
            enriched_relationships.append({
                "type":     "offset",
                "from_id":  bearing_id,
                "to_id":    sid,
                "distance": offset,
            })
            log("enricher",
                f"Injected bearing '{bearing_id}' on '{sid}' at offset {offset:.1f}mm")

    return enriched_components, enriched_relationships
