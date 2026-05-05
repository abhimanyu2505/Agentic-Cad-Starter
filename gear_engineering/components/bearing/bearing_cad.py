import cadquery as cq

def generate_component(parameters: dict):
    """
    Standardized component generation interface for Bearing CAD.
    Expects params: inner_diameter, outer_diameter, width.
    """
    inner_diameter = parameters.get("inner_diameter", 10.0)
    outer_diameter = parameters.get("outer_diameter", 22.0)
    width = parameters.get("width", 7.0)

    if inner_diameter >= outer_diameter:
        raise ValueError(f"Bearing invalid: inner_diameter ({inner_diameter}) must be less than outer_diameter ({outer_diameter})")

    # Generate a hollow cylinder
    bearing_solid = (
        cq.Workplane("XY")
        .circle(outer_diameter / 2.0)
        .circle(inner_diameter / 2.0)
        .extrude(width)
    )

    # Optional: simple chamfer for aesthetics
    try:
        chamfer_dist = min(0.5, (outer_diameter - inner_diameter) * 0.1)
        bearing_solid = bearing_solid.edges().chamfer(chamfer_dist)
    except Exception:
        pass

    return bearing_solid
