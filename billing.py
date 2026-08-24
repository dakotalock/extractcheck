from __future__ import annotations

import os
from typing import Any

import httpx

STRIPE_API = "https://api.stripe.com/v1"
DEFAULT_EVENT = "extractcheck_check"


def secret() -> str:
    return os.environ.get("STRIPE_SECRET_KEY") or ""


def configured() -> bool:
    return bool(secret())


def meter_event_name() -> str:
    return os.environ.get("STRIPE_METER_EVENT") or DEFAULT_EVENT


def price_id() -> str:
    return os.environ.get("STRIPE_PRICE_ID") or ""


def report_usage(receipt_id: str, customer_id: str | None = None, units: int = 1) -> dict[str, Any]:
    """Send a meter event. Never raises. Never returns the secret."""
    key = secret()
    customer = customer_id or os.environ.get("STRIPE_CUSTOMER_ID")
    if not key or not customer:
        return {"stripe_reported": False, "stripe_error": "stripe not configured"}
    if units <= 0:
        return {"stripe_reported": False, "stripe_error": "no billable units"}
    data = {
        "event_name": meter_event_name(),
        "identifier": receipt_id,
        "payload[stripe_customer_id]": customer,
        "payload[value]": str(units),
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(
                f"{STRIPE_API}/billing/meter_events",
                data=data,
                auth=(key, ""),
                headers={"Idempotency-Key": receipt_id},
            )
        if resp.status_code >= 400:
            detail = ""
            try:
                err = resp.json().get("error") or {}
                detail = str(err.get("message") or err.get("type") or "")[:160]
            except Exception:
                detail = f"http {resp.status_code}"
            return {"stripe_reported": False, "stripe_error": detail or f"http {resp.status_code}"}
        return {"stripe_reported": True}
    except httpx.HTTPError as exc:
        return {"stripe_reported": False, "stripe_error": f"{exc.__class__.__name__}"}
    except Exception as exc:  # noqa: BLE001
        return {"stripe_reported": False, "stripe_error": exc.__class__.__name__}
