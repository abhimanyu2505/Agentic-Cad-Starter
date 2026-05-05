"""
assembly_builder.py
===================
Constraint-based assembly layout engine.

Places components in 3D space using a topological dependency order
derived from the relationship graph.  Propagates kinematic state
(speed, torque, direction) through the assembly as constraints are applied.

All debug exports are written to outputs/ — never to the repo root.
"""

try:
    import cadquery as cq
except ImportError:
    pass

import json
import os
from utils.logger import log

# Ensure outputs directory is available for debug exports
_OUTPUTS_DIR = "outputs"


def resolve_dependency_order(components: list, relationships: list) -> list:
    """
    Build an adjacency list and perform a topological sort.
    Raises ValueError on circular dependencies.
    """
    comp_map = {
        c["node"].get("id", f"{c['node']['type']}_{i}"): c
        for i, c in enumerate(components)
    }
    graph = {cid: [] for cid in comp_map}

    for rel in relationships:
        from_id = rel.get("from_id")
        to_id   = rel.get("to_id")
        if from_id in graph and to_id in graph:
            graph[from_id].append(to_id)

    visited   = set()
    temp_mark = set()
    order     = []

    def visit(node_id: str) -> None:
        if node_id in temp_mark:
            raise ValueError(
                f"Circular dependency detected involving component '{node_id}'."
            )
        if node_id not in visited:
            temp_mark.add(node_id)
            for dep in graph[node_id]:
                visit(dep)
            temp_mark.remove(node_id)
            visited.add(node_id)
            order.append(node_id)

    for cid in comp_map:
        if cid not in visited:
            visit(cid)

    return [comp_map[cid] for cid in order]


def build_assembly(compiled_components: list, relationships: list = None):
    """
    Unify topological solids using a constraint-based dependency solver.
    Falls back to legacy deterministic stacking when no relationships are provided.
    """
    os.makedirs(_OUTPUTS_DIR, exist_ok=True)
    asm = cq.Assembly()
    log("assembler",
        f"Initialising constraint-based layout engine for "
        f"{len(compiled_components)} component(s)...")

    if not relationships:
        log("assembler",
            "No relationships — falling back to legacy sequential stacking.")
        return _build_assembly_legacy(compiled_components, asm)

    try:
        ordered_comps = resolve_dependency_order(compiled_components, relationships)
    except ValueError as exc:
        log("error", str(exc))
        log("assembler", "Graph resolution failed — falling back to legacy layout.")
        return _build_assembly_legacy(compiled_components, asm)

    # State tracking
    placed_states:    dict = {}  # id → {loc, bb}
    kinematic_graph:  dict = {}  # id → {speed_rpm, torque, direction, ...}
    mesh_detected:    bool = False

    # Build from_id → [relationships] lookup for O(1) access
    rel_map: dict = {}
    for rel in relationships:
        from_id = rel.get("from_id")
        if from_id not in rel_map:
            rel_map[from_id] = []
        rel_map[from_id].append(rel)

    # Build id → node lookup for attribute access during constraint application
    node_map = {
        c["node"].get("id", f"{c['node']['type']}_{i}"): c["node"]
        for i, c in enumerate(compiled_components)
    }

    # Component colour map
    _COLOURS = {
        "gear":     "red",
        "shaft":    "blue",
        "bolt":     "gray",
        "plate":    "green",
        "flange":   "yellow",
        "bearing":  "orange",
        "coupling": "orange",
    }

    def _rel_priority(r: dict) -> int:
        t = r.get("type", "")
        return {"concentric": 0, "mesh": 1, "meshing": 1, "flush": 2, "offset": 3}.get(t, 4)

    for comp in ordered_comps:
        node      = comp["node"]
        solid     = comp["solid"]
        comp_type = node.get("type", "unknown")
        cid       = node.get("id", f"{comp_type}_{id(node)}")

        if solid is None:
            log("assembler", f"Component '{cid}' has no geometry — skipping placement.")
            placed_states[cid] = {"loc": cq.Location(), "bb": None}
            continue

        color = cq.Color(_COLOURS.get(comp_type, "gray"))

        # Initialise kinematic entry
        if cid not in kinematic_graph:
            role   = node.get("role")
            speed  = float(node.get("input_speed_rpm", 0.0)) if role == "input" else 0.0
            torque = float(node.get("input_torque", 1.0))    if role == "input" else 0.0
            if role == "input" and torque == 0.0:
                torque = 1.0
            kinematic_graph[cid] = {
                "speed_rpm":  speed,
                "torque":     torque,
                "role":       role,
                "direction":  1,
                "driven_by":  None,
                "drives":     [],
            }

        target_x, target_y, target_z = 0.0, 0.0, 0.0

        # Apply constraints in priority order
        comps_rels = sorted(rel_map.get(cid, []), key=_rel_priority)

        for rel in comps_rels:
            to_id    = rel.get("to_id")
            rel_type = rel.get("type")
            val      = rel.get("value", rel.get("distance", 0.0))

            target_state = placed_states.get(to_id)
            target_node  = node_map.get(to_id, {})

            if not target_state or not target_state["bb"]:
                log("assembler",
                    f"Cannot apply [{rel_type}] {cid}→{to_id}: "
                    f"'{to_id}' has no placed geometry yet.")
                continue

            t_bb  = target_state["bb"]
            t_loc = target_state["loc"]
            t_x, t_y, t_z = t_loc.toTuple()[0]

            if rel_type == "concentric":
                target_x, target_y = t_x, t_y
                log("assembler", f"[Concentric] {cid} → centre of {to_id}")

                # Ensure target has a kinematic entry
                if to_id not in kinematic_graph:
                    t_role = target_node.get("role")
                    kinematic_graph[to_id] = {
                        "speed_rpm": float(target_node.get("input_speed_rpm", 0.0))
                                     if t_role == "input" else 0.0,
                        "torque":    float(target_node.get("input_torque", 1.0))
                                     if t_role == "input" else 0.0,
                        "role":      t_role, "direction": 1,
                        "driven_by": None, "drives": [],
                    }

                if kinematic_graph[cid]["driven_by"] not in (None, to_id):
                    log("assembler",
                        f"[WARNING] Single-driver constraint violated for '{cid}' — skipping.")
                    continue

                kinematic_graph[cid].update({
                    "driven_by": to_id,
                    "speed_rpm": kinematic_graph[to_id]["speed_rpm"],
                    "torque":    kinematic_graph[to_id]["torque"],
                    "direction": kinematic_graph[to_id]["direction"],
                })
                kinematic_graph[to_id]["drives"].append(cid)

            elif rel_type in ("mesh", "meshing"):
                mesh_detected = True
                m    = node.get("module", 2.0)
                z1   = node.get("teeth", 20)
                z2   = target_node.get("teeth", 20)
                cd   = ((m * z1) + (m * z2)) / 2.0 + 0.1  # centre distance + clearance
                target_x = t_x + cd
                target_y = t_y
                target_z = t_z

                ratio = z2 / z1 if z1 > 0 else 0.0
                log("assembler",
                    f"[Mesh] {cid} ↔ {to_id}: centre distance={cd:.2f}mm, ratio={ratio:.3f}")

                if to_id not in kinematic_graph:
                    t_role = target_node.get("role")
                    kinematic_graph[to_id] = {
                        "speed_rpm": float(target_node.get("input_speed_rpm", 0.0))
                                     if t_role == "input" else 0.0,
                        "torque":    float(target_node.get("input_torque", 1.0))
                                     if t_role == "input" else 0.0,
                        "role":      t_role, "direction": 1,
                        "driven_by": None, "drives": [],
                    }

                kinematic_graph[cid].update({
                    "driven_by": to_id,
                    "speed_rpm": kinematic_graph[to_id]["speed_rpm"] * ratio,
                    "torque":    kinematic_graph[to_id]["torque"] * (1 / ratio if ratio > 0 else 0) * 0.98,
                    "direction": kinematic_graph[to_id]["direction"] * -1,
                })
                kinematic_graph[to_id]["drives"].append(cid)

            elif rel_type == "flush":
                target_z = t_bb.zmax
                log("assembler", f"[Flush] {cid} stacked on {to_id} at Z={target_z:.2f}")

            elif rel_type in ("offset", "distance"):
                target_z = t_bb.zmax + float(val)
                log("assembler",
                    f"[Offset] {cid} offset {val}mm from {to_id} (Z={target_z:.2f})")

            elif rel_type == "alignment":
                target_z = t_z + float(val)
                log("assembler",
                    f"[Alignment] {cid} aligned to {to_id} origin + {val}mm")

            elif rel_type in ("mount", "fasten"):
                target_x, target_y, target_z = t_x, t_y, t_bb.zmax
                log("assembler", f"[{rel_type.capitalize()}] {cid} anchored to {to_id}")

        loc = cq.Location(cq.Vector(target_x, target_y, target_z))

        # Bounding-box collision check
        located_solid = solid.val().located(loc)
        new_bb        = located_solid.BoundingBox()

        for p_id, p_state in placed_states.items():
            if not p_state["bb"]:
                continue
            p_bb = p_state["bb"]
            overlap = not (
                new_bb.xmax < p_bb.xmin or new_bb.xmin > p_bb.xmax or
                new_bb.ymax < p_bb.ymin or new_bb.ymin > p_bb.ymax or
                new_bb.zmax < p_bb.zmin or new_bb.zmin > p_bb.zmax
            )
            if overlap:
                is_intentional = any(r.get("to_id") == p_id for r in comps_rels)
                if is_intentional:
                    log("assembler",
                        f"[BOUNDS] Intentional overlap: {cid} ↔ {p_id} (constraint-driven).")
                else:
                    log("assembler",
                        f"[WARNING] Collision: {cid} intersects {p_id} (unintentional).")

        placed_states[cid] = {"loc": loc, "bb": new_bb}
        asm.add(solid, name=cid, color=color, loc=loc)

        # Per-component debug STEP (written to outputs/)
        try:
            cq.exporters.export(solid, f"{_OUTPUTS_DIR}/debug_{comp_type}.step")
        except Exception:
            pass

    # Gear train debug export
    if mesh_detected:
        try:
            asm.save(f"{_OUTPUTS_DIR}/debug_gear_train.step")
            log("assembler", f"Exported {_OUTPUTS_DIR}/debug_gear_train.step")
        except Exception:
            pass

    # Kinematic summary
    input_nodes  = [cid for cid, k in kinematic_graph.items() if k["role"] == "input"]
    output_nodes = [cid for cid, k in kinematic_graph.items() if k["role"] == "output"]

    if input_nodes and output_nodes:
        in_k  = kinematic_graph[input_nodes[0]]
        out_k = kinematic_graph[output_nodes[0]]

        if out_k["speed_rpm"] == 0.0:
            log("kinematics",
                f"Kinematic fault: output node '{output_nodes[0]}' is disconnected.")
        else:
            total_ratio = (in_k["speed_rpm"] / out_k["speed_rpm"]
                           if out_k["speed_rpm"] != 0 else 0)
            log("kinematics", "=" * 40)
            log("kinematics", "TRANSMISSION SUMMARY")
            log("kinematics", "=" * 40)
            log("kinematics",
                f"Input  ({input_nodes[0]}): "
                f"{in_k['speed_rpm']:.1f} RPM @ {in_k['torque']:.2f} Nm")
            log("kinematics",
                f"Output ({output_nodes[0]}): "
                f"{out_k['speed_rpm']:.1f} RPM @ {out_k['torque']:.2f} Nm")
            log("kinematics", f"Total ratio: {total_ratio:.3f}:1")

    # Persist kinematic graph
    try:
        with open(f"{_OUTPUTS_DIR}/kinematic_graph.json", "w") as f:
            json.dump(kinematic_graph, f, indent=2)
        log("kinematics", f"Kinematic graph saved to {_OUTPUTS_DIR}/kinematic_graph.json")
    except Exception:
        pass

    # Final assembly debug export
    try:
        asm.save(f"{_OUTPUTS_DIR}/debug_final_assembly.step")
        log("assembler", f"Exported {_OUTPUTS_DIR}/debug_final_assembly.step")
    except Exception:
        pass

    return asm


def _build_assembly_legacy(compiled_components: list, asm: cq.Assembly):
    """
    Original hardcoded Z-stacking logic for backward compatibility.
    Used when no relationship graph is available.
    """
    os.makedirs(_OUTPUTS_DIR, exist_ok=True)

    flange_idx = next(
        (i for i, c in enumerate(compiled_components)
         if c["node"].get("type", c["node"].get("component")) == "flange"), None
    )
    plate_idx = next(
        (i for i, c in enumerate(compiled_components)
         if c["node"].get("type", c["node"].get("component")) == "plate"), None
    )
    assembly_has_flange_plate = (flange_idx is not None and plate_idx is not None)

    current_z_offset = 0.0
    placed_components = []

    _COLOURS = {
        "gear": "red", "shaft": "blue", "bolt": "gray",
        "plate": "green", "flange": "yellow",
    }

    for idx, comp in enumerate(compiled_components):
        node           = comp["node"]
        solid          = comp["solid"]
        component_type = node.get("type", node.get("component"))

        if solid is None:
            continue

        color    = cq.Color(_COLOURS.get(component_type, "gray"))
        name     = f"{component_type}_{idx}"
        target_z = current_z_offset
        relation = node.get("mount_on")

        if relation == "shaft" and component_type == "gear":
            shaft_node = next(
                (n for n in compiled_components
                 if n["node"].get("type", n["node"].get("component")) == "shaft"), None
            )
            if shaft_node:
                shaft_len  = shaft_node["node"]["extracted_parameters"].get("length", 100.0)
                gear_thick = node["extracted_parameters"].get("thickness", 10.0)
                target_z   = max(shaft_len - gear_thick - 5.0, 5.0)

        elif component_type == "plate" and assembly_has_flange_plate:
            target_z = 0.0
        elif component_type == "flange" and assembly_has_flange_plate:
            plate_node = compiled_components[plate_idx]["node"]
            target_z   = plate_node["extracted_parameters"].get("thickness", 5.0)

        loc = cq.Location(cq.Vector(0, 0, target_z))
        located_solid = solid.val().located(loc)
        new_bb        = located_solid.BoundingBox()
        placed_components.append((name, new_bb))
        asm.add(solid, name=name, color=color, loc=loc)

        # Auto-fasteners for flange+plate assemblies
        if component_type == "flange" and assembly_has_flange_plate:
            try:
                from components.bolt.bolt_cad import generate_component as generate_bolt
                from components.nut.nut_cad   import generate_component as generate_nut
                import math

                hole_rad   = node["extracted_parameters"].get("hole_radius", 5.0)
                flange_t   = node["extracted_parameters"].get("thickness", 20.0)
                plate_t    = compiled_components[plate_idx]["node"][
                    "extracted_parameters"
                ].get("thickness", 5.0)

                bolt_dia    = (hole_rad * 2.0) * 0.9
                bolt_params = {"diameter": bolt_dia, "length": plate_t + flange_t + 3.0}
                auto_bolt   = generate_bolt(bolt_params)
                auto_nut    = generate_nut({"diameter": bolt_dia})

                hole_count = node["extracted_parameters"].get("hole_count", 6)
                pcd_rad    = node["extracted_parameters"].get("pcd_diameter", 70.0) / 2.0
                angle_step = 2 * math.pi / hole_count
                recess     = 0.5 * (bolt_dia * 0.6)

                for b_idx in range(hole_count):
                    angle   = b_idx * angle_step
                    bx, by  = pcd_rad * math.cos(angle), pcd_rad * math.sin(angle)
                    bolt_z  = (plate_t + flange_t) - recess
                    bolt_loc = cq.Location(
                        cq.Vector(bx, by, bolt_z), cq.Vector(1, 0, 0), 180
                    )
                    asm.add(auto_bolt, name=f"auto_bolt_{b_idx}",
                            color=cq.Color("gray"), loc=bolt_loc)
                    asm.add(auto_nut, name=f"auto_nut_{b_idx}",
                            color=cq.Color("gray"),
                            loc=cq.Location(cq.Vector(bx, by, 0.0)))
            except Exception as e:
                log("error", f"Auto-fastener generation failed: {e}")

        if not relation and not assembly_has_flange_plate:
            current_z_offset += 25.0

    try:
        asm.save(f"{_OUTPUTS_DIR}/debug_final_assembly.step")
        log("assembler", f"Exported {_OUTPUTS_DIR}/debug_final_assembly.step")
    except Exception:
        pass

    return asm
