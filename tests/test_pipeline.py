"""
test_pipeline.py
================
Tests for main_pipeline routing logic.
All LLM calls and CadQuery geometry generation are mocked.
"""

import pytest
from unittest.mock import patch, MagicMock
from gear_engineering.main_pipeline import (
    run_agentic_pipeline,
    _is_gearbox_request,
    _deterministic_parse_scoped,
    _validate_and_fill_components,
)
from core.llm_client import MissingParametersError
from gear_engineering.core.state_manager import (
    empty_state, is_parameter_only_input,
)


# ---------------------------------------------------------------------------
# Deterministic parser
# ---------------------------------------------------------------------------

class TestDeterministicParser:
    def test_shaft_extraction(self):
        comps = _deterministic_parse_scoped("Create a shaft 120mm long and 15mm diameter", "shaft")
        assert len(comps) == 1
        assert comps[0]["type"] == "shaft"
        assert comps[0]["length"] == 120.0
        assert comps[0]["diameter"] == 15.0

    def test_gear_extraction(self):
        comps = _deterministic_parse_scoped("I need a module 3 gear with 40 teeth", "gear")
        assert any(c["type"] == "gear" for c in comps)
        gear = next(c for c in comps if c["type"] == "gear")
        assert gear["module"] == 3.0
        assert gear["teeth"] == 40

    def test_bearing_extraction(self):
        comps = _deterministic_parse_scoped("Add a bearing with 20mm inner and 40mm outer", "bearing")
        assert any(c["type"] == "bearing" for c in comps)

    def test_empty_on_unknown(self):
        comps = _deterministic_parse_scoped("I want something nice", None)
        assert comps == []


# ---------------------------------------------------------------------------
# Parameter-only input detection
# ---------------------------------------------------------------------------

class TestParameterOnlyDetector:
    def test_mm_only(self):
        assert is_parameter_only_input("120mm") is True

    def test_mm_long(self):
        assert is_parameter_only_input("120mm long") is True

    def test_rpm_torque(self):
        assert is_parameter_only_input("1500 rpm and 10 Nm") is True

    def test_diameter_prefix(self):
        assert is_parameter_only_input("diameter 20") is True

    def test_design_intent_not_param(self):
        assert is_parameter_only_input("Create a shaft") is False

    def test_gearbox_not_param(self):
        assert is_parameter_only_input("Design a gearbox") is False

    def test_add_gear_not_param(self):
        assert is_parameter_only_input("Add a gear with 30 teeth") is False


# ---------------------------------------------------------------------------
# Validate and fill
# ---------------------------------------------------------------------------

class TestValidateAndFill:
    def test_fills_missing_teeth(self):
        comps = [{"id": "gear_1", "type": "gear", "module": 2}]
        cleaned, warns = _validate_and_fill_components(comps)
        assert cleaned[0]["teeth"] == 20      # default applied
        assert any("teeth" in w for w in warns)

    def test_skips_typeless_component(self):
        comps = [{"id": "mystery", "module": 2}]
        cleaned, warns = _validate_and_fill_components(comps)
        assert len(cleaned) == 0
        assert any("type" in w for w in warns)

    def test_auto_id_generation(self):
        comps = [{"type": "shaft", "length": 50, "diameter": 10}]
        cleaned, _ = _validate_and_fill_components(comps)
        assert cleaned[0].get("id") == "shaft_1"


# ---------------------------------------------------------------------------
# Gearbox routing
# ---------------------------------------------------------------------------

class TestGearboxRouting:
    def test_detects_gearbox_keyword(self):
        assert _is_gearbox_request("Design a 4:1 gearbox") is True
        assert _is_gearbox_request("I need a speed reducer") is True
        assert _is_gearbox_request("Create a shaft") is False

    @patch("gear_engineering.main_pipeline.get_similar_design")
    @patch("gear_engineering.main_pipeline.recompile_assembly")
    @patch("core.gearbox_synthesizer.synthesize_gearbox")
    def test_gearbox_uses_synthesizer_not_llm(
        self, mock_synth, mock_recompile, mock_memory
    ):
        mock_memory.return_value  = {"cached_hits": 0, "plan": None}
        mock_synth.return_value   = {
            "components":    [{"id": "g1", "type": "gear", "module": 2, "teeth": 20}],
            "relationships": [],
            "metadata":      {"target_ratio": 4.0, "actual_ratio": 4.0,
                              "num_stages": 1, "input_speed_rpm": 1500,
                              "input_torque": 10.0},
        }
        mock_recompile.return_value = {"status": "success", "components": []}

        run_agentic_pipeline("Design a 4:1 gearbox at 1500 RPM with 10 Nm")

        # synthesize_gearbox must have been called
        mock_synth.assert_called_once()
        # No LLM call should have happened
        with patch("core.llm_client.generate_cad_plan") as mock_llm:
            mock_llm.assert_not_called()

    def test_missing_ratio_triggers_missing_params(self):
        with patch("gear_engineering.main_pipeline.get_similar_design",
                   return_value={"cached_hits": 0, "plan": None}):
            result = run_agentic_pipeline("I need a gearbox")
        assert result["status"] == "question"
        assert any("ratio" in f.lower() for f in result["missing"])


# ---------------------------------------------------------------------------
# Parameter completion flow (PATH A)
# ---------------------------------------------------------------------------

class TestParameterCompletionFlow:
    @patch("gear_engineering.main_pipeline.get_similar_design")
    @patch("gear_engineering.main_pipeline.recompile_assembly")
    @patch("core.llm_client.generate_cad_plan")
    def test_missing_param_returned(self, mock_plan, mock_recompile, mock_memory):
        mock_memory.return_value = {"cached_hits": 0, "plan": None}
        mock_plan.side_effect = MissingParametersError(
            intent={"type": "gear", "id": "gear_1"},
            missing_fields=["module", "teeth"],
        )
        result = run_agentic_pipeline("Create a gear with 20 teeth")
        assert result["status"] == "question"
        assert "module" in result["missing"]
        assert "question" in result

    @patch("gear_engineering.main_pipeline.recompile_assembly")
    def test_completion_path_merges_intent(self, mock_recompile):
        mock_recompile.return_value = {"status": "success", "components": []}

        last_intent = {"type": "gear", "id": "gear_1"}
        result = run_agentic_pipeline(
            "module 2.5 and 35 teeth",
            pending_parameters=["module", "teeth"],
            last_failed_intent=last_intent,
        )
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Continuation flow (PATH B)
# ---------------------------------------------------------------------------

class TestContinuationFlow:
    @patch("core.llm_client.generate_cad_delta")
    @patch("gear_engineering.main_pipeline.recompile_assembly")
    def test_continuation_delta_merged(self, mock_recompile, mock_delta):
        previous_state = {
            "components":    [{"id": "shaft_1", "type": "shaft",
                               "length": 50, "diameter": 10}],
            "relationships": [],
            "metadata":      {},
        }
        mock_delta.return_value = {
            "action":        "add",
            "components":    [{"id": "gear_1", "type": "gear",
                               "module": 2, "teeth": 20}],
            "relationships": [{"type": "concentric",
                               "from_id": "gear_1", "to_id": "shaft_1"}],
            "reasoning":     "Adding a gear to the shaft.",
        }
        mock_recompile.return_value = {"status": "success", "components": []}

        result = run_agentic_pipeline(
            "Add a module 2 gear with 20 teeth to the shaft",
            previous_state=previous_state,
        )

        assert result["status"] == "success"
        args, _ = mock_recompile.call_args
        merged = args[0]
        comp_ids = [c["id"] for c in merged["components"]]
        assert "shaft_1" in comp_ids
        assert "gear_1"  in comp_ids
        assert len(merged["relationships"]) == 1

    @patch("core.llm_client.generate_cad_delta")
    @patch("gear_engineering.main_pipeline.recompile_assembly")
    def test_parameter_only_follow_up_merged(self, mock_recompile, mock_delta):
        """'120mm long' after an existing design should be merged, not treated fresh."""
        previous_state = {
            "components":    [{"id": "shaft_1", "type": "shaft",
                               "length": 50, "diameter": 10}],
            "relationships": [],
            "metadata":      {},
            "last_intent":   {"id": "shaft_1", "type": "shaft"},
        }
        mock_delta.return_value = {
            "action":        "modify",
            "components":    [{"id": "shaft_1", "length": 120}],
            "relationships": [],
            "reasoning":     "Updating shaft length to 120mm.",
        }
        mock_recompile.return_value = {"status": "success", "components": []}

        # '120mm' is parameter-only → should go through continuation (delta)
        result = run_agentic_pipeline(
            "120mm",
            previous_state=previous_state,
        )
        assert result["status"] == "success"
        # Delta generator should have been called (not fresh plan)
        mock_delta.assert_called_once()
