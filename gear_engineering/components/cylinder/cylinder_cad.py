import cadquery as cq


def generate_component(parameters: dict):
    """Generate a parametric cylinder from radius and height."""
    radius = float(parameters["radius"])
    height = float(parameters["height"])
    return cq.Workplane("XY").circle(radius).extrude(height)
