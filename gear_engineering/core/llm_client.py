import os
import json
from typing import List, Optional, Union
from pydantic import BaseModel, Field, ValidationError

class MissingParametersError(Exception):
    def __init__(self, intent: dict, missing_fields: list):
        self.intent = intent
        self.missing_fields = missing_fields
        super().__init__(f"Missing fields {missing_fields} for intent {intent.get('type', 'unknown')}")

class ComponentBase(BaseModel):
    id: str
    type: str
    role: Optional[str] = Field(None, description="Can be 'input' or 'output'")
    input_speed_rpm: Optional[float] = Field(None, description="Initial RPM for input role")
    input_torque: Optional[float] = Field(None, description="Initial Torque for input role")

class GearComponent(ComponentBase):
    type: str = "gear"
    module: float = 2.0
    teeth: int = 20
    pressure_angle: Optional[float] = 20.0

class ShaftComponent(ComponentBase):
    type: str = "shaft"
    length: float = 50.0
    diameter: float = 10.0

class BoltComponent(ComponentBase):
    type: str = "bolt"
    diameter: float = 5.0
    length: float = 20.0

class FlangeComponent(ComponentBase):
    type: str = "flange"
    diameter: float = 50.0
    thickness: float = 10.0

class PlateComponent(ComponentBase):
    type: str = "plate"
    length: float = 100.0
    width: float = 100.0

class NutComponent(ComponentBase):
    type: str = "nut"
    diameter: float = 5.0

class BearingComponent(ComponentBase):
    type: str = "bearing"
    inner_diameter: float
    outer_diameter: float
    width: float

class CouplingComponent(ComponentBase):
    type: str = "coupling"
    length: float
    diameter: float

class BracketComponent(ComponentBase):
    type: str = "bracket"
    length: float
    width: float
    height: float

class HousingComponent(ComponentBase):
    type: str = "housing"
    length: float
    width: float
    height: float

class CylinderComponent(ComponentBase):
    type: str = "cylinder"
    radius: float
    height: float

class BoxComponent(ComponentBase):
    type: str = "box"
    length: float
    width: float
    height: float

class ConeComponent(ComponentBase):
    type: str = "cone"
    diameter: float
    height: float

class SphereComponent(ComponentBase):
    type: str = "sphere"
    radius: float

ComponentType = Union[
    GearComponent, ShaftComponent, BoltComponent, FlangeComponent, PlateComponent, NutComponent,
    BearingComponent, CouplingComponent, BracketComponent, HousingComponent,
    CylinderComponent, BoxComponent, ConeComponent, SphereComponent
]

class Relationship(BaseModel):
    type: str  # e.g., concentric, flush, offset, mount, fasten, mesh
    from_id: str
    to_id: str
    distance: Optional[float] = None

class CADPlan(BaseModel):
    components: List[ComponentType]
    relationships: Optional[List[Relationship]] = Field(default_factory=list)

def generate_cad_plan(prompt: str) -> dict:
    """
    Calls the LLM API to extract a structured JSON CAD plan from the prompt.
    Returns a validated dictionary mapping.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("The 'openai' python package is required for the AI layer. Please install it.")
        
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")
        
    client = OpenAI(api_key=api_key)
    
    system_prompt = """
    You are an expert CAD planning AI. Extract mechanical components from user prompts and return a JSON object.
    The JSON must have "components" (a list of objects) and "relationships" (a list of structural constraints).
    
    Every component MUST have a unique string "id" (e.g., "gear_1", "shaft_A").
    
    Components can optionally act as mechanical endpoints using the "role" field ("input" or "output").
    If "role" is "input", you MUST include "input_speed_rpm" (float) and optionally "input_torque" (float).
    
    Supported component types and their required fields:
    - gear: type="gear", module (float), teeth (int), pressure_angle (float, default 20)
    - shaft: type="shaft", length (float), diameter (float)
    - bolt: type="bolt", diameter (float), length (float)
    - flange: type="flange", diameter (float), thickness (float)
    - plate: type="plate", length (float), width (float)
    - nut: type="nut", diameter (float)
    - bearing: type="bearing", inner_diameter (float), outer_diameter (float), width (float)
    - coupling: type="coupling", length (float), diameter (float)
    - bracket: type="bracket", length (float), width (float), height (float)
    - housing: type="housing", length (float), width (float), height (float)
    - cylinder: type="cylinder", radius (float) or diameter (float), height (float)
    - box: type="box", length (float), width (float), height (float)
    - cone: type="cone", diameter (float), height (float)
    - sphere: type="sphere", radius (float)
    
    Relationships define how components physically connect.
    Relationship types:
    - "concentric": Align the central axes of two components (X/Y alignment). Transfers rotation 1:1.
    - "flush": Align the faces of two components (Z stacking).
    - "offset": Apply a specific Z distance (requires "distance" float field).
    - "mount" / "fasten": General connections. Transfers rotation 1:1.
    - "mesh": Connect two gears mechanically (aligns gears radially based on pitch diameters). Multiplies torque and divides speed by gear ratio.
    
    A relationship has "type", "from_id", "to_id", and optional "distance".
    
    Example output:
    {
      "components": [
        {"id": "gear_1", "type": "gear", "module": 2, "teeth": 20, "role": "input", "input_speed_rpm": 1500, "input_torque": 10},
        {"id": "gear_2", "type": "gear", "module": 2, "teeth": 40, "role": "output"}
      ],
      "relationships": [
        {"type": "mesh", "from_id": "gear_2", "to_id": "gear_1"}
      ]
    }
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        response_format={ "type": "json_object" }
    )
    
    raw_json = response.choices[0].message.content
    data = json.loads(raw_json)
    
    if "error" in data:
        raise ValueError(f"AI Plan Error: {data['error']}")
        
    # Validate with Pydantic
    try:
        plan = CADPlan(**data)
    except ValidationError as e:
        missing = [str(err["loc"][-1]) for err in e.errors() if err["type"] == "missing"]
        if missing and data.get("components"):
            intent = data["components"][0]
            raise MissingParametersError(intent, list(set(missing)))
        raise ValueError(f"AI generated invalid component parameters: {str(e)}")
        
    # Compatible with Pydantic v1 and v2
    if hasattr(plan, "model_dump"):
        return plan.model_dump(exclude_none=True)
    else:
        return plan.dict(exclude_none=True)


def generate_cad_delta(prompt: str, previous_state: dict) -> dict:
    """
    LLM-as-planner: given the current design state and a user intent,
    return ONLY an incremental delta — not the full design graph.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("The 'openai' python package is required for the AI layer.")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    client = OpenAI(api_key=api_key)

    existing_ids = [c.get("id") for c in previous_state.get("components", [])]
    existing_summary = json.dumps({
        "component_ids": existing_ids,
        "component_count": len(existing_ids),
        "relationship_count": len(previous_state.get("relationships", [])),
    }, indent=2)

    delta_system_prompt = f"""
You are an expert mechanical CAD design assistant managing a stateful assembly.

CURRENT DESIGN STATE SUMMARY:
{existing_summary}

FULL CURRENT STATE:
{json.dumps(previous_state, indent=2)}

Your ONLY job is to interpret the user's request and output a minimal JSON delta.
DO NOT return the full design graph. Only return what needs to change.

Output format:
{{
  "action": "add" | "modify" | "remove",
  "components": [ ...only new or changed components... ],
  "relationships": [ ...only new or changed relationships... ],
  "reasoning": "brief explanation"
}}

Rules:
- Use "add" to add new components to the existing assembly.
- Use "modify" to change parameters of existing components (reference by their exact id).
- Use "remove" to remove components by id.
- Every new component MUST have a unique "id" that does NOT conflict with: {existing_ids}
- Prefix new IDs with the component type and a number (e.g. "gear_3", "shaft_B").
- For relationships, "from_id" and "to_id" must reference valid component IDs (existing OR newly added).
- Relationship types: concentric, flush, offset, mount, fasten, mesh.
- Supported component types and fields: gear (module, teeth), shaft (length, diameter),
  bearing (inner_diameter, outer_diameter, width), flange (diameter, thickness),
  housing (length, width, height), bolt (diameter, length), nut (diameter),
  plate (length, width), cylinder (radius, height), box (length, width, height),
  cone (diameter, height), sphere (radius).
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system",  "content": delta_system_prompt},
            {"role": "user",    "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    raw_json = response.choices[0].message.content
    delta    = json.loads(raw_json)

    # Basic sanity check
    if "action" not in delta:
        raise ValueError(f"LLM delta missing 'action' field. Raw: {raw_json[:300]}")
    if delta["action"] not in ("add", "modify", "remove"):
        raise ValueError(f"Invalid delta action: {delta['action']}")

    # Validate components if adding
    if delta["action"] == "add" and delta.get("components"):
        try:
            CADPlan(components=delta["components"])
        except ValidationError as e:
            missing = [str(err["loc"][-1]) for err in e.errors() if err["type"] == "missing"]
            if missing:
                intent = delta["components"][0]
                raise MissingParametersError(intent, list(set(missing)))

    return delta

def extract_parameters(prompt: str, missing_fields: list) -> dict:
    """Deterministic LLM parser that strictly extracts numerical fields."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("The 'openai' python package is required.")

    api_key = os.environ.get("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)

    system_prompt = f"""
You are a specialized parameter extraction tool.
Extract the following numerical parameters from the user's text: {missing_fields}.
Return ONLY a flat JSON dictionary containing the extracted keys and their float/int values.
Example output format: {{"length": 120, "diameter": 20}}
Do not invent parameters. Only extract what is clearly specified in the text.
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def generate_primitive_plan(prompt: str) -> dict:
    """
    Fallback planner specifically for basic geometric primitives 
    (cone, cylinder, box, sphere) when the primary planner fails or
    rejects non-mechanical intent.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("The 'openai' python package is required.")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    client = OpenAI(api_key=api_key)

    system_prompt = """
You are a fallback CAD interpreter for basic geometric primitives.
Extract the shapes from the prompt and return them as a JSON object with a "components" list.
No relationships are needed. Every component must have an "id" (e.g. "cone_1").

Supported types:
- cone (needs diameter, height)
- cylinder (needs diameter or radius, height)
- box (needs length, width, height)
- sphere (needs radius)
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    raw_json = response.choices[0].message.content
    return json.loads(raw_json)

