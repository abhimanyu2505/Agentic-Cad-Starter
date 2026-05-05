import math
import cadquery as cq
from components.gear.tooth import generate_closed_tooth_profile, rotate_point
from components.gear.gear_math import SpurGearCalculator

def generate_component(parameters: dict) -> cq.Workplane:
    """
    Standardized component generation interface for Gear CAD.
    Expects params: module, teeth, pressure_angle, face_width.
    Uses ISO-style spur gear geometry:
      pitch_diameter = module * teeth
      outer_diameter = pitch_diameter + 2 * module
      root_diameter  = pitch_diameter - 2.5 * module
    """
    module = float(parameters["module"])
    teeth = int(parameters["teeth"])
    pressure_angle = float(parameters.get("pressure_angle", 20.0))
    geom = SpurGearCalculator(module, teeth, pressure_angle).calculate()
    face_width = float(parameters.get("face_width", parameters.get("thickness", 8.0 * module)))
    if face_width <= 0:
        raise ValueError("Gear face_width must be greater than 0.")

    # 1. Generate 2D Profile Points (Resolution 80)
    single_pitch_wire, _, _ = generate_closed_tooth_profile(module, teeth, pressure_angle, num_points=80)
    
    # 2. Build 3D solid via strictly continuous wire tracing
    continuous_points = []
    angle_step = 2 * math.pi / teeth
    for i in range(teeth):
        # Simply append the pre-calculated pitch wire correctly rotated
        for x, y in single_pitch_wire:
            rot_x, rot_y = rotate_point(x, y, i * angle_step)
            continuous_points.append((rot_x, rot_y))
            
    continuous_points.append(continuous_points[0]) # Master closure seal
        
    # Extrude exactly as one contiguous Wire
    try:
        gear_solid = cq.Workplane("XY").polyline(continuous_points).close().extrude(face_width)
    except Exception as e:
        raise ValueError(f"Extrusion failed: Continuous wire boolean trap ({str(e)})")
    
    # 3. Optional hub. Minimal mode keeps this absent unless the plan requests it.
    bore_diameter = float(parameters.get("bore_diameter", 0.0))
    hub_diameter  = float(parameters.get("hub_diameter",  0.0))
    hub_thickness = float(parameters.get("hub_thickness", 0.0))

    if hub_diameter > 0 and hub_thickness > 0:
        gear_solid = gear_solid.faces(">Z").workplane().circle(hub_diameter / 2.0).extrude(hub_thickness)

    # 4. Bore cutting (shaft insertion gap)
    if bore_diameter > 0:
        gear_solid = gear_solid.faces(">Z").workplane().circle(bore_diameter / 2.0).cutThruAll()

    # 5. Keyway cut inside bore — aligned to +X axis, matching shaft slot
    if bore_diameter > 0 and parameters.get("keyway", False):
        bore_radius = bore_diameter / 2.0
        key_width   = bore_diameter * 0.25
        key_depth   = bore_diameter * 0.125
        keyway_gear_tool = (
            cq.Workplane("XZ")
            .center(0, face_width / 2.0)
            .rect(key_width, face_width + hub_thickness + 1.0)
            .extrude(key_depth)
            .translate((0, bore_radius, 0))
        )
        gear_solid = gear_solid.cut(keyway_gear_tool)

    # 6. Selective edge finishing — hub and bore faces only (avoids teeth kernel faults)
    try:
        # Chamfer the circular hub top edge by targeting only continuous circular loops
        gear_solid = (
            gear_solid
            .faces(">Z")
            .edges("%Circle")
            .chamfer(0.5)
        )
        print("[gear_cad] Hub and bore selective edge finish cleanly applied on >Z terminal face.")
    except Exception as exc:
        print(f"[gear_cad] Warning: Selective hub chamfer skipped (kernel topological boundary issue: {exc})")

    parameters.setdefault("pitch_diameter", geom["pitch_diameter"])
    parameters.setdefault("outer_diameter", geom["outer_diameter"])
    parameters.setdefault("root_diameter", geom["root_diameter"])
    parameters.setdefault("face_width", face_width)

    return gear_solid
