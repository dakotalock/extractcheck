from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from extractcheck import CHARGE_USD, __version__
from extractcheck.billing import configured, meter_event_name
from extractcheck.receipts import load, verify
from extractcheck.service import run_check

DEFAULT_API_KEY = "dev-key"

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


def _api_key() -> str:
    return os.environ.get("EXTRACTCHECK_API_KEY", DEFAULT_API_KEY)


def _require_key(x_api_key: str | None) -> None:
    if not x_api_key or not hmac_ok(x_api_key, _api_key()):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


def hmac_ok(given: str, expected: str) -> bool:
    import hmac as _hmac

    return _hmac.compare_digest(given, expected)


LANDING = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>ExtractCheck — scrape lie detector</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ margin: 0; font: 16px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
           background: #0b0d10; color: #e8edf2; }}
    main {{ max-width: 720px; margin: 12vh auto; padding: 0 24px; }}
    h1 {{ font-size: 22px; font-weight: 600; letter-spacing: -0.02em; }}
    p {{ color: #c3ccd6; }}
    code, pre {{ background: #151a21; border: 1px solid #2a3340; border-radius: 8px; }}
    code {{ padding: 2px 6px; }}
    pre {{ padding: 14px 16px; overflow-x: auto; color: #d7e3ef; }}
    .price {{ color: #9be59b; }}
    a {{ color: #8ec8ff; }}
    footer {{ margin-top: 2.5rem; color: #7d8896; font-size: 13px; }}
  </style>
</head>
<body>
<main>
  <h1>ExtractCheck</h1>
  <p>We refetch the page, extract independently, and tell you if an agent's claimed JSON is a lie. Signed receipt included.</p>
  <pre>curl -sS http://127.0.0.1:8787/v1/check \\
  -H 'X-API-Key: dev-key' -H 'Content-Type: application/json' \\
  -d '{{{"url":"http://books.toscrape.com/","claim":{{"title":"All products | Books to Scrape - Sandbox","price_text":"£51.77"}}}}'</pre>
  <p class="price">${CHARGE_USD:.2f} per successful non-empty fetch. $0.00 if we cannot fetch or the body is empty.</p>
  <p><a href="/docs">OpenAPI</a> · <a href="/health">health</a> · MCP tool <code>check_extract</code></p>
  <footer>Not a crawler. No logins. No captcha farms. Voidly sells scrape hashes; we sell extract verification.</footer>
</main>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def landing() -> str:
    return LANDING


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "extractcheck", "version": __version__}


@app.get("/v1/billing")
def billing() -> dict[str, Any]:
    return {"ok": True, "meter": meter_event_name(), "configured": configured()}


@app.post("/v1/check")
def check(body: CheckBody, x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> JSONResponse:
    _require_key(x_api_key)
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must be http(s)")
    if not isinstance(body.claim, dict) or not body.claim:
        raise HTTPException(status_code=400, detail="claim must be a non-empty object")
    result = run_check(body.url, body.claim, body.schema_obj)
    return JSONResponse(result)


@app.get("/v1/receipts/{receipt_id}")
def get_receipt(receipt_id: str, x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict[str, Any]:
    _require_key(x_api_key)
    row = load(receipt_id)
    if not row:
        raise HTTPException(status_code=404, detail="receipt not found")
    return {"receipt": row, "signature_valid": verify(row)}
