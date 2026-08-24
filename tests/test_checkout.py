from extractcheck.checkout import hash_secret, parse_paid_key


def test_parse_paid_key():
    got = parse_paid_key("eck_cus_abc123_s3cret-token")
    assert got == ("cus_abc123", "s3cret-token")
    assert parse_paid_key("ec_wVRL_notpaid") is None
    assert parse_paid_key("eck_cus_only") is None


def test_hash_secret_stable():
    assert hash_secret("abc") == hash_secret("abc")
    assert hash_secret("abc") != hash_secret("abd")
