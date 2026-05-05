from utils.logger import log
import core.parser.gear_parser as gear_parser
import core.parser.shaft_parser as shaft_parser
import core.parser.bolt_parser as bolt_parser
import core.parser.plate_parser as plate_parser
import core.parser.flange_parser as flange_parser

try:
    import cadquery as cq
    from components.gear.gear_cad import generate_component as generate_gear
    from components.shaft.shaft_cad import generate_component as generate_shaft
    from components.bolt.bolt_cad import generate_component as generate_bolt
    from components.plate.plate_cad import generate_component as generate_plate
    from components.flange.flange_cad import generate_component as generate_flange
    from components.bearing.bearing_cad import generate_component as generate_bearing
    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False

def route_node(node: dict, prompt_text: str) -> dict:
    comp_type = node.get("type", node.get("component"))
    params = {}
    solid = None
    
    if comp_type == "gear":
        if "module" in node:
            params = {k: v for k, v in node.items() if k not in ["type", "component", "mount_on"]}
        else:
            log("parser", "Falling back to legacy gear parser")
            params = gear_parser.parse_parameters(prompt_text)
        log("router", f"Locked gear scalars natively: {params}")
        if CADQUERY_AVAILABLE: solid = generate_gear(params)
        
    elif comp_type == "shaft":
        if "length" in node:
            params = {k: v for k, v in node.items() if k not in ["type", "component", "mount_on"]}
        else:
            log("parser", "Falling back to legacy shaft parser")
            params = shaft_parser.parse_parameters(prompt_text)
        log("router", f"Locked shaft scalars natively: {params}")
        if CADQUERY_AVAILABLE: solid = generate_shaft(params)
        
    elif comp_type == "bolt":
        if "diameter" in node:
            params = {k: v for k, v in node.items() if k not in ["type", "component", "mount_on"]}
        else:
            log("parser", "Falling back to legacy bolt parser")
            params = bolt_parser.parse_parameters(prompt_text)
        log("router", f"Locked fastener scalars natively: {params}")
        if CADQUERY_AVAILABLE: solid = generate_bolt(params)
        
    elif comp_type == "plate":
        if "length" in node:
            params = {k: v for k, v in node.items() if k not in ["type", "component", "mount_on"]}
        else:
            log("parser", "Falling back to legacy plate parser")
            params = plate_parser.parse_parameters(prompt_text)
        log("router", f"Locked plate scalars natively: {params}")
        if CADQUERY_AVAILABLE: solid = generate_plate(params)
        
    elif comp_type == "flange":
        if "diameter" in node:
            params = {k: v for k, v in node.items() if k not in ["type", "component", "mount_on"]}
        else:
            log("parser", "Falling back to legacy flange parser")
            params = flange_parser.parse_parameters(prompt_text)
        log("router", f"Locked flange scalars natively: {params}")
        if CADQUERY_AVAILABLE: solid = generate_flange(params)
        
    elif comp_type == "nut":
        if "diameter" in node:
            params = {k: v for k, v in node.items() if k not in ["type", "component", "mount_on"]}
        else:
            log("parser", "Falling back to legacy nut parser (not implemented)")
            params = {}
        log("router", f"Locked nut scalars natively: {params}")
        # Nut component missing in imports, add a mock if needed or just pass
        
    elif comp_type == "bearing":
        params = {k: v for k, v in node.items() if k not in ["type", "component", "mount_on"]}
        log("router", f"Locked bearing scalars natively: {params}")
        if CADQUERY_AVAILABLE: solid = generate_bearing(params)
        
    elif comp_type == "cone":
        log("router", f"Locked cone scalars natively: {node}")
        if CADQUERY_AVAILABLE:
            radius = node.get("diameter", 10) / 2
            height = node.get("height", 10)
            solid = cq.Workplane("XY").cone(height, radius, 0)
            
    elif comp_type == "cylinder":
        log("router", f"Locked cylinder scalars natively: {node}")
        if CADQUERY_AVAILABLE:
            if "diameter" in node:
                radius = node.get("diameter") / 2
            else:
                radius = node.get("radius", 5)
            height = node.get("height", 10)
            solid = cq.Workplane("XY").circle(radius).extrude(height)
            
    elif comp_type == "box":
        log("router", f"Locked box scalars natively: {node}")
        if CADQUERY_AVAILABLE:
            length = node.get("length", 10)
            width = node.get("width", 10)
            height = node.get("height", 10)
            solid = cq.Workplane("XY").box(length, width, height)
            
    elif comp_type == "sphere":
        log("router", f"Locked sphere scalars natively: {node}")
        if CADQUERY_AVAILABLE:
            radius = node.get("radius", node.get("diameter", 10) / 2)
            solid = cq.Workplane("XY").sphere(radius)

    else:
        log("router", f"Component type '{comp_type}' requested. No deterministic CAD generator registered yet.")
        params = {k: v for k, v in node.items() if k not in ["type", "component", "mount_on"]}
        
    node["extracted_parameters"] = params
    return {"node": node, "solid": solid}

def is_cadquery_available() -> bool:
    return CADQUERY_AVAILABLE
