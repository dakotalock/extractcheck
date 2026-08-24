# ExtractCheck

A lie detector for agent scrapes. The caller sends a URL plus a claimed JSON extract. We fetch the public page, extract independently, diff, and return pass/fail with a signed receipt.

We do **not** sell crawling. Voidly sells signed scrape hashes. We sell extract verification.

We only verify these fields: `kind`, `title`, `h1`, `description`, `canonical`, `og:title`, `og:description`, `name`, `price`, `currency`, `price_text`; extra claim keys fail because we did not extract them.

## Run

```bash
cd /workspace
source .venv/bin/activate   # created on this machine; or pip install -r extractcheck/requirements.txt
export PYTHONPATH=/workspace
uvicorn extractcheck.api:app --host 0.0.0.0 --port 8787
```

Docker:

```bash
docker build -t extractcheck /workspace/extractcheck
docker run --rm -p 8787:8787 -e EXTRACTCHECK_API_KEY=dev-key -e EXTRACTCHECK_SECRET=dev-secret extractcheck
```

## Check

```bash
curl -sS http://127.0.0.1:8787/v1/check \
  -H 'X-API-Key: dev-key' \
  -H 'Content-Type: application/json' \
  -d '{"url":"http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html","claim":{"title":"A Light in the Attic | Books to Scrape - Sandbox","price_text":"£51.77"}}'
```

Auth: `X-API-Key` must match `EXTRACTCHECK_API_KEY` (default `dev-key`).

GET `/health` · GET `/docs` · GET `/v1/openapi.json` · GET `/v1/fields` · GET `/v1/receipts/{id}`

## Pricing and refunds

- **$0.03** when we fetch a non-empty body (`charge: 0.03`, `charged: true`).
- **$0.00** when we cannot fetch or the body is empty (`charged: false`). That is the refund rule: no fetch, no charge.
- Stripe test-mode meter `extractcheck_check` at **$0.03** per `charged: true` check.
- Set `STRIPE_SECRET_KEY`, `STRIPE_CUSTOMER_ID`, and optional `STRIPE_METER_EVENT` (default `extractcheck_check`).
- If Stripe is unset or errors, the check still returns; `stripe_reported` is false.
- GET `/v1/billing` shows whether Stripe is configured (no secrets).

## MCP

One tool: `check_extract(url, claim, schema?)`.

```json
{
  "mcpServers": {
    "extractcheck": {
      "command": "python",
      "args": ["-m", "extractcheck.mcp_server"],
      "env": {
        "PYTHONPATH": "/workspace",
        "EXTRACTCHECK_SECRET": "dev-secret"
      }
    }
  }
}
```

`extractcheck/mcp.json` describes the tool for hosts / Smithery-style catalogs. Stdio JSON-RPC is implemented in `mcp_server.py`.

## What we will not do

- Browser logins or session cookies
- CAPTCHA farms or paywall bypass
- Generic crawl / sitemap walks
- Memory or ads
- Attacking sites

Fetches use `User-Agent: ExtractCheck/0.1`, a 12s timeout, and a 2MB body cap.

## Tests

```bash
PYTHONPATH=/workspace python -m pytest /workspace/extractcheck/tests -q
PYTHONPATH=/workspace python -m extractcheck.bakeoff_hard
```

## Receipts

HMAC-SHA256 and Ed25519 over the same canonical JSON (keys sorted, no `signature`/`ed25519` fields). HMAC uses `EXTRACTCHECK_SECRET` (default `dev-secret`). Ed25519 uses `EXTRACTCHECK_ED25519_SEED` (64 hex chars); `pubkey_ed25519` is on the receipt and GET `/v1/billing`. Stored at `extractcheck/data/receipts.jsonl`.
