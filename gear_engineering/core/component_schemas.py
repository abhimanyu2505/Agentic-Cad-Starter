"""
component_schemas.py
====================
Schema-driven intent and question layer for general mechanical components.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional


COMPONENT_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "gear": {
        "required": ["module", "teeth"],
        "optional": ["pressure_angle", "face_width", "bore_diameter"],
        "questions": {
            "module": "What module should the gear use?",
            "teeth": "How many teeth should the gear have?",
        },
    },
    "shaft": {
        "required": ["length", "diameter"],
        "optional": ["keyway"],
        "questions": {
            "length": "What shaft length should I use in millimeters?",
            "diameter": "What shaft diameter should I use in millimeters?",
        },
    },
    "bolt": {
        "required": ["diameter", "length", "thread_type", "pitch"],
        "optional": ["head_diameter", "head_height"],
        "questions": {
            "diameter": "What bolt diameter should I use?",
            "length": "What bolt length should I use?",
            "thread_type": "What thread type should I use: M, UNC, or UNF?",
            "pitch": "What thread pitch should I use?",
        },
    },
    "bearing": {
        "required": ["inner_diameter", "outer_diameter", "width"],
        "optional": [],
        "questions": {
            "inner_diameter": "What inner diameter should the bearing have?",
            "outer_diameter": "What outer diameter should the bearing have?",
            "width": "What bearing width should I use?",
        },
    },
    "flange": {
        "required": ["diameter", "thickness"],
        "optional": ["bore_diameter", "pcd_diameter", "hole_radius", "hole_count"],
        "questions": {
            "diameter": "What outside diameter should the flange have?",
            "thickness": "What flange thickness should I use?",
        },
    },
    "plate": {
        "required": ["length", "width"],
        "optional": ["thickness", "pcd_diameter", "hole_radius", "hole_count"],
        "questions": {
            "length": "What plate length should I use?",
            "width": "What plate width should I use?",
        },
    },
    "cylinder": {
        "required": ["radius", "height"],
        "optional": ["diameter"],
        "questions": {
            "radius": "What cylinder radius should I use?",
            "height": "What cylinder height should I use?",
        },
    },
    "housing": {
        "required": ["length", "width", "height"],
        "optional": ["wall_thickness"],
        "questions": {
            "length": "What housing length should I use?",
            "width": "What housing width should I use?",
            "height": "What housing height should I use?",
        },
    },
    "nut": {
        "required": ["diameter", "thread_type", "pitch"],
        "optional": ["thickness"],
        "questions": {
            "diameter": "What nut nominal diameter should I use?",
            "thread_type": "What thread type should I use: M, UNC, or UNF?",
            "pitch": "What thread pitch should I use?",
        },
    },
    "coupling": {
        "required": ["length", "diameter"],
        "optional": ["bore_diameter"],
        "questions": {
            "length": "What coupling length should I use in millimeters?",
            "diameter": "What coupling outside diameter should I use in millimeters?",
        },
    },
    "bracket": {
        "required": ["length", "width", "height"],
        "optional": ["thickness"],
        "questions": {
            "length": "What bracket length should I use?",
            "width": "What bracket width should I use?",
            "height": "What bracket height should I use?",
        },
    },
    "gearbox": {
        "required": ["target_ratio"],
        "optional": ["input_speed_rpm", "input_torque", "max_stages"],
        "questions": {
            "target_ratio": "What target ratio should the gearbox achieve? For example: 4:1.",
        },
    },
}


_COMPONENT_KEYWORDS = {
    "bearing": ["bearing", "ball bearing", "roller bearing"],
    "flange": ["flange"],
    "cylinder": ["cylinder", "cylindrical"],
    "housing": ["housing", "case", "enclosure"],
    "coupling": ["coupling", "coupler"],
    "bracket": ["bracket", "angle bracket"],
    "gear": ["gear", "spur gear"],
    "shaft": ["shaft", "axle"],
    "bolt": ["bolt", "screw", "fastener"],
    "nut": ["nut", "hex nut"],
    "plate": ["plate"],
}


def detect_component(prompt: str) -> Optional[str]:
    """Deterministically map user text to a supported component type."""
    text = (prompt or "").lower()
    for component_type, keywords in _COMPONENT_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in keywords):
            return component_type
    return None


def missing_parameters(component_type: str, parameters: Dict[str, Any]) -> List[str]:
    """Return required schema fields not present in parameters."""
    schema = COMPONENT_SCHEMAS.get(component_type, {})
    return [
        field for field in schema.get("required", [])
        if parameters.get(field) is None or parameters.get(field) == ""
    ]


def question_for(component_type: str, missing: List[str]) -> str:
    """Build a structured question for the next missing parameter set."""
    schema = COMPONENT_SCHEMAS.get(component_type, {})
    questions = schema.get("questions", {})
    if not missing:
        return ""
    if len(missing) == 1:
        return questions.get(missing[0], f"Please provide {missing[0].replace('_', ' ')}.")
    prompts = [questions.get(field, field.replace("_", " ")) for field in missing]
    return " ".join(prompts)
