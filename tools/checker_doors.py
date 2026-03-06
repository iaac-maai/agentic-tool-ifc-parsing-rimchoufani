"""
IFC Compliance Checker - Door Accessibility
Checks that doors meet minimum accessibility width requirements (>= 900mm).
"""

import ifcopenshell
import ifcopenshell.util.element


def check_door_accessibility(model: ifcopenshell.file, min_width_mm: float = 900.0, **kwargs) -> list[dict]:
    """
    Checks each IfcDoor for minimum accessible width (default: 900 mm).

    For each door:
      - If OverallWidth is set and >= min_width_mm  → pass
      - If OverallWidth is set and <  min_width_mm  → fail
      - If OverallWidth is not set                  → warning (cannot verify)

    A summary row is appended at the end.

    Args:
        model: An ifcopenshell.file object representing the IFC model.
        min_width_mm: Minimum required door width in millimetres (default 900).

    Returns:
        List of result dicts following the required schema.
    """
    results = []
    doors = model.by_type("IfcDoor")

    passed = 0
    failed = 0
    warnings = 0

    for door in doors:
        element_id = door.GlobalId
        element_name = door.Name or f"Door #{door.id()}"

        # OverallWidth is a direct attribute on IfcDoor (may be None if not set)
        overall_width = getattr(door, "OverallWidth", None)

        if overall_width is None:
            status = "warning"
            actual = "Not set"
            comment = "OverallWidth not defined; accessibility cannot be verified."
            warnings += 1
        elif overall_width >= min_width_mm:
            status = "pass"
            actual = f"{overall_width} mm"
            comment = None
            passed += 1
        else:
            status = "fail"
            actual = f"{overall_width} mm"
            comment = (
                f"Door is too narrow for accessibility. "
                f"Width {overall_width} mm < required {min_width_mm} mm."
            )
            failed += 1

        results.append({
            "element_id": element_id,
            "element_type": "IfcDoor",
            "element_name": element_name,
            "element_name_long": None,
            "check_status": status,
            "actual_value": actual,
            "required_value": f">= {min_width_mm} mm",
            "comment": comment,
            "log": f"OverallWidth raw value: {overall_width}",
        })

    # --- Summary row ---
    total = len(doors)
    if total == 0:
        summary_status = "warning"
        summary_comment = "No IfcDoor elements found in the model."
    elif failed > 0:
        summary_status = "fail"
        summary_comment = f"{failed}/{total} door(s) do not meet the minimum width requirement."
    elif warnings > 0:
        summary_status = "warning"
        summary_comment = f"{warnings}/{total} door(s) have no width defined; manual review recommended."
    else:
        summary_status = "pass"
        summary_comment = f"All {total} door(s) meet the minimum width requirement."

    results.append({
        "element_id": None,
        "element_type": "Summary",
        "element_name": "Door Accessibility Check",
        "element_name_long": None,
        "check_status": summary_status,
        "actual_value": f"{passed} pass / {failed} fail / {warnings} warning",
        "required_value": f"All doors >= {min_width_mm} mm wide",
        "comment": summary_comment,
        "log": None,
    })

    return results
