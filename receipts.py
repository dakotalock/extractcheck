from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from pathlib import Path
from typing import Any

DEFAULT_SECRET = "dev-secret"
RECEIPTS_PATH = Path(os.environ.get("EXTRACTCHECK_RECEIPTS", "/workspace/extractcheck/data/receipts.jsonl"))


def secret() -> str:
    return os.environ.get("EXTRACTCHECK_SECRET", DEFAULT_SECRET)


def canonical_json(payload: dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign(payload: dict[str, Any], key: str | None = None) -> str:
    raw = canonical_json(payload).encode("utf-8")
    return hmac.new((key or secret()).encode("utf-8"), raw, hashlib.sha256).hexdigest()


def verify(payload: dict[str, Any], key: str | None = None) -> bool:
    sig = payload.get("signature")
    if not isinstance(sig, str) or not sig:
        return False
    expected = sign(payload, key)
    return hmac.compare_digest(sig, expected)


def new_id() -> str:
    return f"rcpt_{uuid.uuid4().hex}"


def store(receipt: dict[str, Any], path: Path | None = None) -> None:
    dest = path or RECEIPTS_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, ensure_ascii=False) + "\n")


def load(receipt_id: str, path: Path | None = None) -> dict[str, Any] | None:
    dest = path or RECEIPTS_PATH
    if not dest.exists():
        return None
    with dest.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("receipt_id") == receipt_id:
                return row
    return None
