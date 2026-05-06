"""
param_handler.py
================
Parameter defaults and validation for the deterministic conversation engine.
No LLM dependency. Called before any geometry generation.
"""
from __future__ import annotations


def apply_defaults(component_type: str, params: dict) -> dict:
    """Fill in safe engineering defaults for optional parameters."""
    p = dict(params)

    if component_type == "gear":
        return {
            "gear_type":      p.get("gear_type", "spur"),
            "module":         float(p["module"]),
            "teeth":          int(p["teeth"]),
            "thickness":      float(p.get("thickness", 10.0)),
            "pressure_angle": float(p.get("pressure_angle", 20.0)),
            "bore_diameter":  float(p.get("bore_diameter", 0.0)),
        }

    if component_type == "shaft":
        return {
            "length":   float(p["length"]),
            "diameter": float(p["diameter"]),
        }

    if component_type == "bolt":
        return {
            "diameter":    float(p["diameter"]),
            "length":      float(p["length"]),
            "thread_type": p.get("thread_type", "coarse"),
            "pitch":       float(p.get("pitch", 1.0)),
        }

    if component_type == "bearing":
        return {
            "inner_diameter": float(p["inner_diameter"]),
            "outer_diameter": float(p["outer_diameter"]),
            "width":          float(p["width"]),
        }

    if component_type == "flange":
        return {
            "diameter":  float(p["diameter"]),
            "thickness": float(p["thickness"]),
        }

    if component_type == "gearbox":
        return {
            "target_ratio":    float(p["target_ratio"]),
            "input_speed_rpm": float(p.get("input_speed_rpm", 1500.0)),
            "input_torque":    float(p.get("input_torque", 1.0)),
            "max_stages":      int(p.get("max_stages", 3)),
        }

    if component_type == "plate":
        return {
            "length":    float(p["length"]),
            "width":     float(p["width"]),
            "thickness": float(p.get("thickness", 5.0)),
        }

    if component_type == "housing":
        return {
            "length":         float(p["length"]),
            "width":          float(p["width"]),
            "height":         float(p["height"]),
            "wall_thickness": float(p.get("wall_thickness", 5.0)),
        }

    if component_type == "coupling":
        return {
            "length":   float(p["length"]),
            "diameter": float(p["diameter"]),
        }

    if component_type == "bracket":
        return {
            "length":    float(p["length"]),
            "width":     float(p["width"]),
            "height":    float(p["height"]),
            "thickness": float(p.get("thickness", 5.0)),
        }

    if component_type == "cylinder":
        radius = p.get("radius") or (float(p["diameter"]) / 2.0 if p.get("diameter") else None)
        return {
            "radius": float(radius),
            "height": float(p["height"]),
        }

    if component_type == "nut":
        return {
            "diameter":    float(p["diameter"]),
            "thread_type": p.get("thread_type", "coarse"),
            "pitch":       float(p.get("pitch", 1.0)),
        }

    return dict(p)


def validate_params(component_type, p):
    """
    Validate parameters for a component type.
    Returns an error string if invalid, or None if valid.
    """
    if component_type == "gear":
        if float(p.get("module", 0)) <= 0:
            return "Module must be greater than 0."
        if int(p.get("teeth", 0)) < 6:
            return "Teeth must be 6 or greater."
        if float(p.get("thickness", 1)) <= 0:
            return "Thickness must be greater than 0."
        return None

    if component_type == "shaft":
        if float(p.get("length", 0)) <= 0:
            return "Shaft length must be positive."
        if float(p.get("diameter", 0)) <= 0:
            return "Shaft diameter must be positive."
        return None

    if component_type == "bolt":
        if float(p.get("length", 0)) <= 0:
            return "Bolt length must be positive."
        if float(p.get("diameter", 0)) <= 0:
            return "Bolt diameter must be positive."
        return None

    if component_type == "bearing":
        inner = float(p.get("inner_diameter", 0))
        outer = float(p.get("outer_diameter", 0))
        if inner <= 0 or outer <= 0:
            return "Bearing diameters must be positive."
        if inner >= outer:
            return "Inner diameter must be less than outer diameter."
        if float(p.get("width", 0)) <= 0:
            return "Bearing width must be positive."
        return None

    if component_type == "flange":
        if float(p.get("diameter", 0)) <= 0:
            return "Flange diameter must be positive."
        if float(p.get("thickness", 0)) <= 0:
            return "Flange thickness must be positive."
        return None

    if component_type == "gearbox":
        if float(p.get("target_ratio", 0)) <= 0:
            return "Gearbox target ratio must be greater than 0."
        return None

    if component_type in ("plate", "housing", "bracket"):
        for field in ("length", "width"):
            if float(p.get(field, 0)) <= 0:
                return f"{field.capitalize()} must be positive."
        if component_type in ("housing", "bracket") and float(p.get("height", 0)) <= 0:
            return "Height must be positive."
        return None

    if component_type == "cylinder":
        if float(p.get("radius", 0)) <= 0:
            return "Cylinder radius must be positive."
        if float(p.get("height", 0)) <= 0:
            return "Cylinder height must be positive."
        return None

    if component_type in ("coupling", "nut"):
        if float(p.get("diameter", 0)) <= 0:
            return "Diameter must be positive."
        return None

    return None
