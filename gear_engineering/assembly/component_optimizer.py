"""
Component Optimizer: Deduplicates and trims the component list before rendering.

Rules:
- Remove components with the same (type, key_dimensions) fingerprint
- Limit bearings to max 2 per parent shaft
- Preserve IDs of the first-seen component to keep relationships valid
"""

from utils.logger import log


def _fingerprint(comp: dict) -> tuple:
    """Create a deduplication key based on type + dimensional parameters."""
    t = comp.get("type", "unknown")
    if t == "gear":
        return (t, comp.get("module", 0), comp.get("teeth", 0))
    elif t == "shaft":
        return (t, round(comp.get("diameter", 0), 1), round(comp.get("length", 0), 1))
    elif t == "bearing":
        return (t, round(comp.get("inner_diameter", 0), 1), round(comp.get("outer_diameter", 0), 1))
    elif t in ("flange", "plate"):
        return (t, round(comp.get("diameter", comp.get("length", 0)), 1))
    elif t == "housing":
        return (t, round(comp.get("length", 0), 1), round(comp.get("width", 0), 1))
    else:
        return (t, str(sorted(
            {k: v for k, v in comp.items() if k not in ("id", "type", "role")}.items()
        )))


def optimize_components(components: list, relationships: list) -> tuple:
    """
    Deduplicate the component list and enforce bearing limits per shaft.

    Returns:
        (optimized_components, optimized_relationships, id_remap)
        id_remap maps removed duplicate IDs → the surviving canonical ID,
        so relationships can be rewritten.
    """
    seen: dict = {}        # fingerprint → canonical_id
    id_remap: dict = {}    # removed_id → canonical_id
    kept: list = []

    # ── 1. Deduplicate by fingerprint ─────────────────────────────────────────
    for comp in components:
        fp = _fingerprint(comp)
        cid = comp.get("id", "")
        if fp in seen:
            canonical = seen[fp]
            id_remap[cid] = canonical
            log("optimizer", f"Duplicate {comp['type']} '{cid}' → merged into '{canonical}'")
        else:
            seen[fp] = cid
            kept.append(comp)

    # ── 2. Limit bearings to 2 per shaft ─────────────────────────────────────
    shaft_bearing_count: dict = {}   # shaft_id → count of bearings kept

    # Build shaft→bearing map from relationships of kept components
    kept_ids = {c["id"] for c in kept}
    bearing_parent: dict = {}   # bearing_id → shaft_id
    for rel in relationships:
        if rel.get("type") in ("concentric", "mount"):
            f, t = rel.get("from_id", ""), rel.get("to_id", "")
            fcomp = next((c for c in kept if c["id"] == f), None)
            tcomp = next((c for c in kept if c["id"] == t), None)
            if fcomp and tcomp:
                if fcomp.get("type") == "bearing" and tcomp.get("type") == "shaft":
                    bearing_parent[f] = t
                elif tcomp.get("type") == "bearing" and fcomp.get("type") == "shaft":
                    bearing_parent[t] = f

    pruned_bearings: set = set()
    final_kept: list = []
    for comp in kept:
        if comp.get("type") == "bearing":
            parent = bearing_parent.get(comp["id"])
            if parent:
                shaft_bearing_count[parent] = shaft_bearing_count.get(parent, 0) + 1
                if shaft_bearing_count[parent] > 2:
                    # Prune this excess bearing
                    pruned_bearings.add(comp["id"])
                    log("optimizer", f"Pruned excess bearing '{comp['id']}' on shaft '{parent}' (limit=2)")
                    continue
        final_kept.append(comp)

    # ── 3. Rewrite relationships ──────────────────────────────────────────────
    final_rels = []
    final_ids = {c["id"] for c in final_kept}
    for rel in relationships:
        f = id_remap.get(rel.get("from_id"), rel.get("from_id"))
        t = id_remap.get(rel.get("to_id"), rel.get("to_id"))
        # Skip if either endpoint was pruned
        if f not in final_ids or t not in final_ids:
            continue
        if f == t:
            continue   # self-loop after remap
        new_rel = dict(rel)
        new_rel["from_id"] = f
        new_rel["to_id"] = t
        final_rels.append(new_rel)

    log("optimizer", f"Optimization: {len(components)} → {len(final_kept)} components, "
                     f"{len(relationships)} → {len(final_rels)} relationships")
    return final_kept, final_rels, id_remap
