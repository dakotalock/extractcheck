from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import httpx

UA = "ExtractCheck/0.1"
TIMEOUT = 12.0
MAX_BODY = 2_000_000


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_url(url: str) -> dict:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    }
    try:
        with httpx.Client(follow_redirects=True, timeout=TIMEOUT, headers=headers) as client:
            with client.stream("GET", url) as resp:
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
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "error": f"fetch failed: {exc.__class__.__name__}: {str(exc)[:160]}",
            "http_status": None,
            "fetched_at": utc_now(),
        }
    except Exception as exc:  # noqa: BLE001 — surface any fetch blow-up as no-charge
        return {
            "ok": False,
            "error": f"fetch failed: {str(exc)[:160]}",
            "http_status": None,
            "fetched_at": utc_now(),
        }

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
