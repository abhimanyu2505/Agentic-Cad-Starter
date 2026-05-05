def build_execution_graph(prompt: str, intents: list) -> list:
    """
    Upgraded Agentic Module.
    Generates a structured multi-part build JSON plan, 
    mapping implicit mounting and geometric relations.
    """
    graph = []
    prompt_lower = prompt.lower()
    
    for intent in intents:
        node = {"component": intent}
        
        # Contextual Semantic Relational Mapping
        if intent == "gear" and "mounted" in prompt_lower and "shaft" in intents:
            node["mount_on"] = "shaft"
        elif intent == "bolt" and "mounted" in prompt_lower and "plate" in intents:
            node["mount_on"] = "plate"
            
        graph.append(node)
        
    # Validation default trap
    if not graph:
        graph.append({"component": "unknown"})
        
    return graph
