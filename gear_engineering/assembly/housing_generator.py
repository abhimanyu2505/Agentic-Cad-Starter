import cadquery as cq
from utils.logger import log

def generate_housing(assembly: cq.Assembly, clearance_mm: float = 3.0, wall_thickness: float = 5.0) -> cq.Workplane:
    """
    Generates a mechanically realistic housing enclosure based on the global
    bounding box of the fully assembled system.
    """
    log("housing", "Computing global bounding box for housing generation...")
    
    # Convert assembly to compound to compute global bounding box
    try:
        compound = assembly.toCompound()
        bb = compound.BoundingBox()
    except Exception as e:
        log("error", f"Failed to compute global bounding box: {e}")
        return None

    # Calculate dimensions
    inner_dx = bb.xlen + (clearance_mm * 2)
    inner_dy = bb.ylen + (clearance_mm * 2)
    inner_dz = bb.zlen + (clearance_mm * 2)

    outer_dx = inner_dx + (wall_thickness * 2)
    outer_dy = inner_dy + (wall_thickness * 2)
    outer_dz = inner_dz + (wall_thickness * 2)
    
    # Center of the bounding box
    cx = (bb.xmin + bb.xmax) / 2.0
    cy = (bb.ymin + bb.ymax) / 2.0
    cz = (bb.zmin + bb.zmax) / 2.0

    log("housing", f"Housing dims: Outer({outer_dx:.1f}x{outer_dy:.1f}x{outer_dz:.1f}), Inner({inner_dx:.1f}x{inner_dy:.1f}x{inner_dz:.1f})")

    # Generate outer box
    housing_solid = (
        cq.Workplane("XY")
        .box(outer_dx, outer_dy, outer_dz)
    )
    
    # Subtract inner cavity
    cavity = (
        cq.Workplane("XY")
        .box(inner_dx, inner_dy, inner_dz)
    )
    
    housing_solid = housing_solid.cut(cavity)
    
    # Translate to match assembly center
    housing_solid = housing_solid.translate((cx, cy, cz))
    
    import os
    os.makedirs("outputs", exist_ok=True)
    
    # Export debug STEP
    debug_step_path = "outputs/debug_housing.step"
    glb_path = "outputs/housing.glb"
    try:
        cq.exporters.export(housing_solid, debug_step_path)
        log("housing", f"Exported housing STEP to {debug_step_path}")
        # Export GLB for the GUI viewer
        import trimesh, trimesh.exchange.gltf as tgltf
        stl_tmp = "outputs/housing_tmp.stl"
        cq.exporters.export(housing_solid, stl_tmp)
        mesh = trimesh.load(stl_tmp, force='mesh')
        try:
            mesh = mesh.simplify_quadratic_decimation(50000)
        except Exception:
            pass  # Simplification unavailable, use original mesh
        glb_data = tgltf.export_glb(trimesh.Scene([mesh]))
        with open(glb_path, "wb") as f:
            f.write(glb_data)
        log("housing", f"Exported housing GLB to {glb_path}")
    except Exception as e:
        log("error", f"Failed to export housing: {e}")

    return housing_solid
