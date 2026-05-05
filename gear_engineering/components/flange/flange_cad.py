import cadquery as cq

def generate_component(parameters: dict):
    """
    Standardized component generation interface for Flange CAD.
    Expects params: diameter, thickness
    Extracts derived parameters (bore_diameter).
    Generates: A circular flange with an inner bore and a 6-bolt radial hole pattern.
    """
    diameter = parameters.get("diameter", 100.0)
    thickness = parameters.get("thickness", 20.0)
    bore_diameter = parameters.get("bore_diameter", diameter * 0.4)
    
    print(f"[flange_cad] Generating flange: OD={diameter:.2f}mm, T={thickness:.2f}mm, ID={bore_diameter:.2f}mm")

    radius = diameter / 2.0
    bore_radius = bore_diameter / 2.0
    
    # Base circular flange extruded along +Z
    flange = cq.Workplane("XY").circle(radius).extrude(thickness)
    
    # Main inner bore cut
    if bore_radius > 0:
        flange = flange.faces(">Z").workplane().circle(bore_radius).cutThruAll()
        
    # Radial Bolt Hole Pattern
    # Safely extract bounded variables driven modularly upstream
    pcd_radius = parameters.get("pcd_diameter", (diameter + bore_diameter) / 2.0) / 2.0
    bolt_hole_radius = parameters.get("hole_radius", diameter * 0.05)
    hole_count = parameters.get("hole_count", 6)
    
    # Bolt seating fix: drill shallow circular recesses on Flange >Z surface
    bolt_dia = (bolt_hole_radius * 2.0) * 0.9
    recess_depth = 0.5 * (bolt_dia * 0.6)
    recess_radius = (bolt_dia * 1.8) / 2.0 + 1.0 # Add 1.0mm clearance padding perfectly spanning limits
    
    flange = (
        flange.faces(">Z").workplane()
        .polarArray(pcd_radius, 0, 360, hole_count)
        .circle(recess_radius)
        .cutBlind(-recess_depth)
    )
    
    # Create the repeating pattern
    # .polarArray(radius, startAngle, angleDegrees, numPoints)
    flange = (
        flange.faces(">Z").workplane()
        .polarArray(pcd_radius, 0, 360, hole_count)
        .circle(bolt_hole_radius)
        .cutThruAll()
    )
    
    print("[flange_cad] Bore and radial bolt hole limits cut successfully.")
    
    # Selective finishing: Add a small chamfer to outer terminal bounds if feasible
    chamfer_dist = round(thickness * 0.05, 3)
    try:
        flange = flange.faces(">Z").edges("%Circle").chamfer(chamfer_dist)
    except Exception as exc:
        pass
        
    return flange
