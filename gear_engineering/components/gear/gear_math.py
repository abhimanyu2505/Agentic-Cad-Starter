import math

class SpurGearCalculator:
    """
    Core engineer-based calculator for standard involute spur gears.
    """
    def __init__(self, module: float, teeth: int, pressure_angle_deg: float):
        self.m = module
        self.z = teeth
        self.phi = math.radians(pressure_angle_deg)
        self.validate_inputs()

    def validate_inputs(self):
        if self.m <= 0: raise ValueError("Module must be positive")
        if self.z < 5: raise ValueError("Teeth count too low")
        if not (14 <= math.degrees(self.phi) <= 25): raise ValueError("Pressure angle should be between 14° and 25°")

    def calculate(self) -> dict:
        d = self.m * self.z
        db = d * math.cos(self.phi)
        ha = self.m
        hf = 1.25 * self.m
        do = d + 2 * ha
        dr = d - 2 * hf
        p = math.pi * self.m
        t = p / 2

        return {
            "module": self.m,
            "teeth": self.z,
            "pressure_angle_deg": math.degrees(self.phi),
            "pitch_diameter": d,
            "base_diameter": db,
            "addendum": ha,
            "dedendum": hf,
            "outer_diameter": do,
            "root_diameter": dr,
            "circular_pitch": p,
            "tooth_thickness": t
        }
