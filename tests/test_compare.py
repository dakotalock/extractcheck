from extractcheck.compare import compare_claim, validate_schema


def test_compare_only_claimed_keys():
    found = {"title": "Hello", "price": "10.00", "h1": "Other"}
    assert compare_claim({"title": "hello"}, found)["pass"] is True
    assert compare_claim({"title": "hello", "price": "9"}, found)["pass"] is False


def test_whitespace_and_casefold():
    found = {"title": "  A Light\nIn the Attic "}
    r = compare_claim({"title": "a light in the attic"}, found)
    assert r["pass"] is True


def test_numeric_price_equivalence():
    found = {"price": "51.77", "price_text": "£51.77"}
    assert compare_claim({"price": 51.77}, found)["pass"] is True
    assert compare_claim({"price": "£51.77"}, found)["pass"] is True
    assert compare_claim({"price": "12.00"}, found)["pass"] is False


def test_nested_claim():
    found = {"offer": {"price": "3", "currency": "GBP"}}
    r = compare_claim({"offer": {"price": "3"}}, found)
    assert r["pass"] is True
    r = compare_claim({"offer": {"price": "4"}}, found)
    assert r["pass"] is False
    assert r["diffs"][0]["path"] == "offer.price"


def test_schema_required():
    assert validate_schema({"title": "x"}, {"type": "object", "required": ["title"]}) is None
    err = validate_schema({}, {"type": "object", "required": ["title"]})
    assert err and "title" in err
