import cadquery as cq


def generate_component(parameters: dict):
    """Generate a simple cylindrical shaft coupling with an optional through bore."""
    length = float(parameters["length"])
    diameter = float(parameters["diameter"])
    bore_diameter = float(parameters.get("bore_diameter", diameter * 0.45))

    if bore_diameter >= diameter:
        raise ValueError("Coupling bore_diameter must be less than outside diameter.")

    coupling = cq.Workplane("XY").circle(diameter / 2.0).extrude(length)
    coupling = coupling.faces(">Z").workplane().circle(bore_diameter / 2.0).cutThruAll()

    try:
        coupling = coupling.edges("%Circle").chamfer(min(0.75, diameter * 0.03))
    except Exception:
        pass

    return coupling
