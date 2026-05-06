from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Optional, Dict, List

from gear_engineering.core.state_manager import add_message, empty_state, from_dict
from gear_engineering.main_pipeline import recompile_assembly, run_agentic_pipeline


ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = ROOT_DIR / "outputs"


class DesignSession:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.design_state = empty_state()
        self.messages: List[Dict[str, Any]] = []
        self.pending_parameters: Optional[List[str]] = None
        self.last_failed_intent: Optional[Dict[str, Any]] = None
        self.clarification_options: List[str] = []
        self.clarification_type: Optional[str] = None
        self.pipeline_result: Optional[Dict[str, Any]] = None

    def snapshot(self) -> Dict[str, Any]:
        return {
            "design_state": copy.deepcopy(self.design_state),
            "messages": copy.deepcopy(self.messages),
            "pending_parameters": copy.deepcopy(self.pending_parameters),
            "last_failed_intent": copy.deepcopy(self.last_failed_intent),
            "clarification_options": copy.deepcopy(self.clarification_options),
            "clarification_type": self.clarification_type,
            "pipeline_result": copy.deepcopy(self.pipeline_result),
        }

    def restore(self, snapshot: Dict[str, Any]) -> None:
        self.design_state = from_dict(snapshot["design_state"])
        self.messages = copy.deepcopy(snapshot["messages"])
        self.pending_parameters = copy.deepcopy(snapshot["pending_parameters"])
        self.last_failed_intent = copy.deepcopy(snapshot["last_failed_intent"])
        self.clarification_options = copy.deepcopy(snapshot["clarification_options"])
        self.clarification_type = snapshot["clarification_type"]
        self.pipeline_result = copy.deepcopy(snapshot["pipeline_result"])

    def _asset_url_map(self, glb_paths: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        assets: Dict[str, Any] = {}
        for comp_id, info in (glb_paths or {}).items():
            path = info.get("path")
            if not path:
                continue
            filename = Path(path).name
            assets[comp_id] = {
                "type": info.get("type"),
                "path": path,
                "url": f"/outputs/{filename}",
            }
        return assets

    def serialize(self) -> Dict[str, Any]:
        result = self.pipeline_result or {}
        return {
            "design_state": copy.deepcopy(self.design_state),
            "messages": copy.deepcopy(self.messages),
            "pending_parameters": copy.deepcopy(self.pending_parameters),
            "last_failed_intent": copy.deepcopy(self.last_failed_intent),
            "clarification_options": copy.deepcopy(self.clarification_options),
            "clarification_type": self.clarification_type,
            "pipeline_result": copy.deepcopy(result),
            "viewer_assets": self._asset_url_map(result.get("glb_paths")),
        }

    def apply_pipeline_result(self, result: Dict[str, Any]) -> None:
        existing_history = self.design_state.get("conversation_history", [])
        self.design_state = from_dict({
            "components": result.get("components", []),
            "relationships": result.get("relationships", []),
            "metadata": result.get("metadata", {}),
            "conversation_history": existing_history,
            "last_intent": self.design_state.get("last_intent"),
            "current_task": self.design_state.get("current_task"),
        })
        self.pipeline_result = result
        self.pending_parameters = None
        self.last_failed_intent = None
        self.clarification_options = []
        self.clarification_type = None

    def run_generate(self, prompt: str) -> Dict[str, Any]:
        self.messages.append({"role": "user", "content": prompt})
        add_message(self.design_state, "user", prompt)

        result = run_agentic_pipeline(
            prompt,
            previous_state=self.design_state,
            pending_parameters=self.pending_parameters,
            last_failed_intent=self.last_failed_intent,
            conversation_history=self.design_state.get("conversation_history", []),
            generation_mode=self.design_state.get("metadata", {}).get("generation_mode", "minimal"),
            clarification_choice=None,
        )

        status = result.get("status")
        if status == "success":
            n_comp = len(result.get("components", []))
            reply = f"Generated {n_comp} component(s)." if n_comp else "No geometry was generated."
            self.messages.append({"role": "assistant", "content": reply})
            add_message(self.design_state, "assistant", reply)
            self.apply_pipeline_result(result)
        elif status in ("question", "missing_parameters"):
            missing_fields = result.get("missing", result.get("missing_fields", []))
            question = result.get("question") or f"Please provide: {', '.join(missing_fields)}."
            self.pending_parameters = missing_fields
            self.last_failed_intent = result.get("intent")
            self.messages.append({"role": "assistant", "content": question, "is_question": True})
            add_message(self.design_state, "assistant", question)
        elif status == "clarification":
            self.clarification_options = result.get("options", [])
            self.clarification_type = result.get("type")
            message = result.get("message", "Please clarify your intent.")
            self.messages.append({"role": "assistant", "content": message})
            add_message(self.design_state, "assistant", message)
        else:
            error_message = result.get("message", "Unknown error.")
            self.messages.append({"role": "error", "content": error_message})

        self.pipeline_result = result
        return result

    def run_modify(self, component_id: Optional[str], parameters: Optional[Dict[str, Any]], prompt: Optional[str]) -> Dict[str, Any]:
        if prompt:
            return self.run_generate(prompt)

        if not component_id or not parameters:
            result = {"status": "error", "message": "Modify requires a component_id and parameters."}
            self.pipeline_result = result
            return result

        components = self.design_state.get("components", [])
        target = next((comp for comp in components if comp.get("id") == component_id), None)
        if target is None:
            result = {"status": "error", "message": f"Component '{component_id}' was not found."}
            self.pipeline_result = result
            return result

        target.update(parameters)
        if target.get("type") == "gear" and "thickness" in parameters:
            target["face_width"] = parameters["thickness"]

        result = recompile_assembly(self.design_state, "api_modify")
        if result.get("status") == "success":
            self.apply_pipeline_result(result)
        self.pipeline_result = result
        return result


SESSION = DesignSession()
