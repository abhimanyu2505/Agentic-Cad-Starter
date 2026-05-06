import cadquery as cq


def generate_component(parameters: dict):
    """Generate an L bracket from two rectangular plates."""
    length = float(parameters["length"])
    width = float(parameters["width"])
    height = float(parameters["height"])
    thickness = float(parameters.get("thickness", 5.0))

    if thickness >= min(length, width, height):
        raise ValueError("Bracket thickness must be smaller than bracket dimensions.")

    base = (
        cq.Workplane("XY")
        .box(length, width, thickness, centered=(True, True, False))
    )
    upright = (
        cq.Workplane("XY")
        .box(length, thickness, height, centered=(True, False, False))
        .translate((0, -width / 2.0 + thickness / 2.0, thickness))
    )
    bracket = base.union(upright)

    try:
        bracket = bracket.edges("|Z").fillet(min(1.0, thickness * 0.2))
    except Exception:
        pass

    return bracket
