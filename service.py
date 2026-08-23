from __future__ import annotations

from typing import Any

from extractcheck import CHARGE_USD
from extractcheck.compare import compare_claim, validate_schema
from extractcheck.extract import extract_from_bytes
from extractcheck.fetch import fetch_url, utc_now
from extractcheck.receipts import new_id, sign, store


def run_check(url: str, claim: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema_error = validate_schema(claim, schema)
    fetched = fetch_url(url)
    fetched_at = fetched.get("fetched_at") or utc_now()

    if not fetched.get("ok"):
        result: dict[str, Any] = {
            "pass": False,
            "charge": 0.0,
            "charged": False,
            "fetched_at": fetched_at,
            "http_status": fetched.get("http_status"),
            "snapshot_sha256": None,
            "our_extract": {},
            "diffs": [],
            "receipt_id": new_id(),
            "error": fetched.get("error") or "fetch failed",
            "url": url,
        }
        if schema_error:
            result["error"] = f"{result['error']}; {schema_error}"
        result["signature"] = sign(result)
        store(result)
        return result

    extract = extract_from_bytes(fetched["raw"], fetched.get("content_type") or "text/html")
    verdict = compare_claim(claim, extract)
    result = {
        "pass": verdict["pass"] and not schema_error,
        "charge": CHARGE_USD,
        "charged": True,
        "fetched_at": fetched_at,
        "http_status": fetched.get("http_status"),
        "snapshot_sha256": fetched.get("snapshot_sha256"),
        "our_extract": extract,
        "diffs": verdict["diffs"],
        "receipt_id": new_id(),
        "url": url,
    }
    if schema_error:
        result["error"] = schema_error
        result["diffs"] = list(result["diffs"]) + [
            {"path": "$schema", "claimed": schema, "found": None}
        ]
    result["signature"] = sign(result)
    store(result)
    return result
