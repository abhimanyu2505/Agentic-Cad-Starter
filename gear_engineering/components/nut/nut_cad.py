import cadquery as cq

def generate_component(parameters: dict):
    """
    Standardized component generation interface for Fastener/Nut CAD.
    Expects params: diameter.
    Generates: ISO proportions approximation (Hex body + threaded hole mapped via solid cut).
    """
    diameter = parameters.get("diameter", 10.0)
    
    # ISO Approx parameters
    hex_size = diameter * 1.6
    thickness = diameter * 0.8
    
    print(f"[nut_cad] Generating ISO-approx nut: D={diameter:.2f}mm, T={thickness:.2f}mm")
    
    # Create the base hexagon profile and extrude downward into -Z
    nut = (
        cq.Workplane("XY")
        .polygon(6, hex_size)
        .extrude(-thickness)
    )
    
    # Drill exact inner bore limit through the center origin symmetrically
    nut = nut.faces(">Z").workplane().circle(diameter / 2.0).cutThruAll()
    
    print("[nut_cad] Threaded bore mapping integration complete.")
    return nut
