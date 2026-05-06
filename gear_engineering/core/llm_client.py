"""
llm_client.py
=============
LLM interface for the Agentic CAD pipeline.

Provides:
  - Pydantic component models (validation contracts)
  - generate_cad_plan()   — fresh design from a user prompt + conversation history
  - generate_cad_delta()  — incremental delta on an existing design state
  - extract_parameters()  — targeted extraction of missing numeric fields
  - generate_primitive_plan() — fallback for basic geometric primitives
"""

import os
import json
from typing import List, Optional, Union
from pydantic import BaseModel, Field, ValidationError


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class MissingParametersError(Exception):
    def __init__(self, intent: dict, missing_fields: list):
        self.intent = intent
        self.missing_fields = missing_fields
        super().__init__(
            f"Missing fields {missing_fields} for intent {intent.get('type', 'unknown')}"
        )


class OpenAIConfigurationError(RuntimeError):
    """Raised when the OpenAI client is needed but no API key is configured."""


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def _load_local_env_once() -> None:
    """Load OPENAI_API_KEY from repo-local .env files without adding a dependency."""
    if os.getenv("OPENAI_API_KEY"):
        return

    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", ".."))
    candidates = [
        os.path.join(repo_root, ".env"),
        os.path.join(repo_root, "gear_engineering", ".env"),
    ]

    for env_path in candidates:
        if not os.path.exists(env_path):
            continue
        with open(env_path, encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == "OPENAI_API_KEY":
                    os.environ["OPENAI_API_KEY"] = value.strip().strip('"').strip("'")
                    return


# ---------------------------------------------------------------------------
# Pydantic component models
# ---------------------------------------------------------------------------

class ComponentBase(BaseModel):
    id: str
    type: str
    role: Optional[str] = Field(None, description="'input' or 'output'")
    input_speed_rpm: Optional[float] = Field(None)
    input_torque: Optional[float] = Field(None)


class GearComponent(ComponentBase):
    type: str = "gear"
    module: float
    teeth: int
    pressure_angle: Optional[float] = 20.0


class ShaftComponent(ComponentBase):
    type: str = "shaft"
    length: float
    diameter: float


class BoltComponent(ComponentBase):
    type: str = "bolt"
    diameter: float
    length: float
    thread_type: str
    pitch: float


class FlangeComponent(ComponentBase):
    type: str = "flange"
    diameter: float
    thickness: float


class PlateComponent(ComponentBase):
    type: str = "plate"
    length: float
    width: float


class NutComponent(ComponentBase):
    type: str = "nut"
    diameter: float
    thread_type: str
    pitch: float


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
    GearComponent, ShaftComponent, BoltComponent, FlangeComponent,
    PlateComponent, NutComponent, BearingComponent, CouplingComponent,
    BracketComponent, HousingComponent, CylinderComponent, BoxComponent,
    ConeComponent, SphereComponent,
]


class Relationship(BaseModel):
    type: str
    from_id: str
    to_id: str
    distance: Optional[float] = None


class CADPlan(BaseModel):
    components: List[ComponentType]
    relationships: Optional[List[Relationship]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client():
    """Return an initialised OpenAI client, raising clearly if unconfigured."""
    _load_local_env_once()
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "The 'openai' python package is required. Install it with: pip install openai"
        )
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIConfigurationError("OpenAI API key not configured")
    return OpenAI(api_key=api_key)


def is_openai_configured() -> bool:
    """True when the OpenAI API key is available in the process environment."""
    _load_local_env_once()
    return bool(os.getenv("OPENAI_API_KEY"))


_COMPONENT_SCHEMA = """
Supported component types and required fields:
  gear      → module (float), teeth (int), pressure_angle (float, default 20)
  shaft     → length (float), diameter (float)
  bolt      → diameter (float), length (float), thread_type (M/UNC/UNF), pitch (float)
  flange    → diameter (float), thickness (float)
  plate     → length (float), width (float)
  nut       → diameter (float)
  bearing   → inner_diameter (float), outer_diameter (float), width (float)
  coupling  → length (float), diameter (float)
  bracket   → length (float), width (float), height (float)
  housing   → length (float), width (float), height (float)
  cylinder  → radius (float) or diameter (float), height (float)
  box       → length (float), width (float), height (float)
  cone      → diameter (float), height (float)
  sphere    → radius (float)

Relationship types: concentric, flush, offset, mount, fasten, mesh
Every relationship needs: type, from_id, to_id (and optional distance float).
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_cad_plan(
    prompt: str,
    conversation_history: list = None,
) -> dict:
    """
    Call the LLM to extract a structured CAD plan from the user prompt.

    conversation_history: list of {role, content} dicts representing the
    prior turns of this design session (for genuine multi-turn context).
    """
    client = _get_client()

    system_prompt = f"""You are an expert mechanical CAD planning AI managing a stateful design session.
The user is iteratively building or modifying a mechanical assembly across multiple conversation turns.

Your job is to extract mechanical components from the user's latest message and return a structured JSON object.

The JSON must have:
  "components" — a list of component objects
  "relationships" — a list of structural constraints between components

Every component MUST have a unique string "id" (e.g., "gear_1", "shaft_A").
Components can act as mechanical endpoints using the "role" field ("input" or "output").
If role is "input", include "input_speed_rpm" (float) and optionally "input_torque" (float).

{_COMPONENT_SCHEMA}

Example output:
{{
  "components": [
    {{"id": "gear_1", "type": "gear", "module": 2, "teeth": 20, "role": "input", "input_speed_rpm": 1500, "input_torque": 10}},
    {{"id": "gear_2", "type": "gear", "module": 2, "teeth": 40, "role": "output"}}
  ],
  "relationships": [
    {{"type": "mesh", "from_id": "gear_2", "to_id": "gear_1"}}
  ]
}}
"""

    # Build messages: system → prior history → current user prompt
    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        response_format={"type": "json_object"},
    )

    raw_json = response.choices[0].message.content
    data = json.loads(raw_json)

    if "error" in data:
        raise ValueError(f"LLM Plan Error: {data['error']}")

    # Validate with Pydantic
    try:
        plan = CADPlan(**data)
    except ValidationError as e:
        missing = [str(err["loc"][-1]) for err in e.errors() if err["type"] == "missing"]
        if missing and data.get("components"):
            intent = data["components"][0]
            raise MissingParametersError(intent, list(set(missing)))
        raise ValueError(f"LLM generated invalid component parameters: {e}")

    if hasattr(plan, "model_dump"):
        return plan.model_dump(exclude_none=True)
    return plan.dict(exclude_none=True)


def generate_cad_delta(
    prompt: str,
    previous_state: dict,
    conversation_history: list = None,
) -> dict:
    """
    LLM-as-planner: given the current design state and a user intent,
    return ONLY an incremental delta — not the full design graph.

    Uses a compact state summary to avoid token overflow on large assemblies.
    """
    client = _get_client()

    from gear_engineering.core.state_manager import component_summary

    existing_ids = [c.get("id") for c in previous_state.get("components", [])]
    state_summary = component_summary(previous_state)

    system_prompt = f"""You are an expert mechanical CAD design assistant managing a stateful assembly.

CURRENT DESIGN STATE:
{state_summary}

EXISTING COMPONENT IDs (do NOT reuse these): {existing_ids}

Your ONLY job is to interpret the user's request and output a minimal JSON delta.
Do NOT return the full design graph — only what changes.

Output format:
{{
  "action": "add" | "modify" | "remove",
  "components": [ ...only new or changed components... ],
  "relationships": [ ...only new or changed relationships... ],
  "reasoning": "brief explanation"
}}

Rules:
  - "add"    → append new components/relationships to the existing assembly
  - "modify" → change parameters of existing components (reference by exact id)
  - "remove" → remove components by id
  - New component IDs must NOT conflict with existing IDs. Prefix with type + number (e.g. "gear_3").
  - Relationship from_id/to_id must reference valid IDs (existing OR newly added in this delta).

{_COMPONENT_SCHEMA}
"""

    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        response_format={"type": "json_object"},
    )

    raw_json = response.choices[0].message.content
    delta = json.loads(raw_json)

    if "action" not in delta:
        raise ValueError(f"LLM delta missing 'action' field. Raw: {raw_json[:300]}")
    if delta["action"] not in ("add", "modify", "remove"):
        raise ValueError(f"Invalid delta action: {delta['action']}")

    # Validate new components if adding
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
    """
    Targeted extraction of specific numeric/string fields from a user reply.
    Used in the missing-parameter completion flow.
    """
    client = _get_client()

    system_prompt = f"""You are a specialised parameter extraction tool.
Extract the following parameters from the user's text: {missing_fields}.
Return ONLY a flat JSON dictionary with the extracted keys and their float/int values.
Example: {{"length": 120, "diameter": 20}}
Do not invent parameters. Only extract what is clearly specified.
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def generate_primitive_plan(prompt: str) -> dict:
    """
    Fallback planner for basic geometric primitives (cone, cylinder, box, sphere)
    when the primary planner rejects non-mechanical intent.
    """
    client = _get_client()

    system_prompt = """You are a fallback CAD interpreter for basic geometric primitives.
Extract shapes from the prompt and return a JSON object with a "components" list.
No relationships needed. Every component must have a unique "id" (e.g. "cone_1").

Supported types:
  cone      (needs diameter, height)
  cylinder  (needs diameter or radius, height)
  box       (needs length, width, height)
  sphere    (needs radius)
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
