import re

PLATE_DEFAULTS = {"width": 50.0, "length": 50.0}

def parse_parameters(prompt: str) -> dict:
    prompt_lower = prompt.lower()
    
    len_match = re.search(r'(?:length|l)[\s:=]*(?:of\s*)?(\d+(?:\.\d+)?)', prompt_lower)
    len_val = float(len_match.group(1)) if len_match else PLATE_DEFAULTS["length"]

    width_match = re.search(r'(?:width|w)[\s:=]*(?:of\s*)?(\d+(?:\.\d+)?)', prompt_lower)
    width_val = float(width_match.group(1)) if width_match else PLATE_DEFAULTS["width"]
    
    # Assembly scaling constants mapped to standard Flange OD 100 metrics
    pcd_diameter = 70.0
    hole_radius = 5.0
    hole_count = 6
    
    return {
        "width": width_val, 
        "length": len_val,
        "pcd_diameter": pcd_diameter,
        "hole_radius": hole_radius,
        "hole_count": hole_count
    }
