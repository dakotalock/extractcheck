from extractcheck import billing


def test_skip_when_unconfigured(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_CUSTOMER_ID", raising=False)
    got = billing.report_usage("rcpt_x")
    assert got["stripe_reported"] is False
    assert "not configured" in got["stripe_error"]


def test_posts_meter_event(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("STRIPE_CUSTOMER_ID", "cus_test")
    monkeypatch.setenv("STRIPE_METER_EVENT", "extractcheck_check")
    calls = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"identifier": "rcpt_1"}

    class FakeClient:
        def __init__(self, timeout=None):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def post(self, url, data=None, auth=None, headers=None):
            calls.append({"url": url, "data": data, "headers": headers})
            return FakeResp()

    monkeypatch.setattr(billing.httpx, "Client", FakeClient)
    got = billing.report_usage("rcpt_1")
    assert got == {"stripe_reported": True}
    assert calls[0]["data"]["identifier"] == "rcpt_1"
    assert calls[0]["data"]["payload[value]"] == "1"
    assert "sk_test" not in str(got)


def test_stripe_error_does_not_raise(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("STRIPE_CUSTOMER_ID", "cus_test")

    class FakeResp:
        status_code = 500
        def json(self):
            return {"error": {"message": "nope"}}

    class FakeClient:
        def __init__(self, timeout=None):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def post(self, url, data=None, auth=None, headers=None):
            return FakeResp()

    monkeypatch.setattr(billing.httpx, "Client", FakeClient)
    got = billing.report_usage("rcpt_2")
    assert got["stripe_reported"] is False
    assert "nope" in got["stripe_error"]
