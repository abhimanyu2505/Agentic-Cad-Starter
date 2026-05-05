import pytest
from gear_engineering.core.gearbox_synthesizer import synthesize_gearbox

def test_gearbox_4to1_generation():
    result = synthesize_gearbox(
        target_ratio=4.0,
        input_speed_rpm=1500,
        input_torque=10.0,
        max_stages=3
    )
    
    # Check shape
    assert "components" in result
    assert "relationships" in result
    assert "metadata" in result
    
    # 4:1 usually done in 1 stage
    assert result["metadata"]["num_stages"] == 1
    
    # Check actual ratio within tolerance
    actual = result["metadata"]["actual_ratio"]
    assert abs(actual - 4.0) < 0.2
    
    # Verify input speed and torque
    assert result["metadata"]["input_speed_rpm"] == 1500
    assert result["metadata"]["input_torque"] == 10.0

def test_gearbox_multistage():
    # 20:1 ratio should trigger multi-stage
    result = synthesize_gearbox(
        target_ratio=20.0,
        input_speed_rpm=3000,
        input_torque=5.0,
        max_stages=3
    )
    
    # Should take 2 stages for 20:1
    assert result["metadata"]["num_stages"] >= 2
    
    actual = result["metadata"]["actual_ratio"]
    assert abs(actual - 20.0) < 1.0  # Allow some tolerance for integer teeth

    # Verify input gear has role
    comps = result["components"]
    inputs = [c for c in comps if c.get("role") == "input"]
    outputs = [c for c in comps if c.get("role") == "output"]
    
    assert len(inputs) == 1
    assert len(outputs) == 1
