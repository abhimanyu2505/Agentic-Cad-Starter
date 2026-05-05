"""
Gearbox Synthesizer
===================
Goal-driven automatic gearbox designer. Given a target gear ratio and input
kinematics, this module synthesizes a complete component plan (gears, shafts,
relationships) that feeds directly into the existing constraint, kinematic, and
CAD assembly pipeline without any modification to the deterministic CAD core.
"""
import math
from typing import Optional
from utils.logger import log


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_MODULE = 2.0          # mm — standard module for all generated gears
MIN_TEETH = 12                 # Minimum to avoid undercutting
DEFAULT_MAX_TEETH = 120        # Practical manufacturing upper limit
DEFAULT_SHAFT_DIAMETER = 15.0  # mm — baseline shaft diameter
DEFAULT_SHAFT_LENGTH = 80.0    # mm — baseline shaft length
DEFAULT_EFFICIENCY = 0.98      # Per-stage power transfer efficiency

# Scoring weights
W_RATIO_ACCURACY = 0.75        # Priority: how close is the actual ratio?
W_SIMPLICITY = 0.25            # Secondary: prefer smaller (simpler) gears


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def find_best_gear_pair(
    target_ratio: float,
    min_teeth: int = MIN_TEETH,
    max_teeth: int = DEFAULT_MAX_TEETH,
    module: float = DEFAULT_MODULE,
) -> dict:
    """
    Iterates all valid (z_driver, z_driven) pairs and returns the one that
    best satisfies the target ratio using a weighted scoring function.

    Score = W_RATIO_ACCURACY * (1 - norm_error) + W_SIMPLICITY * (1 - norm_size)
    A higher score is better.
    """
    best_pair = None
    best_score = -1.0

    # Pre-compute normalization bounds
    max_error = target_ratio  # worst case: ratio far off
    max_size = min_teeth + max_teeth  # worst case combined teeth

    for z1 in range(min_teeth, max_teeth + 1):
        for z2 in range(min_teeth, max_teeth + 1):
            actual_ratio = z2 / z1
            ratio_error = abs(actual_ratio - target_ratio)

            if ratio_error / target_ratio > 0.05:
                # Skip pairs with more than 5% error immediately for speed
                continue

            norm_error = ratio_error / max_error
            norm_size = (z1 + z2) / (2 * max_size)

            score = W_RATIO_ACCURACY * (1.0 - norm_error) + W_SIMPLICITY * (1.0 - norm_size)

            if score > best_score:
                best_score = score
                best_pair = {
                    "z_driver": z1,
                    "z_driven": z2,
                    "actual_ratio": round(actual_ratio, 5),
                    "ratio_error_pct": round((ratio_error / target_ratio) * 100, 3),
                    "score": round(score, 5),
                }

    if best_pair is None:
        # Fallback: brute-force closest ratio ignoring tolerance gate
        best_err = float("inf")
        for z1 in range(min_teeth, max_teeth + 1):
            z2_ideal = round(target_ratio * z1)
            z2 = max(min_teeth, min(max_teeth, z2_ideal))
            err = abs((z2 / z1) - target_ratio)
            if err < best_err:
                best_err = err
                best_pair = {
                    "z_driver": z1,
                    "z_driven": z2,
                    "actual_ratio": round(z2 / z1, 5),
                    "ratio_error_pct": round((err / target_ratio) * 100, 3),
                    "score": 0.0,
                }

    return best_pair


def split_ratio_into_stages(total_ratio: float, num_stages: int) -> list:
    """
    Distributes a total ratio evenly across N stages.
    Per-stage ratio = total_ratio ^ (1 / num_stages).
    Returns a list of per-stage target ratios.
    """
    per_stage = total_ratio ** (1.0 / num_stages)
    return [round(per_stage, 5)] * num_stages


def scale_shaft_diameter(torque_nm: float) -> float:
    """
    Returns a shaft diameter (mm) scaled to carry the propagated torque.
    Uses a simplified solid-shaft torsion formula with a mild safety factor.
    d = (16 * T / (pi * tau_allow)) ^ (1/3)  where tau_allow = 60 MPa (mild steel).
    Enforces a 10 mm minimum to stay manufacturable.
    """
    TAU_ALLOW_MPA = 60.0
    tau_pa = TAU_ALLOW_MPA * 1e6
    torque_nm = max(torque_nm, 0.001)  # guard zero torque
    d_m = ((16.0 * torque_nm) / (math.pi * tau_pa)) ** (1.0 / 3.0)
    d_mm = d_m * 1000.0
    return round(max(10.0, d_mm * 3.0), 2)  # 3x safety factor


# ---------------------------------------------------------------------------
# Primary synthesis function
# ---------------------------------------------------------------------------

def synthesize_gearbox(
    target_ratio: float,
    input_speed_rpm: float,
    input_torque: float = 1.0,
    max_stages: int = 3,
    max_gear_teeth: int = DEFAULT_MAX_TEETH,
    module: float = DEFAULT_MODULE,
) -> dict:
    """
    Synthesizes a complete {components, relationships, metadata} plan dict
    from a performance specification.

    The returned dict is structurally identical to the LLM plan output so it
    flows directly into the existing validation + assembly pipeline.
    """
    log("synthesizer", f"Target ratio: {target_ratio:.3f}  Input: {input_speed_rpm} RPM @ {input_torque} Nm")

    # -----------------------------------------------------------------------
    # Determine number of stages required
    # -----------------------------------------------------------------------
    MAX_SINGLE_STAGE_RATIO = 6.0
    MAX_TWO_STAGE_RATIO = 36.0

    if target_ratio <= MAX_SINGLE_STAGE_RATIO:
        num_stages = 1
    elif target_ratio <= MAX_TWO_STAGE_RATIO:
        num_stages = 2
    else:
        num_stages = min(max_stages, 3)

    log("synthesizer", f"Decomposing into {num_stages} stage(s)")
    stage_ratios = split_ratio_into_stages(target_ratio, num_stages)

    # -----------------------------------------------------------------------
    # Build component & relationship lists
    # -----------------------------------------------------------------------
    components = []
    relationships = []

    # Running kinematics state
    current_speed = input_speed_rpm
    current_torque = input_torque

    # Track actual compound ratio for metadata
    actual_compound_ratio = 1.0

    # First component: the input (driver) gear of stage 1
    first_gear_id = None

    for stage_idx, stage_ratio in enumerate(stage_ratios):
        pair = find_best_gear_pair(
            target_ratio=stage_ratio,
            min_teeth=MIN_TEETH,
            max_teeth=max_gear_teeth,
            module=module,
        )

        z1 = pair["z_driver"]   # driver (smaller for reduction)
        z2 = pair["z_driven"]   # driven (larger for reduction)
        actual_stage_ratio = z2 / z1
        actual_compound_ratio *= actual_stage_ratio

        log("synthesizer", (
            f"Stage {stage_idx + 1}: z_driver={z1}, z_driven={z2}  "
            f"Stage ratio={actual_stage_ratio:.4f}  Error={pair['ratio_error_pct']}%"
        ))

        # Compute stage output kinematics
        stage_output_speed = current_speed / actual_stage_ratio
        stage_output_torque = current_torque * actual_stage_ratio * DEFAULT_EFFICIENCY

        # -----------------------------------------------------------------
        # Driver gear (input gear of this stage)
        # -----------------------------------------------------------------
        driver_id = f"gear_s{stage_idx + 1}_driver"
        driver_gear = {
            "id": driver_id,
            "type": "gear",
            "module": module,
            "teeth": z1,
            "pressure_angle": 20.0,
        }

        if stage_idx == 0:
            # This is the system input
            driver_gear["role"] = "input"
            driver_gear["input_speed_rpm"] = input_speed_rpm
            driver_gear["input_torque"] = input_torque
            first_gear_id = driver_id
        # else: intermediate driver inherits from shaft (see below)

        components.append(driver_gear)

        # -----------------------------------------------------------------
        # Driven gear (output gear of this stage)
        # -----------------------------------------------------------------
        driven_id = f"gear_s{stage_idx + 1}_driven"
        driven_gear = {
            "id": driven_id,
            "type": "gear",
            "module": module,
            "teeth": z2,
            "pressure_angle": 20.0,
        }

        if stage_idx == num_stages - 1:
            # This is the system output
            driven_gear["role"] = "output"

        components.append(driven_gear)

        # -----------------------------------------------------------------
        # Mesh relationship: driven → driver
        # -----------------------------------------------------------------
        relationships.append({
            "type": "mesh",
            "from_id": driven_id,
            "to_id": driver_id,
        })

        # -----------------------------------------------------------------
        # Inter-stage shaft + coupling gears
        # If not the last stage, add a shaft that couples the driven gear
        # of this stage to the driver gear of the next stage.
        # -----------------------------------------------------------------
        if stage_idx < num_stages - 1:
            shaft_torque = stage_output_torque
            shaft_diameter = scale_shaft_diameter(shaft_torque)
            shaft_length = max(DEFAULT_SHAFT_LENGTH, shaft_diameter * 5)

            shaft_id = f"shaft_s{stage_idx + 1}"
            shaft = {
                "id": shaft_id,
                "type": "shaft",
                "length": round(shaft_length, 2),
                "diameter": shaft_diameter,
            }
            components.append(shaft)

            # Driven gear mounts concentrically on shaft
            relationships.append({
                "type": "concentric",
                "from_id": driven_id,
                "to_id": shaft_id,
            })

            # Next stage's driver mounts concentrically on same shaft
            next_driver_id = f"gear_s{stage_idx + 2}_driver"
            relationships.append({
                "type": "concentric",
                "from_id": next_driver_id,
                "to_id": shaft_id,
            })

        # Update running kinematics for next stage
        current_speed = stage_output_speed
        current_torque = stage_output_torque

    # -----------------------------------------------------------------------
    # Design intent metadata
    # -----------------------------------------------------------------------
    actual_output_speed = input_speed_rpm / actual_compound_ratio
    actual_output_torque = (
        input_torque
        * actual_compound_ratio
        * (DEFAULT_EFFICIENCY ** num_stages)
    )

    metadata = {
        "target_ratio": target_ratio,
        "actual_ratio": round(actual_compound_ratio, 5),
        "ratio_error_pct": round(abs(actual_compound_ratio - target_ratio) / target_ratio * 100, 3),
        "num_stages": num_stages,
        "module": module,
        "input_speed_rpm": input_speed_rpm,
        "input_torque": input_torque,
        "output_speed_rpm": round(actual_output_speed, 3),
        "output_torque_nm": round(actual_output_torque, 4),
    }

    log("synthesizer", "="*50)
    log("synthesizer", "SYNTHESIS COMPLETE")
    log("synthesizer", f"  Stages        : {num_stages}")
    log("synthesizer", f"  Target ratio  : {target_ratio:.4f}:1")
    log("synthesizer", f"  Actual ratio  : {actual_compound_ratio:.4f}:1")
    log("synthesizer", f"  Ratio error   : {metadata['ratio_error_pct']}%")
    log("synthesizer", f"  Output speed  : {actual_output_speed:.2f} RPM")
    log("synthesizer", f"  Output torque : {actual_output_torque:.4f} Nm")
    log("synthesizer", "="*50)

    return {
        "components": components,
        "relationships": relationships,
        "metadata": metadata,
    }
