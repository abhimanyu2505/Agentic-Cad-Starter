import re

GEAR_DEFAULTS = {"module": 2.0, "teeth": 20, "pressure_angle": 20.0}

def parse_parameters(prompt: str) -> dict:
    """Extracts purely gear-related mathematics."""
    prompt_lower = prompt.lower()
    
    m_match = re.search(r'(?:module|m)[\s:=]*(\d+(?:\.\d+)?)', prompt_lower)
    m_val = float(m_match.group(1)) if m_match else GEAR_DEFAULTS["module"]
    
    t_match = re.search(r'(\d+)\s*teeth', prompt_lower)
    if not t_match: t_match = re.search(r'(?:teeth|z)[\s:=]*(\d+)', prompt_lower)
    t_val = int(t_match.group(1)) if t_match else GEAR_DEFAULTS["teeth"]
    
    pa_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:degree|deg|°)?\s*pressure\s*angle', prompt_lower)
    if not pa_match: pa_match = re.search(r'(?:pressure\s*angle|pa)[\s:o=of]*(\d+(?:\.\d+)?)', prompt_lower)
    pa_val = float(pa_match.group(1)) if pa_match else GEAR_DEFAULTS["pressure_angle"]
    
    params = {"module": m_val, "teeth": t_val, "pressure_angle": pa_val}
    return _validate(params)

def _validate(params: dict) -> dict:
    if params["module"] <= 0:
        params["module"] = GEAR_DEFAULTS["module"]
    if params["teeth"] < 5:
        params["teeth"] = GEAR_DEFAULTS["teeth"]
    if not (14.0 <= params["pressure_angle"] <= 25.0):
        params["pressure_angle"] = GEAR_DEFAULTS["pressure_angle"]
    # Derive assembly-critical structural parameters
    # The CAD engine handles fallback logic natively, but we expose them here
    # so the assembly planner node has visibility into the final sizing bounds.
    bore_diameter = 20.0
    thickness = 10.0 * params["module"]
    hub_diameter = 1.8 * bore_diameter
    hub_thickness = 1.2 * thickness
    
    params.update({
        "bore_diameter": bore_diameter,
        "thickness": thickness,
        "hub_diameter": hub_diameter,
        "hub_thickness": hub_thickness
    })
    
    return params
