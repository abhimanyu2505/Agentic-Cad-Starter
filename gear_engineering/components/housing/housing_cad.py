import cadquery as cq


def generate_component(parameters: dict):
    """
    Generate a standalone rectangular housing shell.
    Expects: length, width, height, wall_thickness.
    """
    length = float(parameters["length"])
    width = float(parameters["width"])
    height = float(parameters["height"])
    wall = float(parameters.get("wall_thickness", 5.0))

    inner_l = length - 2.0 * wall
    inner_w = width - 2.0 * wall
    inner_h = height - 2.0 * wall
    if inner_l <= 0 or inner_w <= 0 or inner_h <= 0:
        raise ValueError("Housing wall_thickness is too large for the requested dimensions.")

    shell = cq.Workplane("XY").box(length, width, height)
    cavity = cq.Workplane("XY").box(inner_l, inner_w, inner_h).translate((0, 0, wall))
    return shell.cut(cavity)
