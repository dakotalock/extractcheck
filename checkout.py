from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import Any
import httpx

from extractcheck.billing import price_id, secret as stripe_secret

PUBLIC_BASE = os.environ.get("EXTRACTCHECK_PUBLIC_URL") or "https://extractcheck.onrender.com"
HASH_META = "extractcheck_key_hash"


def _form(data: dict[str, Any]) -> dict[str, str]:
    pairs: dict[str, str] = {}

    def flatten(prefix: str, val: Any) -> None:
        if isinstance(val, dict):
            for k, v in val.items():
                flatten(f"{prefix}[{k}]" if prefix else k, v)
        elif isinstance(val, list):
            for i, v in enumerate(val):
                flatten(f"{prefix}[{i}]", v)
        elif val is not None:
            pairs[prefix] = str(val)

    flatten("", data)
    return pairs


def _stripe(method: str, path: str, data: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    key = stripe_secret()
    if not key:
        return 500, {"error": {"message": "stripe not configured"}}
    with httpx.Client(timeout=20.0) as client:
        resp = client.request(
            method,
            f"https://api.stripe.com/v1{path}",
            data=_form(data) if data else None,
            auth=(key, ""),
        )
    try:
        body = resp.json()
    except Exception:
        body = {"error": {"message": f"http {resp.status_code}"}}
    if not isinstance(body, dict):
        body = {"error": {"message": "bad stripe response"}}
    return resp.status_code, body


def hash_secret(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_paid_key(api_key: str) -> tuple[str, str] | None:
    if not api_key.startswith("eck_cus_"):
        return None
    rest = api_key[len("eck_") :]
    idx = rest.find("_", 4)  # skip "cus_"
    if idx < 0:
        return None
    customer_id, token = rest[:idx], rest[idx + 1 :]
    if not customer_id.startswith("cus_") or not token:
        return None
    return customer_id, token


def create_checkout_session() -> dict[str, Any]:
    pid = price_id()
    if not stripe_secret() or not pid:
        return {"ok": False, "error": "checkout not configured"}
    payload = {
        "mode": "subscription",
        "success_url": PUBLIC_BASE + "/v1/checkout/success?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": PUBLIC_BASE + "/",
        "line_items": [{"price": pid, "quantity": 1}],
        "payment_method_collection": "always",
        "billing_address_collection": "auto",
        "allow_promotion_codes": "false",
        "subscription_data": {"description": "ExtractCheck usage, $0.03 per successful fetch"},
    }
    status, body = _stripe("POST", "/checkout/sessions", payload)
    if status >= 400:
        # metered prices often reject quantity
        payload["line_items"] = [{"price": pid}]
        status, body = _stripe("POST", "/checkout/sessions", payload)
    if status >= 400:
        err = (body.get("error") or {}).get("message") or f"http {status}"
        return {"ok": False, "error": str(err)[:200]}
    url = body.get("url")
    if not url:
        return {"ok": False, "error": "no checkout url"}
    return {"ok": True, "url": url, "id": body.get("id")}


def issue_key_for_session(session_id: str) -> dict[str, Any]:
    status, session = _stripe("GET", f"/checkout/sessions/{session_id}")
    if status >= 400:
        return {"ok": False, "error": "session not found"}
    if session.get("mode") != "subscription":
        return {"ok": False, "error": "not a subscription session"}
    if session.get("status") not in {"complete", "paid"} and session.get("payment_status") not in {"paid", "no_payment_required"}:
        # subscriptions can be complete with paid
        if session.get("status") != "complete":
            return {"ok": False, "error": "checkout not complete"}
    customer_id = session.get("customer")
    if not customer_id or not isinstance(customer_id, str):
        return {"ok": False, "error": "no customer on session"}
    st, customer = _stripe("GET", f"/customers/{customer_id}")
    if st >= 400:
        return {"ok": False, "error": "customer not found"}
    meta = customer.get("metadata") or {}
    existing = meta.get(HASH_META)
    if existing:
        return {
            "ok": True,
            "already_issued": True,
            "customer_id": customer_id,
            "api_key": None,
            "message": "API key was already issued for this checkout. We cannot show it again.",
        }
    token = secrets.token_urlsafe(24)
    api_key = f"eck_{customer_id}_{token}"
    st, updated = _stripe(
        "POST",
        f"/customers/{customer_id}",
        {"metadata": {HASH_META: hash_secret(token)}},
    )
    if st >= 400:
        return {"ok": False, "error": "could not save key"}
    return {
        "ok": True,
        "already_issued": False,
        "customer_id": customer_id,
        "api_key": api_key,
        "message": "Save this API key. We will not show it again.",
    }


def customer_for_paid_key(api_key: str) -> str | None:
    parsed = parse_paid_key(api_key)
    if not parsed:
        return None
    customer_id, token = parsed
    st, customer = _stripe("GET", f"/customers/{customer_id}")
    if st >= 400:
        return None
    expected = (customer.get("metadata") or {}).get(HASH_META) or ""
    if not expected:
        return None
    if hmac.compare_digest(expected, hash_secret(token)):
        return customer_id
    return None
