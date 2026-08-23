from __future__ import annotations

from typing import Any

from extractcheck.normalize import as_number, casefold_text, collapse


def _values_equal(claimed: Any, found: Any) -> bool:
    if claimed is None and found is None:
        return True
    cn, fn = as_number(claimed), as_number(found)
    if cn is not None and fn is not None:
        return cn == fn
    return casefold_text(claimed) == casefold_text(found)


def compare_claim(claim: dict[str, Any], found: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Compare only keys present in claim. Nested dicts recurse."""
    diffs: list[dict[str, Any]] = []
    passed = True
    if not isinstance(claim, dict):
        return {"pass": False, "diffs": [{"path": prefix or "$", "claimed": claim, "found": found}]}

    for key, claimed in claim.items():
        path = f"{prefix}.{key}" if prefix else key
        current = found.get(key) if isinstance(found, dict) else None
        if isinstance(claimed, dict):
            nested = compare_claim(claimed, current if isinstance(current, dict) else {}, path)
            if not nested["pass"]:
                passed = False
                diffs.extend(nested["diffs"])
            continue
        if not _values_equal(claimed, current):
            passed = False
            diffs.append({"path": path, "claimed": claimed, "found": current})
    return {"pass": passed, "diffs": diffs}


def validate_schema(claim: dict[str, Any], schema: dict[str, Any] | None) -> str | None:
    if not schema:
        return None
    if schema.get("type") == "object" and not isinstance(claim, dict):
        return "claim is not an object"
    required = schema.get("required") or []
    missing = [k for k in required if k not in claim]
    if missing:
        return f"claim missing required keys: {', '.join(missing)}"
    return None


def display(value: Any) -> Any:
    if isinstance(value, str):
        return collapse(value)
    return value
