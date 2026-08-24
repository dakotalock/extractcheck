import json

from extractcheck.receipts import canonical_json, sign, verify


def test_sign_and_verify_roundtrip():
    payload = {
        "pass": True,
        "charge": 0.03,
        "charged": True,
        "receipt_id": "rcpt_test",
        "our_extract": {"title": "Hi"},
        "diffs": [],
    }
    signed = dict(payload)
    signed["signature"] = sign(payload)
    assert verify(signed) is True


def test_tamper_breaks_signature():
    payload = {"pass": True, "receipt_id": "rcpt_x", "charge": 0.03}
    payload["signature"] = sign(payload)
    payload["pass"] = False
    assert verify(payload) is False


def test_canonical_excludes_signature_and_sorts():
    raw = canonical_json({"b": 1, "a": 2, "signature": "nope"})
    assert raw == '{"a":2,"b":1}'
    json.loads(raw)


def test_secret_override(monkeypatch):
    payload = {"receipt_id": "rcpt_1"}
    monkeypatch.setenv("EXTRACTCHECK_SECRET", "other-secret")
    from extractcheck import receipts as r

    sig = r.sign(payload)
    assert r.verify({**payload, "signature": sig}) is True
    assert r.verify({**payload, "signature": sig}, key="dev-secret") is False


def test_ed25519_roundtrip_and_either_verify():
    from extractcheck.receipts import attach_signatures, verify

    payload = {"pass": True, "receipt_id": "rcpt_ed", "charge": 0.03}
    attach_signatures(payload)
    assert payload.get("ed25519")
    assert payload.get("pubkey_ed25519")
    assert len(payload["pubkey_ed25519"]) == 64
    assert verify(payload) is True
    hmac_only = dict(payload)
    hmac_only.pop("ed25519")
    assert verify(hmac_only) is True
    ed_only = dict(payload)
    ed_only["signature"] = "0" * 64
    assert verify(ed_only) is True
