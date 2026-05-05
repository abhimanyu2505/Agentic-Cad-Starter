import math
from components.gear.gear_math import SpurGearCalculator
from components.gear.involute import generate_involute_curve

def rotate_point(x: float, y: float, angle: float):
    return (x * math.cos(angle) - y * math.sin(angle),
            x * math.sin(angle) + y * math.cos(angle))

def generate_closed_tooth_profile(module: float, teeth: int, pressure_angle_deg: float, num_points: int = 30):
    gear = SpurGearCalculator(module, teeth, pressure_angle_deg)
    geom = gear.calculate()
    
    rp = geom["pitch_diameter"] / 2
    ro = geom["outer_diameter"] / 2
    rb = geom["base_diameter"] / 2
    rr = geom["root_diameter"] / 2
    tooth_thickness = geom["tooth_thickness"]
    
    if ro <= rb: raise ValueError("Outer radius is smaller than base radius.")
    t_max = math.sqrt((ro / rb)**2 - 1)
    
    basic_involute = generate_involute_curve(rb, t_max, num_points)
    
    t_p = math.sqrt((rp / rb)**2 - 1)
    x_p = rb * (math.cos(t_p) + t_p * math.sin(t_p))
    y_p = rb * (math.sin(t_p) - t_p * math.cos(t_p))
    theta_p = math.atan2(y_p, x_p)
    
    angular_thickness = tooth_thickness / rp
    target_pitch_angle = (math.pi / 2) - (angular_thickness / 2)
    rotation_angle = target_pitch_angle - theta_p
    
    right_flank = [rotate_point(x, y, rotation_angle) for x, y in basic_involute]
    
    if rr < rb:
        # Add a blended curve instead of a strict corner
        # Using a slight quadratic bezier curve to logically approximate a precision root fillet
        first_pt = right_flank[0]
        theta_base = math.atan2(first_pt[1], first_pt[0])
        root_pt = (rr * math.cos(theta_base), rr * math.sin(theta_base))
        ctrl_pt = ((rr * math.cos(theta_base)) * 1.05, (rr * math.sin(theta_base)) * 1.05)
        
        blend_pts = []
        for i in range(5, 0, -1): # Reverse to order [root point -> base point]
            t = i / 5.0
            bx = (1-t)**2 * root_pt[0] + 2*(1-t)*t * ctrl_pt[0] + t**2 * first_pt[0]
            by = (1-t)**2 * root_pt[1] + 2*(1-t)*t * ctrl_pt[1] + t**2 * first_pt[1]
            blend_pts.append((bx, by))
            
        right_flank = blend_pts + right_flank[1:] # Displace initial unrounded point gracefully
    else:
        right_flank = [pt for pt in right_flank if math.hypot(pt[0], pt[1]) >= rr]

    left_flank_ordered = [(-x, y) for (x, y) in right_flank]
    left_flank_ordered.reverse()
    
    top_arc = []
    top_right_angle = math.atan2(right_flank[-1][1], right_flank[-1][0])
    top_left_angle = math.atan2(left_flank_ordered[0][1], left_flank_ordered[0][0])
    arc_points = 15
    for i in range(1, arc_points):
        frac = i / arc_points
        angle = top_right_angle + frac * (top_left_angle - top_right_angle)
        top_arc.append((ro * math.cos(angle), ro * math.sin(angle)))
        
    gap_arc = []
    bottom_left_angle = math.atan2(left_flank_ordered[-1][1], left_flank_ordered[-1][0])
    
    angle_step = 2 * math.pi / teeth
    next_right_angle = math.atan2(right_flank[0][1], right_flank[0][0]) + angle_step
    
    # Normalize angular progression
    if next_right_angle < bottom_left_angle:
        next_right_angle += 2 * math.pi
        
    for i in range(1, arc_points):
        frac = i / arc_points
        angle = bottom_left_angle + frac * (next_right_angle - bottom_left_angle)
        gap_arc.append((rr * math.cos(angle), rr * math.sin(angle)))
        
    single_pitch_wire = right_flank + top_arc + left_flank_ordered + gap_arc
    return single_pitch_wire, right_flank, left_flank_ordered
