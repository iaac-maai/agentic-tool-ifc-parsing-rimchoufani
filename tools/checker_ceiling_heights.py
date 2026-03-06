"""
IFC Compliance Checker - Ceiling Heights
Checks that spaces (rooms) meet minimum ceiling height requirements (>= 2500 mm).

Strategy (in priority order, all values converted to mm via project unit scale):
1. Pset_SpaceCommon.Height
2. Qto_SpaceBaseQuantities.Height
3. PSet_Revit_Dimensions.Unbounded Height  (Revit-exported IFC)
4. PSet_Revit_Constraints.Limit Offset     (Revit ceiling offset, fallback)
5. IfcBuildingStorey elevation difference  (last resort)
"""

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.unit


def check_ceiling_heights(
    model: ifcopenshell.file,
    min_height_mm: float = 2500.0,
    **kwargs,
) -> list[dict]:
    """
    Checks each IfcSpace for a minimum ceiling height (default: 2500 mm).

    For each space:
      - Height >= min_height_mm  → pass
      - Height <  min_height_mm  → fail
      - Height cannot be found   → warning (cannot verify)

    A summary row is appended at the end.

    Args:
        model: An ifcopenshell.file object representing the IFC model.
        min_height_mm: Minimum required ceiling height in millimetres (default 2500).

    Returns:
        List of result dicts following the required schema.
    """
    results = []
    spaces = model.by_type("IfcSpace")

    passed = 0
    failed = 0
    warnings = 0

    # Unit scale: multiply model values by this to get metres, then × 1000 → mm.
    unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)  # metres per model unit
    to_mm = unit_scale * 1000.0

    # Build a storey-height lookup from IfcBuildingStorey elevations (mm).
    # Used as a fallback when a space has no explicit height property.
    storey_heights = _compute_storey_heights(model, to_mm)

    # Map space → containing storey for the fallback lookup.
    space_to_storey = _map_spaces_to_storeys(model)

    for space in spaces:
        element_id = space.GlobalId
        element_name = space.Name or f"Space #{space.id()}"
        element_name_long = getattr(space, "LongName", None)

        height_mm, source = _get_space_height(model, space, space_to_storey, storey_heights, to_mm)

        if height_mm is None:
            status = "warning"
            actual = "Not found"
            comment = (
                "Ceiling height could not be determined. "
                "No Height property or quantity found, and no storey height available."
            )
            log = "Checked Pset_SpaceCommon.Height, Qto_SpaceBaseQuantities.Height, storey elevation diff."
            warnings += 1
        elif height_mm >= min_height_mm:
            status = "pass"
            actual = f"{height_mm:.0f} mm"
            comment = None
            log = f"Height source: {source}"
            passed += 1
        else:
            status = "fail"
            actual = f"{height_mm:.0f} mm"
            comment = (
                f"Ceiling too low: {height_mm:.0f} mm < required {min_height_mm:.0f} mm."
            )
            log = f"Height source: {source}"
            failed += 1

        results.append({
            "element_id": element_id,
            "element_type": "IfcSpace",
            "element_name": element_name,
            "element_name_long": element_name_long,
            "check_status": status,
            "actual_value": actual,
            "required_value": f">= {min_height_mm:.0f} mm",
            "comment": comment,
            "log": log,
        })

    # --- Summary row ---
    total = len(spaces)
    if total == 0:
        summary_status = "warning"
        summary_comment = "No IfcSpace elements found in the model."
    elif failed > 0:
        summary_status = "fail"
        summary_comment = f"{failed}/{total} space(s) do not meet the minimum ceiling height."
    elif warnings > 0:
        summary_status = "warning"
        summary_comment = (
            f"{warnings}/{total} space(s) have no height data; manual review recommended."
        )
    else:
        summary_status = "pass"
        summary_comment = f"All {total} space(s) meet the minimum ceiling height requirement."

    results.append({
        "element_id": None,
        "element_type": "Summary",
        "element_name": "Ceiling Height Check",
        "element_name_long": None,
        "check_status": summary_status,
        "actual_value": f"{passed} pass / {failed} fail / {warnings} warning",
        "required_value": f"All spaces >= {min_height_mm:.0f} mm high",
        "comment": summary_comment,
        "log": None,
    })

    return results


# =============================================================================
# Helpers
# =============================================================================

def _get_space_height(model, space, space_to_storey, storey_heights, to_mm):
    """
    Returns (height_mm, source_description) for a space, or (None, None).

    Priority:
      1. Pset_SpaceCommon.Height
      2. Qto_SpaceBaseQuantities.Height
      3. PSet_Revit_Dimensions.Unbounded Height  (Revit IFC export)
      4. PSet_Revit_Constraints.Limit Offset     (Revit ceiling offset)
      5. Containing storey height (elevation diff)
    """
    psets = ifcopenshell.util.element.get_psets(space)

    def _scaled(value):
        return float(value) * to_mm

    # 1. Pset_SpaceCommon.Height
    height = psets.get("Pset_SpaceCommon", {}).get("Height")
    if height is not None:
        try:
            return _scaled(height), "Pset_SpaceCommon.Height"
        except (TypeError, ValueError):
            pass

    # 2. Qto_SpaceBaseQuantities.Height
    height = psets.get("Qto_SpaceBaseQuantities", {}).get("Height")
    if height is not None:
        try:
            return _scaled(height), "Qto_SpaceBaseQuantities.Height"
        except (TypeError, ValueError):
            pass

    # 3. PSet_Revit_Dimensions.Unbounded Height (Revit-exported IFC)
    height = psets.get("PSet_Revit_Dimensions", {}).get("Unbounded Height")
    if height is not None:
        try:
            return _scaled(height), "PSet_Revit_Dimensions.Unbounded Height"
        except (TypeError, ValueError):
            pass

    # 4. PSet_Revit_Constraints.Limit Offset (ceiling offset from level)
    height = psets.get("PSet_Revit_Constraints", {}).get("Limit Offset")
    if height is not None:
        try:
            return _scaled(height), "PSet_Revit_Constraints.Limit Offset"
        except (TypeError, ValueError):
            pass

    # 5. Fallback: storey height from elevation diff (already in mm)
    storey = space_to_storey.get(space.id())
    if storey is not None:
        h = storey_heights.get(storey.id())
        if h is not None:
            return h, "IfcBuildingStorey elevation difference"

    return None, None


def _compute_storey_heights(model, to_mm):
    """
    Build a dict {storey_id: height_mm} from IfcBuildingStorey Elevation differences.

    Storeys are sorted by Elevation; each storey's height is the gap to the next one.
    The topmost storey gets no entry (unknown height).
    """
    storeys = model.by_type("IfcBuildingStorey")
    if not storeys:
        return {}

    valid = []
    for s in storeys:
        elev = getattr(s, "Elevation", None)
        if elev is not None:
            try:
                valid.append((float(elev), s))
            except (TypeError, ValueError):
                pass

    valid.sort(key=lambda x: x[0])

    heights = {}
    for i, (elev, storey) in enumerate(valid):
        if i + 1 < len(valid):
            next_elev = valid[i + 1][0]
            heights[storey.id()] = (next_elev - elev) * to_mm
        # Top storey: no height info from elevation alone

    return heights


def _map_spaces_to_storeys(model):
    """
    Returns a dict {space_id: storey} mapping each IfcSpace to its containing storey
    via IfcRelAggregates or IfcRelContainedInSpatialStructure relationships.
    """
    mapping = {}

    # IfcRelContainedInSpatialStructure
    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        structure = rel.RelatingStructure
        if not structure.is_a("IfcBuildingStorey"):
            continue
        for element in rel.RelatedElements:
            if element.is_a("IfcSpace"):
                mapping[element.id()] = structure

    # IfcRelAggregates (spaces can be aggregated into a storey)
    for rel in model.by_type("IfcRelAggregates"):
        relating = rel.RelatingObject
        if not relating.is_a("IfcBuildingStorey"):
            continue
        for obj in rel.RelatedObjects:
            if obj.is_a("IfcSpace"):
                mapping[obj.id()] = relating

    return mapping


# =============================================================================
# CLI entry point
# =============================================================================

if __name__ == "__main__":
    import sys

    ifc_path = sys.argv[1] if len(sys.argv) > 1 else None
    min_h = float(sys.argv[2]) if len(sys.argv) > 2 else 2500.0

    if not ifc_path:
        print("Usage: python checker_ceiling_heights.py <model.ifc> [min_height_mm]")
        print("Example: python checker_ceiling_heights.py duplex.ifc 2500")
        sys.exit(1)

    model = ifcopenshell.open(ifc_path)
    results = check_ceiling_heights(model, min_height_mm=min_h)

    STATUS_ICON = {"pass": "+ PASS", "fail": "! FAIL", "warning": "? WARN", "blocked": "- BLCK", "log": "  LOG "}

    print(f"\nCeiling Height Check — min {min_h:.0f} mm")
    print(f"Model: {ifc_path}")
    print("=" * 72)

    for r in results:
        icon = STATUS_ICON.get(r["check_status"], r["check_status"].upper())
        name = r["element_name"]
        if r.get("element_name_long"):
            name += f" / {r['element_name_long']}"
        print(f"[{icon}]  {r['element_type']:<14} {name:<30} {r['actual_value']}")
        if r["comment"]:
            print(f"          -> {r['comment']}")

    print("=" * 72)

    summary = results[-1]
    print(f"Summary: {summary['actual_value']}  |  {summary['comment']}")
