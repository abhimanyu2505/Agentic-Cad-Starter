from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
GEAR_DIR = ROOT_DIR / "gear_engineering"
if str(GEAR_DIR) not in sys.path:
    sys.path.insert(0, str(GEAR_DIR))


def _load_local_env_once() -> None:
    if os.getenv("OPENAI_API_KEY"):
        return
    for rel_path in (".env", os.path.join("gear_engineering", ".env")):
        env_path = ROOT_DIR / rel_path
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "OPENAI_API_KEY" and not os.getenv(key.strip()):
                os.environ[key.strip()] = value.strip().strip('"').strip("'")
                return


_load_local_env_once()

from backend.app.session import OUTPUTS_DIR, SESSION


class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


class ModifyRequest(BaseModel):
    component_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    prompt: Optional[str] = None


app = FastAPI(title="Agentic CAD API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUTS_DIR.mkdir(exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/state")
def get_state() -> Dict[str, Any]:
    return SESSION.serialize()


@app.post("/generate")
def generate(request: PromptRequest) -> Dict[str, Any]:
    SESSION.run_generate(request.prompt)
    return SESSION.serialize()


@app.post("/modify")
def modify(request: ModifyRequest) -> Dict[str, Any]:
    SESSION.run_modify(request.component_id, request.parameters, request.prompt)
    return SESSION.serialize()
