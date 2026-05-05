"""
component_registry.py
=====================
Deterministic component contract for Agentic CAD.

Each registered component owns three responsibilities:
  - validate required parameters
  - apply engineering defaults
  - generate CadQuery geometry through the component CAD backend
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Any, Optional


class ComponentValidationError(ValueError):
    """Raised when component parameters are missing or mechanically invalid."""


@dataclass(frozen=True)
class ComponentHandler:
    component_type: str
    required: List[str]
    defaults: Dict[str, Any]
    validate: Callable[[Dict[str, Any]], None]
    generator_path: str

    def apply_defaults(self, params: Dict[str, Any]) -> Dict[str, Any]:
        clean = dict(self.defaults)
        clean.update({k: v for k, v in params.items() if v is not None})
        return clean

    def prepare(self, node: Dict[str, Any]) -> Dict[str, Any]:
        params = {
            k: v for k, v in node.items()
            if k not in ("type", "component", "mount_on", "extracted_parameters")
        }
        clean = self.apply_defaults(params)
        missing = [field for field in self.required if clean.get(field) is None]
        if missing:
            raise ComponentValidationError(
                f"{self.component_type} missing required parameter(s): {', '.join(missing)}"
            )
        self.validate(clean)
        return clean

    def generate(self, params: Dict[str, Any]):
        module_name, attr = self.generator_path.rsplit(":", 1)
        mod = __import__(module_name, fromlist=[attr])
        return getattr(mod, attr)(params)


def _validate_positive(params: Dict[str, Any], fields: List[str]) -> None:
    for field in fields:
        if float(params[field]) <= 0:
            raise ComponentValidationError(f"{field} must be greater than 0.")


def _validate_gear(params: Dict[str, Any]) -> None:
    if params.get("face_width") is None:
        params["face_width"] = 8.0 * float(params["module"])
    _validate_positive(params, ["module", "face_width"])
    if int(params["teeth"]) < 12:
        raise ComponentValidationError("gear teeth must be 12 or greater.")
    if not 14.0 <= float(params.get("pressure_angle", 20.0)) <= 25.0:
        raise ComponentValidationError("pressure_angle must be between 14 and 25 degrees.")
    params["teeth"] = int(params["teeth"])


def _validate_shaft(params: Dict[str, Any]) -> None:
    _validate_positive(params, ["length", "diameter"])


def _validate_bolt(params: Dict[str, Any]) -> None:
    _validate_positive(params, ["length", "diameter", "pitch"])
    if str(params["thread_type"]).upper() not in ("M", "UNC", "UNF"):
        raise ComponentValidationError("thread_type must be M, UNC, or UNF.")


def _validate_bearing(params: Dict[str, Any]) -> None:
    _validate_positive(params, ["inner_diameter", "outer_diameter", "width"])
    if float(params["inner_diameter"]) >= float(params["outer_diameter"]):
        raise ComponentValidationError("bearing inner_diameter must be less than outer_diameter.")


def _validate_housing(params: Dict[str, Any]) -> None:
    _validate_positive(params, ["length", "width", "height", "wall_thickness"])


def _validate_flange(params: Dict[str, Any]) -> None:
    _validate_positive(params, ["diameter", "thickness"])


def _validate_plate(params: Dict[str, Any]) -> None:
    _validate_positive(params, ["length", "width"])
    if "thickness" in params and params["thickness"] is not None:
        _validate_positive(params, ["thickness"])


def _validate_cylinder(params: Dict[str, Any]) -> None:
    if params.get("diameter") is not None and params.get("radius") is None:
        params["radius"] = float(params["diameter"]) / 2.0
    _validate_positive(params, ["radius", "height"])


COMPONENT_REGISTRY: Dict[str, ComponentHandler] = {
    "gear": ComponentHandler(
        component_type="gear",
        required=["module", "teeth"],
        defaults={"pressure_angle": 20.0, "face_width": None},
        validate=_validate_gear,
        generator_path="components.gear.gear_cad:generate_component",
    ),
    "shaft": ComponentHandler(
        component_type="shaft",
        required=["length", "diameter"],
        defaults={},
        validate=_validate_shaft,
        generator_path="components.shaft.shaft_cad:generate_component",
    ),
    "bolt": ComponentHandler(
        component_type="bolt",
        required=["diameter", "length", "thread_type", "pitch"],
        defaults={"thread_type": "M"},
        validate=_validate_bolt,
        generator_path="components.bolt.bolt_cad:generate_component",
    ),
    "bearing": ComponentHandler(
        component_type="bearing",
        required=["inner_diameter", "outer_diameter", "width"],
        defaults={},
        validate=_validate_bearing,
        generator_path="components.bearing.bearing_cad:generate_component",
    ),
    "housing": ComponentHandler(
        component_type="housing",
        required=["length", "width", "height"],
        defaults={"wall_thickness": 5.0},
        validate=_validate_housing,
        generator_path="components.housing.housing_cad:generate_component",
    ),
    "flange": ComponentHandler(
        component_type="flange",
        required=["diameter", "thickness"],
        defaults={},
        validate=_validate_flange,
        generator_path="components.flange.flange_cad:generate_component",
    ),
    "plate": ComponentHandler(
        component_type="plate",
        required=["length", "width"],
        defaults={"thickness": 5.0},
        validate=_validate_plate,
        generator_path="components.plate.plate_cad:generate_component",
    ),
    "cylinder": ComponentHandler(
        component_type="cylinder",
        required=["radius", "height"],
        defaults={},
        validate=_validate_cylinder,
        generator_path="components.cylinder.cylinder_cad:generate_component",
    ),
}

REGISTRY = COMPONENT_REGISTRY


def get_handler(component_type: str) -> Optional[ComponentHandler]:
    """Return the deterministic handler for a component type, if registered."""
    return COMPONENT_REGISTRY.get(component_type)
