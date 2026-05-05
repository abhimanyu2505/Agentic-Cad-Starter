import copy
import uuid
from typing import Tuple, List, Dict
from utils.logger import log

def enrich_components(components: List[Dict], relationships: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Mechanical Enricher: Upgrades geometric prototype plans to mechanically
    realistic assemblies by injecting missing shafts, bearings, and enforcing proportions.
    """
    enriched_components = copy.deepcopy(components)
    enriched_relationships = copy.deepcopy(relationships)
    
    # 1. Enforce Gear Proportions & Track Existing Mounts
    gear_ids = []
    shaft_ids = []
    gear_to_shaft_map = {}
    
    # Map components by ID for quick lookup
    comp_map = {c.get("id"): c for c in enriched_components if "id" in c}
    
    for comp in enriched_components:
        if "id" not in comp:
            comp["id"] = f"{comp.get('type', 'comp')}_{uuid.uuid4().hex[:6]}"
            comp_map[comp["id"]] = comp
            
        comp_type = comp.get("type")
        if comp_type == "gear":
            gear_ids.append(comp["id"])
            module = comp.get("module", 2.0)
            if "thickness" not in comp:
                comp["thickness"] = 10.0 * module
                log("enricher", f"Enforced standard thickness ({comp['thickness']}mm) on gear {comp['id']}")
            if "bore_diameter" not in comp:
                comp["bore_diameter"] = 5.0 * module
        elif comp_type == "shaft":
            shaft_ids.append(comp["id"])
            
    # Track which gears are already mounted to a shaft
    for rel in enriched_relationships:
        if rel.get("type") in ["concentric", "mount"]:
            from_id = rel.get("from_id")
            to_id = rel.get("to_id")
            if from_id in gear_ids and to_id in shaft_ids:
                gear_to_shaft_map[from_id] = to_id
            elif to_id in gear_ids and from_id in shaft_ids:
                gear_to_shaft_map[to_id] = from_id

    # 2. Inject Missing Shafts
    for gid in gear_ids:
        if gid not in gear_to_shaft_map:
            gear_comp = comp_map[gid]
            bore_dia = gear_comp.get("bore_diameter", 10.0)
            thickness = gear_comp.get("thickness", 20.0)
            
            shaft_dia = bore_dia - 0.05
            bearing_w = shaft_dia * 0.4
            # Length covers gear + 2 bearings + 5mm clearance on each side
            shaft_length = thickness + (bearing_w * 2) + 10.0
            
            new_shaft_id = f"auto_shaft_{uuid.uuid4().hex[:6]}"
            new_shaft = {
                "id": new_shaft_id,
                "type": "shaft",
                "diameter": shaft_dia,
                "length": shaft_length
            }
            enriched_components.append(new_shaft)
            shaft_ids.append(new_shaft_id)
            comp_map[new_shaft_id] = new_shaft
            
            # Mount gear to new shaft
            enriched_relationships.append({
                "type": "concentric",
                "from_id": gid,
                "to_id": new_shaft_id
            })
            log("enricher", f"Injected shaft '{new_shaft_id}' for orphan gear '{gid}'")

    # 3. Inject Bearings for All Shafts
    for sid in shaft_ids:
        shaft_comp = comp_map[sid]
        s_dia = shaft_comp.get("diameter", 20.0)
        s_len = shaft_comp.get("length", 100.0)
        
        b_inner = s_dia
        b_outer = s_dia * 1.8
        b_width = s_dia * 0.4
        
        # We place bearings at the extreme ends of the shaft
        offset_dist = (s_len / 2.0) - (b_width / 2.0)
        
        for idx, offset in enumerate([offset_dist, -offset_dist]):
            bearing_id = f"bearing_{sid}_{idx+1}"
            bearing_comp = {
                "id": bearing_id,
                "type": "bearing",
                "inner_diameter": b_inner,
                "outer_diameter": b_outer,
                "width": b_width
            }
            enriched_components.append(bearing_comp)
            
            # Mount bearing to shaft
            enriched_relationships.append({
                "type": "concentric",
                "from_id": bearing_id,
                "to_id": sid
            })
            enriched_relationships.append({
                "type": "offset",
                "from_id": bearing_id,
                "to_id": sid,
                "distance": offset
            })
            log("enricher", f"Injected bearing '{bearing_id}' on shaft '{sid}' at offset {offset}")

    return enriched_components, enriched_relationships
