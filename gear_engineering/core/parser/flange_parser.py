import re

FLANGE_DEFAULTS = {"diameter": 100.0, "thickness": 20.0}

def parse_parameters(prompt: str) -> dict:
    prompt_lower = prompt.lower()
    
    dia_match = re.search(r'(?:diameter|dia|d)[\s:=]*(?:of\s*)?(\d+(?:\.\d+)?)', prompt_lower)
    if not dia_match: dia_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:mm)?\s*(?:dia|diameter)', prompt_lower)
    dia_val = float(dia_match.group(1)) if dia_match else FLANGE_DEFAULTS["diameter"]
    
    thick_match = re.search(r'(?:thickness|thick|t)[\s:=]*(?:of\s*)?(\d+(?:\.\d+)?)', prompt_lower)
    if not thick_match: thick_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:mm)?\s*(?:thick|thickness)', prompt_lower)
    thick_val = float(thick_match.group(1)) if thick_match else FLANGE_DEFAULTS["thickness"]
    
    # Assembly scaling constants directly injected for the builder mapping
    # Inner bore approx 0.4*OD, Bolt Hole count = 6 by default
    bore_diameter = dia_val * 0.4
    pcd_diameter = (dia_val + bore_diameter) / 2.0
    hole_radius = dia_val * 0.05
    hole_count = 6
    
    return {
        "diameter": dia_val, 
        "thickness": thick_val,
        "bore_diameter": bore_diameter,
        "pcd_diameter": pcd_diameter,
        "hole_radius": hole_radius,
        "hole_count": hole_count
    }
