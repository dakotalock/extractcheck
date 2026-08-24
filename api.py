from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from extractcheck import __version__
from extractcheck.billing import configured, meter_event_name, price_id
from extractcheck.checkout import create_checkout_session, customer_for_paid_key, issue_key_for_session
from extractcheck.extract import SUPPORTED_FIELDS
from extractcheck.receipts import load, pubkey_ed25519, verify
from extractcheck.service import run_check

DEFAULT_API_KEY = "dev-key"

def _require_prod_secrets() -> None:
    if os.environ.get("EXTRACTCHECK_ALLOW_DEV") == "1":
        return
    api_key = os.environ.get("EXTRACTCHECK_API_KEY")
    secret = os.environ.get("EXTRACTCHECK_SECRET")
    seed = os.environ.get("EXTRACTCHECK_ED25519_SEED") or ""
    if not api_key or api_key == DEFAULT_API_KEY:
        raise RuntimeError("EXTRACTCHECK_API_KEY must be set to a non-dev value")
    if not secret or secret == "dev-secret":
        raise RuntimeError("EXTRACTCHECK_SECRET must be set to a non-dev value")
    if len(seed) != 64:
        raise RuntimeError("EXTRACTCHECK_ED25519_SEED must be 64 hex characters")
    try:
        bytes.fromhex(seed)
    except ValueError as exc:
        raise RuntimeError("EXTRACTCHECK_ED25519_SEED must be 64 hex characters") from exc


_require_prod_secrets()


app = FastAPI(
    title="ExtractCheck",
    version=__version__,
    description="Lie detector for agent scrapes. Verify a claimed JSON extract against a live page.",
    docs_url="/docs",
    openapi_url="/v1/openapi.json",
)


class CheckBody(BaseModel):
    url: str
    claim: dict[str, Any]
    schema_obj: dict[str, Any] | None = Field(default=None, alias="schema")

    model_config = {"populate_by_name": True}


def _operator_key() -> str:
    return os.environ.get("EXTRACTCHECK_API_KEY", DEFAULT_API_KEY)


def hmac_ok(given: str, expected: str) -> bool:
    import hmac as _hmac

    return _hmac.compare_digest(given, expected)


def resolve_caller(x_api_key: str | None) -> str | None:
    """Return Stripe customer id to bill, or None for the operator key (env customer)."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
    if hmac_ok(x_api_key, _operator_key()):
        return os.environ.get("STRIPE_CUSTOMER_ID")
    customer_id = customer_for_paid_key(x_api_key)
    if not customer_id:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
    return customer_id


LANDING = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>ExtractCheck — scrape lie detector</title>
  <style>
    :root { color-scheme: dark; }
    body { margin: 0; font: 16px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
           background: #0b0d10; color: #e8edf2; }
    main { max-width: 720px; margin: 12vh auto; padding: 0 24px; }
    h1 { font-size: 22px; font-weight: 600; letter-spacing: -0.02em; }
    p { color: #c3ccd6; }
    code, pre { background: #151a21; border: 1px solid #2a3340; border-radius: 8px; }
    code { padding: 2px 6px; }
    pre { padding: 14px 16px; overflow-x: auto; color: #d7e3ef; }
    .price { color: #9be59b; }
    a { color: #8ec8ff; }
    footer { margin-top: 2.5rem; color: #7d8896; font-size: 13px; }
  </style>
</head>
<body>
<main>
  <h1>ExtractCheck</h1>
  <p>We refetch the page, extract independently, and tell you if an agent's claimed JSON is a lie. Signed receipt included.</p>
  <pre>curl -sS https://extractcheck.onrender.com/v1/check \\
  -H 'X-API-Key: YOUR_KEY' -H 'Content-Type: application/json' \\
  -d '{"url":"http://books.toscrape.com/","claim":{"title":"All products | Books to Scrape - Sandbox","price_text":"£51.77"}}'</pre>
  <p class="price">$0.03 per successful non-empty fetch. $0.00 if we cannot fetch or the body is empty. Card required.</p>
  <p><a href="/v1/checkout">Subscribe with a card</a> · <a href="/docs">OpenAPI</a> · <a href="/health">health</a></p>
  <footer>Not a crawler. No logins. No captcha farms.</footer>
</main>
</body>
</html>
"""


SUCCESS_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><title>ExtractCheck key</title>
<style>
:root { color-scheme: dark; }
body { margin: 0; font: 16px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
       background: #0b0d10; color: #e8edf2; }
main { max-width: 720px; margin: 12vh auto; padding: 0 24px; }
code, pre { background: #151a21; border: 1px solid #2a3340; border-radius: 8px; padding: 14px 16px; display: block; overflow-x: auto; }
p { color: #c3ccd6; } a { color: #8ec8ff; }
</style></head><body><main>
<h1>ExtractCheck</h1>
<p>{message}</p>
{key_block}
<p>Header: <code>X-API-Key</code>. $0.03 per successful fetch, billed to the card on this subscription.</p>
<p><a href="/">Home</a></p>
</main></body></html>
"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def landing() -> str:
    return LANDING


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "extractcheck", "version": __version__}


@app.get("/v1/billing")
def billing() -> dict[str, Any]:
    return {
        "ok": True,
        "meter": meter_event_name(),
        "configured": configured(),
        "checkout": bool(price_id()),
        "pubkey_ed25519": pubkey_ed25519(),
    }


@app.get("/v1/fields")
def fields() -> dict[str, Any]:
    return {"fields": list(SUPPORTED_FIELDS)}


@app.get("/v1/checkout")
def checkout_redirect():
    got = create_checkout_session()
    if not got.get("ok"):
        raise HTTPException(status_code=503, detail=got.get("error") or "checkout failed")
    return RedirectResponse(got["url"], status_code=303)


@app.post("/v1/checkout")
def checkout_json() -> dict[str, Any]:
    got = create_checkout_session()
    if not got.get("ok"):
        raise HTTPException(status_code=503, detail=got.get("error") or "checkout failed")
    return {"url": got["url"]}


@app.get("/v1/checkout/success", response_class=HTMLResponse)
def checkout_success(session_id: str = Query(default="")) -> str:
    if not session_id:
        raise HTTPException(status_code=400, detail="missing session_id")
    got = issue_key_for_session(session_id)
    if not got.get("ok"):
        raise HTTPException(status_code=400, detail=got.get("error") or "could not issue key")
    key = got.get("api_key")
    key_block = f"<pre>{key}</pre>" if key else "<p>No key in this response.</p>"
    return SUCCESS_PAGE.replace("{message}", got.get("message") or "").replace("{key_block}", key_block)


@app.post("/v1/check")
def check(body: CheckBody, x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> JSONResponse:
    bill_to = resolve_caller(x_api_key)
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must be http(s)")
    if not isinstance(body.claim, dict) or not body.claim:
        raise HTTPException(status_code=400, detail="claim must be a non-empty object")
    result = run_check(body.url, body.claim, body.schema_obj, bill_to=bill_to)
    return JSONResponse(result)


@app.get("/v1/receipts/{receipt_id}")
def get_receipt(receipt_id: str, x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict[str, Any]:
    resolve_caller(x_api_key)
    row = load(receipt_id)
    if not row:
        raise HTTPException(status_code=404, detail="receipt not found")
    return {"receipt": row, "signature_valid": verify(row)}
