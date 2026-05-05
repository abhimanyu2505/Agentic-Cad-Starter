try:
    import cadquery as cq
except ImportError:
    pass

from utils.logger import log

def resolve_dependency_order(components: list, relationships: list) -> list:
    """
    Builds an adjacency list and performs a topological sort.
    Detects circular dependencies.
    """
    comp_map = {c["node"].get("id", f"{c['node']['type']}_{i}"): c for i, c in enumerate(components)}
    
    # Adjacency list for dependencies (A depends on B -> graph[A] = [B])
    graph = {cid: [] for cid in comp_map}
    
    for rel in relationships:
        from_id = rel.get("from_id")
        to_id = rel.get("to_id")
        if from_id in graph and to_id in graph:
            graph[from_id].append(to_id)
            
    visited = set()
    temp_mark = set()
    order = []
    
    def visit(node_id):
        if node_id in temp_mark:
            raise ValueError(f"Circular dependency detected involving component '{node_id}'!")
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
            
    # Return ordered components
    return [comp_map[cid] for cid in order]

def build_assembly(compiled_components: list, relationships: list = None):
    """
    Unifies topological solids utilizing a constraint-based dependency solver.
    Falls back to legacy deterministic stacking if no relationships are provided.
    """
    asm = cq.Assembly()
    log("assembler", f"Initializing constraint-based layout engine for {len(compiled_components)} objects...")
    
    if not relationships:
        log("assembler", "No explicit AI relationships detected. Falling back to legacy hardcoded heuristics.")
        return _build_assembly_legacy(compiled_components, asm)

    try:
        ordered_comps = resolve_dependency_order(compiled_components, relationships)
    except ValueError as e:
        log("error", str(e))
        log("assembler", "Graph resolution failed. Falling back to legacy layout.")
        return _build_assembly_legacy(compiled_components, asm)

    # State tracking
    placed_states = {} # id -> {"loc": cq.Location, "bb": BoundingBox}
    kinematic_graph = {} # id -> {"speed_ratio": float, "direction": int, "driven_by": str, "drives": list}
    
    # Pre-calculate mapping for fast lookup
    rel_map = {} # from_id -> list of relationships
    for rel in relationships:
        from_id = rel.get("from_id")
        if from_id not in rel_map:
            rel_map[from_id] = []
        rel_map[from_id].append(rel)

    for comp in ordered_comps:
        node = comp["node"]
        solid = comp["solid"]
        comp_type = node.get("type", "unknown")
        # Ensure ID exists even if legacy
        cid = node.get("id", f"{comp_type}_{id(node)}")
        
        if solid is None:
            log("assembler", f"Component {cid} generated null geometry. Skipping.")
            placed_states[cid] = {"loc": cq.Location(), "bb": None}
            continue
            
        color = cq.Color("gray")
        if comp_type == "gear": color = cq.Color("red")
        elif comp_type == "shaft": color = cq.Color("blue")
        elif comp_type == "bolt": color = cq.Color("gray")
        elif comp_type == "plate": color = cq.Color("green")
        elif comp_type == "flange": color = cq.Color("yellow")
        elif comp_type in ["bearing", "coupling"]: color = cq.Color("orange")
        
        target_x, target_y, target_z = 0.0, 0.0, 0.0
        
        if cid not in kinematic_graph:
            role = node.get("role")
            speed = float(node.get("input_speed_rpm", 0.0)) if role == "input" else 0.0
            torque = float(node.get("input_torque", 1.0)) if role == "input" else 0.0
            if role == "input" and torque == 0.0: torque = 1.0
            kinematic_graph[cid] = {"speed_rpm": speed, "torque": torque, "role": role, "direction": 1, "driven_by": None, "drives": []}
        
        # Apply Constraints (Order matters: Concentric -> Flush -> Offset)
        comps_rels = rel_map.get(cid, [])
        
        # Map nodes for attribute lookup
        node_map = {c["node"].get("id", f"{c['node']['type']}_{i}"): c["node"] for i, c in enumerate(compiled_components)}
        mesh_detected = False
        
        # Sort relationships to enforce priority
        def rel_priority(r):
            t = r.get("type", "")
            if t == "concentric": return 0
            if t == "mesh": return 1
            if t == "flush": return 2
            if t == "offset": return 3
            return 4
            
        comps_rels.sort(key=rel_priority)
        
        for rel in comps_rels:
            to_id = rel.get("to_id")
            rel_type = rel.get("type")
            val = rel.get("value", rel.get("distance", 0.0))  # fallback to legacy distance
            
            target_state = placed_states.get(to_id)
            target_node = node_map.get(to_id, {})
            
            if not target_state or not target_state["bb"]:
                log("WARNING", f"Cannot apply {rel_type} to {cid} -> {to_id} because {to_id} has no geometry.")
                continue
                
            t_bb = target_state["bb"]
            t_loc = target_state["loc"]
            t_x, t_y, t_z = t_loc.toTuple()[0]
            
            if rel_type == "concentric":
                target_x, target_y = t_x, t_y
                log("assembler", f"Constraint [Concentric]: {cid} aligned to center of {to_id}")
                
                # Kinematic Propagation
                if to_id not in kinematic_graph:
                    t_role = target_node.get("role")
                    kinematic_graph[to_id] = {
                        "speed_rpm": float(target_node.get("input_speed_rpm", 0.0)) if t_role == "input" else 0.0,
                        "torque": float(target_node.get("input_torque", 1.0)) if t_role == "input" else 0.0,
                        "role": t_role, "direction": 1, "driven_by": None, "drives": []
                    }
                
                if kinematic_graph[cid]["driven_by"] not in [None, to_id]:
                    raise ValueError(f"Single-driver constraint violated for {cid}")
                
                kinematic_graph[cid].update({
                    "driven_by": to_id,
                    "speed_rpm": kinematic_graph[to_id]["speed_rpm"],
                    "torque": kinematic_graph[to_id]["torque"],
                    "direction": kinematic_graph[to_id]["direction"]
                })
                kinematic_graph[to_id]["drives"].append(cid)
                
            elif rel_type == "mesh":
                m = node.get("module", 2.0)
                center_dist = ((m * node.get("teeth", 20)) + (m * target_node.get("teeth", 20))) / 2.0 + 0.1
                
                target_x = t_x + center_dist
                target_y = t_y
                target_z = t_z
                
                ratio = target_node.get("teeth", 20) / node.get("teeth", 20) if node.get("teeth", 20) > 0 else 0
                log("assembler", f"Constraint [Mesh]: {cid} meshes with {to_id} at center distance {center_dist:.2f}mm.")
                
                if to_id not in kinematic_graph:
                    t_role = target_node.get("role")
                    kinematic_graph[to_id] = {
                        "speed_rpm": float(target_node.get("input_speed_rpm", 0.0)) if t_role == "input" else 0.0,
                        "torque": float(target_node.get("input_torque", 1.0)) if t_role == "input" else 0.0,
                        "role": t_role, "direction": 1, "driven_by": None, "drives": []
                    }
                
                kinematic_graph[cid].update({
                    "driven_by": to_id,
                    "speed_rpm": kinematic_graph[to_id]["speed_rpm"] * ratio,
                    "torque": kinematic_graph[to_id]["torque"] * (1/ratio if ratio > 0 else 0) * 0.98,
                    "direction": kinematic_graph[to_id]["direction"] * -1
                })
                kinematic_graph[to_id]["drives"].append(cid)
                
            elif rel_type == "flush":
                target_z = t_bb.zmax
                log("assembler", f"Constraint [Flush]: {cid} stacked on {to_id} at Z={target_z:.2f}")
                
            elif rel_type in ["offset", "distance"]:
                target_z = t_bb.zmax + float(val)
                log("assembler", f"Constraint [{rel_type}]: {cid} offset by {val}mm from {to_id} (Z={target_z:.2f})")
                
            elif rel_type == "alignment":
                target_z = t_z + float(val)
                log("assembler", f"Constraint [Alignment]: {cid} aligned to origin of {to_id} + {val}mm")
                
            elif rel_type in ["mount", "fasten"]:
                target_x, target_y, target_z = t_x, t_y, t_bb.zmax
                log("assembler", f"Constraint [{rel_type.capitalize()}]: {cid} anchored generically to {to_id}")

        loc = cq.Location(cq.Vector(target_x, target_y, target_z))
        
        # Prevent Bounding Box overlap (simple collision warning)
        located_solid = solid.val().located(loc)
        new_bb = located_solid.BoundingBox()
        
        for p_id, p_state in placed_states.items():
            if not p_state["bb"]: continue
            placed_bb = p_state["bb"]
            
            if not (new_bb.xmax < placed_bb.xmin or new_bb.xmin > placed_bb.xmax or
                    new_bb.ymax < placed_bb.ymin or new_bb.ymin > placed_bb.ymax or
                    new_bb.zmax < placed_bb.zmin or new_bb.zmin > placed_bb.zmax):
                
                # If they share a relationship, intersection might be intentional (e.g. shafts in holes)
                # Check if p_id is in comps_rels
                is_intentional = any(r.get("to_id") == p_id for r in comps_rels)
                if is_intentional:
                    log("assembler", f"BOUNDS VALIDATION: Intentional constraint bounding overlap between {cid} -> {p_id}.")
                else:
                    log("WARNING", f"COLLISION: Arbitrary intersection between {cid} and {p_id} detected via bounding box!")
                    
        placed_states[cid] = {"loc": loc, "bb": new_bb}
        asm.add(solid, name=cid, color=color, loc=loc)
        
        # Save individual debug step
        cq.exporters.export(solid, f"debug_{comp_type}.step")

    if mesh_detected:
        asm.save("debug_gear_train.step")
        log("assembler", "Exported debug_gear_train.step for verification.")
        
    # Validation & Summary
    input_nodes = [cid for cid, k in kinematic_graph.items() if k["role"] == "input"]
    output_nodes = [cid for cid, k in kinematic_graph.items() if k["role"] == "output"]
    
    if input_nodes and output_nodes:
        in_node = input_nodes[0]
        out_node = output_nodes[0]
        in_k = kinematic_graph[in_node]
        out_k = kinematic_graph[out_node]
        
        if out_k["speed_rpm"] == 0.0:
            log("error", f"Kinematic Fault: Output node {out_node} is completely disconnected from input power source.")
        else:
            total_ratio = in_k["speed_rpm"] / out_k["speed_rpm"] if out_k["speed_rpm"] != 0 else 0
            log("kinematics", "="*40)
            log("kinematics", "TRANSMISSION SUMMARY")
            log("kinematics", "="*40)
            log("kinematics", f"Input ({in_node}):  {in_k['speed_rpm']:.1f} RPM @ {in_k['torque']:.2f} Nm")
            log("kinematics", f"Output ({out_node}): {out_k['speed_rpm']:.1f} RPM @ {out_k['torque']:.2f} Nm")
            log("kinematics", f"Total Gear Ratio: {total_ratio:.3f}:1")
            log("kinematics", "="*40)
        
    import json
    with open("kinematic_graph.json", "w") as f:
        json.dump(kinematic_graph, f, indent=2)
    log("kinematics", "Serialized full kinematic graph to kinematic_graph.json")

    log("assembler", "Unified constraint graph collapsed. B-Rep cleanly serialized.")
    asm.save("debug_final_assembly.step")
    return asm

def _build_assembly_legacy(compiled_components: list, asm: cq.Assembly):
    """
    The original hardcoded logic for backward compatibility.
    """
    flange_idx = next((i for i, c in enumerate(compiled_components) if c["node"].get("type", c["node"].get("component")) == "flange"), None)
    plate_idx = next((i for i, c in enumerate(compiled_components) if c["node"].get("type", c["node"].get("component")) == "plate"), None)
    
    assembly_has_flange_plate = (flange_idx is not None and plate_idx is not None)
    
    current_z_offset = 0.0
    placed_components = []
    
    for idx, comp in enumerate(compiled_components):
        node = comp["node"]
        solid = comp["solid"]
        component_type = node.get("type", node.get("component"))
        
        if solid is None: continue
            
        color = cq.Color("gray")
        if component_type == "gear": color = cq.Color("red")
        elif component_type == "shaft": color = cq.Color("blue")
        elif component_type == "bolt": color = cq.Color("gray")
        elif component_type == "plate": color = cq.Color("green")
        elif component_type == "flange": color = cq.Color("yellow")
            
        name = f"{component_type}_{idx}"
        target_z = current_z_offset
        relation = node.get("mount_on")
        
        if relation == "shaft" and component_type == "gear":
            shaft_node = next((n for n in compiled_components if n["node"].get("type", n["node"].get("component")) == "shaft"), None)
            if shaft_node:
                shaft_len  = shaft_node["node"]["extracted_parameters"].get("length", 100.0)
                gear_thick = node["extracted_parameters"].get("thickness", 10.0)
                target_z = shaft_len - gear_thick - 5.0
                target_z = max(target_z, 5.0)
            
        elif component_type == "plate" and assembly_has_flange_plate:
            target_z = 0.0
            
        elif component_type == "flange" and assembly_has_flange_plate:
            plate_node = compiled_components[plate_idx]["node"]
            target_z = plate_node["extracted_parameters"].get("thickness", 5.0)
            
        loc = cq.Location(cq.Vector(0, 0, target_z))
        
        located_solid = solid.val().located(loc)
        new_bb = located_solid.BoundingBox()
        placed_components.append((name, new_bb))
        asm.add(solid, name=name, color=color, loc=loc)
        
        if component_type == "flange" and assembly_has_flange_plate:
            try:
                from components.bolt.bolt_cad import generate_component as generate_bolt
                from components.nut.nut_cad import generate_component as generate_nut
                import math
                
                hole_rad = node["extracted_parameters"].get("hole_radius", 5.0)
                flange_thick = node["extracted_parameters"].get("thickness", 20.0)
                plate_thick = compiled_components[plate_idx]["node"]["extracted_parameters"].get("thickness", 5.0)
                
                bolt_dia = (hole_rad * 2.0) * 0.9
                bolt_params = {"diameter": bolt_dia, "length": plate_thick + flange_thick + 3.0}
                auto_bolt = generate_bolt(bolt_params)
                auto_nut = generate_nut({"diameter": bolt_dia})
                
                hole_count = node["extracted_parameters"].get("hole_count", 6)
                pcd_rad = node["extracted_parameters"].get("pcd_diameter", 70.0) / 2.0
                angle_step = 2 * math.pi / hole_count
                recess_depth = 0.5 * (bolt_dia * 0.6)
                
                for b_idx in range(hole_count):
                    angle = b_idx * angle_step
                    bx, by = pcd_rad * math.cos(angle), pcd_rad * math.sin(angle)
                    
                    bolt_z = (plate_thick + flange_thick) - recess_depth
                    bolt_loc = cq.Location(cq.Vector(bx, by, bolt_z), cq.Vector(1, 0, 0), 180)
                    asm.add(auto_bolt, name=f"auto_bolt_{b_idx}", color=cq.Color("gray"), loc=bolt_loc)
                    
                    nut_loc = cq.Location(cq.Vector(bx, by, 0.0))
                    asm.add(auto_nut, name=f"auto_nut_{b_idx}", color=cq.Color("gray"), loc=nut_loc)
            except Exception as e:
                log("error", f"Auto-fastener error: {e}")
                
        if not relation and not assembly_has_flange_plate:
            current_z_offset += 25.0 
            
    asm.save("debug_final_assembly.step")
    return asm
