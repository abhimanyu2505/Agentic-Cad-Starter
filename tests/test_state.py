import pytest
from gear_engineering.core.state_manager import empty_state, from_dict
from gear_engineering.core.state_merger import apply_delta

def test_empty_state():
    state = empty_state()
    assert state["components"] == []
    assert state["relationships"] == []
    assert state["metadata"] == {}
    assert state["conversation_history"] == []

def test_apply_delta_add():
    state = empty_state()
    delta = {
        "action": "add",
        "components": [{"id": "gear_1", "type": "gear", "module": 2, "teeth": 20}],
        "relationships": []
    }
    
    new_state = apply_delta(state, delta)
    assert len(new_state["components"]) == 1
    assert new_state["components"][0]["id"] == "gear_1"
    
    # Ensure original state unchanged
    assert len(state["components"]) == 0

def test_apply_delta_modify():
    state = {
        "components": [{"id": "gear_1", "type": "gear", "module": 2, "teeth": 20}],
        "relationships": [],
        "metadata": {}
    }
    delta = {
        "action": "modify",
        "components": [{"id": "gear_1", "teeth": 40}],
        "relationships": []
    }
    
    new_state = apply_delta(state, delta)
    assert len(new_state["components"]) == 1
    assert new_state["components"][0]["teeth"] == 40
    # Type should be preserved
    assert new_state["components"][0]["type"] == "gear"

def test_apply_delta_remove():
    state = {
        "components": [
            {"id": "gear_1", "type": "gear"},
            {"id": "shaft_1", "type": "shaft"}
        ],
        "relationships": [
            {"type": "concentric", "from_id": "gear_1", "to_id": "shaft_1"}
        ],
        "metadata": {}
    }
    delta = {
        "action": "remove",
        "components": [{"id": "gear_1"}],
        "relationships": []
    }
    
    new_state = apply_delta(state, delta)
    assert len(new_state["components"]) == 1
    assert new_state["components"][0]["id"] == "shaft_1"
    # Relationship should be removed automatically because gear_1 is gone
    assert len(new_state["relationships"]) == 0

def test_dangling_relationship_pruning():
    state = {
        "components": [{"id": "gear_1", "type": "gear"}],
        "relationships": [],
        "metadata": {}
    }
    delta = {
        "action": "add",
        "components": [],
        "relationships": [
            {"type": "mesh", "from_id": "gear_1", "to_id": "ghost_gear"}
        ]
    }
    
    new_state = apply_delta(state, delta)
    # The dangling relationship to 'ghost_gear' should be pruned during validation
    assert len(new_state["relationships"]) == 0
