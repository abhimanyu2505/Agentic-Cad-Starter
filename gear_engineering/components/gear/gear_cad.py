"""
gear_cad.py
===========
Real involute gear geometry using cq_gears.
Supports spur and helical gear types.
All units in mm. Geometry centred at origin.
"""
import cadquery as cq
from cq_gears import SpurGear


def _as_workplane(solid) -> cq.Workplane:
    if isinstance(solid, cq.Workplane):
        return solid
    return cq.Workplane("XY").add(solid)


def generate_component(parameters: dict) -> cq.Workplane:
    """
    Generate a real involute gear using cq_gears.

    Required : module, teeth
    Optional : gear_type (spur/helical), thickness/face_width,
               pressure_angle, bore_diameter, keyway
    """
    module         = float(parameters["module"])
    teeth          = int(parameters["teeth"])
    pressure_angle = float(parameters.get("pressure_angle", 20.0))
    thickness      = float(
        parameters.get("thickness", parameters.get("face_width", 8.0 * module))
    )
    gear_type      = str(parameters.get("gear_type", "spur")).lower()

    if module <= 0:
        raise ValueError("Gear module must be greater than 0.")
    if thickness <= 0:
        raise ValueError("Gear thickness must be greater than 0.")
    if teeth < 6:
        raise ValueError("Gear teeth must be 6 or greater.")

    # helix_angle adds twist for helical gears; 0 = standard spur
    helix_angle = 15.0 if gear_type == "helical" else 0.0

    spur_gear = SpurGear(
        module=module,
        teeth_number=teeth,
        width=thickness,
        pressure_angle=pressure_angle,
        helix_angle=helix_angle,
    )
    gear_solid = _as_workplane(cq.Workplane("XY").gear(spur_gear))

    # Optional bore
    bore_diameter = float(parameters.get("bore_diameter", 0.0))
    if bore_diameter > 0:
        pitch_diameter = module * teeth
        if bore_diameter >= pitch_diameter:
            raise ValueError("bore_diameter must be smaller than pitch diameter.")
        gear_solid = (
            gear_solid
            .faces(">Z").workplane()
            .circle(bore_diameter / 2.0)
            .cutThruAll()
        )

    # Optional keyway
    if bore_diameter > 0 and parameters.get("keyway", False):
        bore_radius = bore_diameter / 2.0
        key_width   = bore_diameter * 0.25
        key_depth   = bore_diameter * 0.125
        keyway_tool = (
            cq.Workplane("XZ")
            .center(0, thickness / 2.0)
            .rect(key_width, thickness + 1.0)
            .extrude(key_depth)
            .translate((0, bore_radius, 0))
        )
        gear_solid = gear_solid.cut(keyway_tool)

    # Store computed geometry metadata back into params dict
    pitch_diameter = module * teeth
    parameters["pitch_diameter"] = pitch_diameter
    parameters["outer_diameter"] = pitch_diameter + 2.0 * module
    parameters["root_diameter"]  = pitch_diameter - 2.5 * module
    parameters["face_width"]     = thickness
    parameters["thickness"]      = thickness

    return gear_solid
