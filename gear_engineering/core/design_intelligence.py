from typing import Dict, List, Tuple

def validate_cad_plan(plan: Dict) -> Tuple[Dict, List[str]]:
    """
    Validates the mechanical feasibility of components in the CAD plan.
    Does not silently adjust; generates warnings to prompt the user.
    """
    warnings = []
    components = plan.get("components", [])
    
    for comp in components:
        comp_type = comp.get("type", "")
        
        if comp_type == "gear":
            teeth = comp.get("teeth", 0)
            if teeth < 12:
                warnings.append(f"Gear Warning: {teeth} teeth is less than the standard 12 minimum. May cause undercutting.")
                
        elif comp_type == "shaft":
            length = comp.get("length", 0)
            diameter = comp.get("diameter", 0)
            if diameter > 0:
                ratio = length / diameter
                if ratio > 20:
                    warnings.append(f"Shaft Warning: Length/Diameter ratio ({ratio:.1f}) exceeds 20:1. High risk of deflection.")
                
                # Shaft Failure / Torque Overload Check
                # Assuming typical steel shear strength ~50 MPa (N/mm^2).
                # Max Torque (N*m) = (pi * d^3 * tau) / 16
                # tau = (16 * T) / (pi * d^3)
                torque_nm = comp.get("input_torque") or comp.get("output_torque_nm") or plan.get("metadata", {}).get("output_torque_nm", 0)
                if torque_nm:
                    # Convert diameter mm to m for formula
                    d_m = diameter / 1000.0
                    import math
                    shear_stress_pa = (16.0 * float(torque_nm)) / (math.pi * (d_m ** 3))
                    shear_stress_mpa = shear_stress_pa / 1_000_000.0
                    if shear_stress_mpa > 50.0:
                        warnings.append(f"Engineering Alert: Torque overload ({torque_nm:.1f} Nm). Calculated shear stress is {shear_stress_mpa:.1f} MPa on {diameter}mm shaft. High risk of shaft failure!")
            else:
                warnings.append("Shaft Warning: Diameter must be greater than 0.")
                
        elif comp_type == "bolt":
            # Simple clearance check placeholder if hole diameter is known
            pass
            
    # Validate Roles
    inputs = [c for c in components if c.get("role") == "input"]
    outputs = [c for c in components if c.get("role") == "output"]
    
    if len(inputs) == 0:
        warnings.append("System Warning: No 'input' component defined. System will be statically kinematic.")
    elif len(inputs) > 1:
        warnings.append("System Warning: Multiple 'input' components defined. This may cause ambiguous kinematic propagation.")
        
    if len(outputs) == 0:
        warnings.append("System Warning: No 'output' component defined. System has no driven payload.")
            
    # Validate Relationships
    relationships = plan.get("relationships", [])
    comp_map = {c.get("id"): c for c in components if "id" in c}
    
    for rel in relationships:
        if rel.get("type") == "mesh":
            from_id = rel.get("from_id")
            to_id = rel.get("to_id")
            
            comp1 = comp_map.get(from_id)
            comp2 = comp_map.get(to_id)
            
            if not comp1 or not comp2:
                continue
                
            if comp1.get("type") != "gear" or comp2.get("type") != "gear":
                warnings.append(f"Mesh Warning: Cannot mesh '{from_id}' and '{to_id}'. Both must be gears.")
                continue
                
            m1 = comp1.get("module", 2.0)
            m2 = comp2.get("module", 2.0)
            
            if abs(m1 - m2) > 0.001:
                warnings.append(f"Mesh Warning: Incompatible gear modules (M{m1} vs M{m2}). Gears will mechanically jam.")
            
    # Validate Gear Ratio Accuracy (synthesis path)
    metadata = plan.get("metadata", {})
    target_ratio = metadata.get("target_ratio")
    ratio_error_pct = metadata.get("ratio_error_pct")
    
    if target_ratio is not None and ratio_error_pct is not None:
        if ratio_error_pct > 2.0:
            warnings.append(
                f"Ratio Accuracy Warning: Synthesized ratio achieves {metadata.get('actual_ratio'):.4f}:1 "
                f"against target {target_ratio}:1 — error is {ratio_error_pct:.2f}%. "
                f"Consider relaxing max_gear_teeth constraint for a closer match."
            )
        else:
            # Print informational summary — not a warning, just telemetry
            print(f"\n[SYNTHESIS RESULT]")
            print(f"  Target ratio   : {target_ratio}:1")
            print(f"  Actual ratio   : {metadata.get('actual_ratio')}:1  ({ratio_error_pct}% error)")
            print(f"  Output speed   : {metadata.get('output_speed_rpm')} RPM")
            print(f"  Output torque  : {metadata.get('output_torque_nm')} Nm")
            print(f"  Stages         : {metadata.get('num_stages')}")
            
    return plan, warnings
