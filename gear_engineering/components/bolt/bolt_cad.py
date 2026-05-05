import cadquery as cq

def generate_component(parameters: dict):
    """
    Standardized component generation interface for Fastener/Bolt CAD.
    Expects params: length, diameter.
    Generates: ISO proportions approximation (Hex head + cylindrical shaft).
    """
    length = parameters.get("length")
    diameter = parameters.get("diameter", 10.0)
    
    if length is None:
        raise ValueError("Critical Parameter Missing: Bolt requires length.")
        
    # ISO Approx parameters
    head_diameter_approx = diameter * 1.8
    head_height = diameter * 0.6
    
    print(f"[bolt_cad] Generating ISO-approx bolt: D={diameter:.2f}mm, L={length:.2f}mm")
    
    # Create the cylindrical shaft along +Z axis
    bolt = cq.Workplane("XY").circle(diameter / 2.0).extrude(length)
    
    # Sweep standard hex head at the origin facing away from shaft (into -Z)
    # The polygon(6, radius) creates a hexagon inscribed in circle of that radius
    hex_head = (
        cq.Workplane("XY")
        .workplane(offset=0) # start at bottom plan where shaft starts
        .polygon(6, head_diameter_approx)
        .extrude(-head_height) # Extrude downwards
    )
    
    # Union the geometries natively
    bolt_solid = bolt.union(hex_head)
    
    print("[bolt_cad] Bolt shaft and parametric hex union executed.")
    return bolt_solid
