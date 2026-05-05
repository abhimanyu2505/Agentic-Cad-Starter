import math

def generate_involute_curve(rb: float, max_t: float, num_points: int) -> list:
    """
    Generates X, Y coordinate points for an involute curve using standard parametric equations.
    """
    if num_points <= 1:
        raise ValueError("num_points must be greater than 1")
        
    points = []
    for i in range(num_points):
        # Linearly interpolate t from 0 to max_t
        t = (i / (num_points - 1)) * max_t
        x = rb * (math.cos(t) + t * math.sin(t))
        y = rb * (math.sin(t) - t * math.cos(t))
        points.append((x, y))
        
    return points
