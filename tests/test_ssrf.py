from extractcheck.ssrf import validate_url


def test_blocks_loopback_and_private():
    blocked = [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/",
        "http://[::1]/",
        "file:///etc/passwd",
        "ftp://example.com/",
    ]
    for url in blocked:
        err = validate_url(url)
        assert err, url
        assert "blocked" in err


def test_allows_example_at_validator():
    assert validate_url("https://example.com") is None
    assert validate_url("http://example.com") is None


def test_blocks_userinfo_and_odd_ports():
    assert validate_url("https://user:pass@example.com/")
    assert validate_url("https://example.com:8080/")
