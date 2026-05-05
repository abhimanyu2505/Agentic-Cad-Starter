import re

SHAFT_DEFAULTS = {"diameter": 20.0}

def parse_parameters(prompt: str) -> dict:
    prompt_lower = prompt.lower()
    
    len_match = re.search(r'(?:length|l)[\s:=]*(?:of\s*)?(\d+(?:\.\d+)?)', prompt_lower)
    if not len_match: len_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:mm)?\s*(?:long|length)', prompt_lower)
    if not len_match: raise ValueError("Missing Essential Parameter: 'length' required for shaft extraction.")
    len_val = float(len_match.group(1))

    dia_match = re.search(r'(?:diameter|dia|d)[\s:=]*(?:of\s*)?(\d+(?:\.\d+)?)', prompt_lower)
    if not dia_match: dia_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:mm)?\s*(?:dia|diameter)', prompt_lower)
    dia_val = float(dia_match.group(1)) if dia_match else SHAFT_DEFAULTS["diameter"]
    
    return {"length": len_val, "diameter": dia_val}
