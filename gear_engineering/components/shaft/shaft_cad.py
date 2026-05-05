import cadquery as cq

def generate_component(parameters: dict):
    """
    Standardized component generation interface for Shaft CAD.
    Expects params: length, diameter.

    Geometry produced:
      - Cylindrical shaft body extruded along +Z.
      - Longitudinal keyway slot cut from the +Y surface along the full shaft
        length, with proportions derived from shaft diameter:
          key_width  = diameter * 0.25
          key_depth  = diameter * 0.125
      - Terminal face chamfer applied to the top circular arc only (>Z face),
        restricted via the '%Circle' edge selector to avoid the keyway's
        longitudinal corner edges which can cause OCCT topological faults.
      - Debug STEP export: debug_keyway_shaft.step
    """
    length   = parameters.get("length")
    diameter = parameters.get("diameter", 20.0)

    if length is None:
        raise ValueError("Critical Parameter Missing: Shaft requires specified length.")

    radius = diameter / 2.0
    print(f"[shaft_cad] Generating shaft: length={length:.2f}mm, diameter={diameter:.2f}mm")

    # ── 1. Base cylindrical shaft ──────────────────────────────────────────────
    shaft_solid = cq.Workplane("XY").circle(radius).extrude(length)

    # ── 2. Keyway boolean cut ─────────────────────────────────────────────────
    # Slot runs the full shaft length, centered on the +Y surface.
    # On XZ workplane: X is lateral width, Z is axial direction.
    # Extrude goes in +Y; translate seats the tool flush at the surface
    # so it cuts key_depth into the body.
    key_width = diameter * 0.25
    key_depth = diameter * 0.125
    print(f"[shaft_cad] Keyway dims: width={key_width:.3f}mm, depth={key_depth:.3f}mm (axis: +Y surface)")

    keyway_tool = (
        cq.Workplane("XZ")
        .center(0, length / 2.0)                # center axially
        .rect(key_width, length)                # full-length span in Z
        .extrude(key_depth)                     # extrude +Y (toward bore surface)
        .translate((0, radius - key_depth, 0))  # seat at shaft OD, cut inward
    )
    shaft_solid = shaft_solid.cut(keyway_tool)
    print("[shaft_cad] Keyway boolean cut applied.")

    # ── 3. Selective chamfer — terminal circular arc, top face only ───────────
    # '%Circle' restricts selection to circular arc edges on the >Z face,
    # explicitly excluding the keyway's longitudinal straight edges that run
    # parallel to Z. Those parallel edges (the '|Z' set) are topologically
    # unstable for chamfering after the boolean subtraction.
    chamfer_dist = round(diameter * 0.05, 3)
    try:
        shaft_solid = shaft_solid.faces(">Z").edges("%Circle").chamfer(chamfer_dist)
        print(f"[shaft_cad] Terminal face chamfer applied: {chamfer_dist:.3f}mm on >Z circular arc.")
    except Exception as exc:
        print(f"[shaft_cad] Chamfer skipped (kernel rejected): {exc}")

    # ── 4. Debug STEP export ───────────────────────────────────────────────────
    debug_path = "debug_keyway_shaft.step"
    cq.exporters.export(shaft_solid, debug_path)
    print(f"[shaft_cad] Debug export written → {debug_path}")

    return shaft_solid
