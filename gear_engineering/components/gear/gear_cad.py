import math
import cadquery as cq
from components.gear.tooth import generate_closed_tooth_profile, rotate_point

def generate_component(parameters: dict) -> cq.Workplane:
    """
    Standardized component generation interface for Gear CAD.
    Expects params: module, teeth, pressure_angle.
    Thickness is defaulted natively at 10.0mm.
    """
    module = parameters.get("module", 2.0)
    teeth = parameters.get("teeth", 20)
    pressure_angle = parameters.get("pressure_angle", 20.0)
    # Proportion Adjustments
    thickness = parameters.get("thickness", 10.0 * module)

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
        gear_solid = cq.Workplane("XY").polyline(continuous_points).close().extrude(thickness)
    except Exception as e:
        raise ValueError(f"Extrusion failed: Continuous wire boolean trap ({str(e)})")
    
    # 3. Add Hub Extension Construct
    bore_diameter = parameters.get("bore_diameter", 20.0)  # Native match for shaft
    hub_diameter  = parameters.get("hub_diameter",  1.8 * bore_diameter)
    hub_thickness = parameters.get("hub_thickness", 1.2 * thickness)

    if hub_diameter > 0 and hub_thickness > 0:
        gear_solid = gear_solid.faces(">Z").workplane().circle(hub_diameter / 2.0).extrude(hub_thickness)

    # 4. Bore cutting (shaft insertion gap)
    if bore_diameter > 0:
        gear_solid = gear_solid.faces(">Z").workplane().circle(bore_diameter / 2.0).cutThruAll()

    # 5. Keyway cut inside bore — aligned to +X axis, matching shaft slot
    bore_radius = bore_diameter / 2.0
    key_width   = bore_diameter * 0.25
    key_depth   = bore_diameter * 0.125
    # Tool: slot starting from bore surface, cutting radially outward along +Y
    keyway_gear_tool = (
        cq.Workplane("XZ")
        .center(0, thickness / 2.0)
        .rect(key_width, thickness + hub_thickness + 1.0)   # span full axial depth
        .extrude(key_depth)
        .translate((0, bore_radius, 0))                     # position flush at bore wall
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
        print(f"[gear_cad] Hub and bore selective edge finish cleanly applied on >Z terminal face.")
    except Exception as exc:
        print(f"[gear_cad] Warning: Selective hub chamfer skipped (kernel topological boundary issue: {exc})")

    # 7. Debug export for isolated keyway gear validation
    cq.exporters.export(gear_solid, "debug_keyway_gear.step")

    return gear_solid

