def extract_intents(prompt: str) -> list:
    """
    Lightweight base NLP hook.
    Scans natural language prompts to detect mentioned core mechanical components.
    Returns a list of base components requested.
    """
    prompt_lower = prompt.lower()
    intents = []
    
    if "gear" in prompt_lower: intents.append("gear")
    if "shaft" in prompt_lower: intents.append("shaft")
    if "bolt" in prompt_lower: intents.append("bolt")
    if "plate" in prompt_lower: intents.append("plate")
    if "flange" in prompt_lower: intents.append("flange")
        
    return intents
