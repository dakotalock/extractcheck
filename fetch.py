from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx

from extractcheck.ssrf import BLOCKED_MSG, validate_url

UA = "ExtractCheck/0.1"
TIMEOUT = 12.0
MAX_BODY = 2_000_000
MAX_HOPS = 5
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fail(error: str, http_status: int | None = None) -> dict:
    return {
        "ok": False,
        "error": error,
        "http_status": http_status,
        "fetched_at": utc_now(),
    }


def _read_body(resp: httpx.Response) -> tuple[bytes, int, str, str]:
    chunks: list[bytes] = []
    size = 0
    for chunk in resp.iter_bytes():
        size += len(chunk)
        if size > MAX_BODY:
            chunks.append(chunk[: MAX_BODY - (size - len(chunk))])
            break
        chunks.append(chunk)
    raw = b"".join(chunks)[:MAX_BODY]
    status = resp.status_code
    ctype = resp.headers.get("content-type", "")
    final = str(resp.url)
    return raw, status, ctype, final


def fetch_url(url: str) -> dict:
    err = validate_url(url)
    if err:
        return _fail(err)

    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    }
    current = url
    hops = 0
    try:
        with httpx.Client(follow_redirects=False, timeout=TIMEOUT, headers=headers) as client:
            while True:
                err = validate_url(current)
                if err:
                    return _fail(err)
                with client.stream("GET", current) as resp:
                    status = resp.status_code
                    if status in REDIRECT_STATUSES:
                        hops += 1
                        if hops > MAX_HOPS:
                            return _fail(BLOCKED_MSG, status)
                        loc = resp.headers.get("location")
                        if not loc:
                            return _fail(BLOCKED_MSG, status)
                        nxt = urljoin(str(resp.url), loc)
                        hop_err = validate_url(nxt)
                        if hop_err:
                            return _fail(hop_err, status)
                        current = nxt
                        continue
                    raw, status, ctype, final = _read_body(resp)
                    break
    except httpx.HTTPError as exc:
        return _fail(f"fetch failed: {exc.__class__.__name__}: {str(exc)[:160]}")
    except Exception as exc:  # noqa: BLE001 — surface any fetch blow-up as no-charge
        return _fail(f"fetch failed: {str(exc)[:160]}")

    if not raw.strip():
        return {
            "ok": False,
            "error": "empty body",
            "http_status": status,
            "fetched_at": utc_now(),
            "final_url": final,
        }

    return {
        "ok": True,
        "http_status": status,
        "fetched_at": utc_now(),
        "final_url": final,
        "content_type": ctype,
        "raw": raw,
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
