from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from pathlib import Path
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

DEFAULT_SECRET = "dev-secret"
RECEIPTS_PATH = Path(os.environ.get("EXTRACTCHECK_RECEIPTS", "/workspace/extractcheck/data/receipts.jsonl"))
SIG_FIELDS = frozenset({"signature", "ed25519"})


def secret() -> str:
    return os.environ.get("EXTRACTCHECK_SECRET", DEFAULT_SECRET)


def _seed_bytes() -> bytes | None:
    raw = os.environ.get("EXTRACTCHECK_ED25519_SEED") or ""
    if len(raw) != 64:
        return None
    try:
        seed = bytes.fromhex(raw)
    except ValueError:
        return None
    if len(seed) != 32:
        return None
    return seed


def signing_key() -> SigningKey | None:
    seed = _seed_bytes()
    if seed is None:
        return None
    return SigningKey(seed)


def pubkey_ed25519() -> str | None:
    key = signing_key()
    if key is None:
        return None
    return key.verify_key.encode().hex()


def canonical_json(payload: dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k not in SIG_FIELDS}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign(payload: dict[str, Any], key: str | None = None) -> str:
    raw = canonical_json(payload).encode("utf-8")
    return hmac.new((key or secret()).encode("utf-8"), raw, hashlib.sha256).hexdigest()


def sign_ed25519(payload: dict[str, Any]) -> str | None:
    key = signing_key()
    if key is None:
        return None
    signed = key.sign(canonical_json(payload).encode("utf-8"))
    return signed.signature.hex()


def verify(payload: dict[str, Any], key: str | None = None) -> bool:
    sig = payload.get("signature")
    if isinstance(sig, str) and sig:
        expected = sign(payload, key)
        if hmac.compare_digest(sig, expected):
            return True
    ed_sig = payload.get("ed25519")
    pub = payload.get("pubkey_ed25519")
    if isinstance(ed_sig, str) and ed_sig and isinstance(pub, str) and pub:
        try:
            VerifyKey(bytes.fromhex(pub)).verify(
                canonical_json(payload).encode("utf-8"),
                bytes.fromhex(ed_sig),
            )
            return True
        except (BadSignatureError, ValueError):
            return False
    return False


def attach_signatures(payload: dict[str, Any]) -> dict[str, Any]:
    pub = pubkey_ed25519()
    if pub:
        payload["pubkey_ed25519"] = pub
        ed = sign_ed25519(payload)
        if ed:
            payload["ed25519"] = ed
    payload["signature"] = sign(payload)
    return payload


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
