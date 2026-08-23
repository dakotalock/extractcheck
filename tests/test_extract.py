from extractcheck.extract import extract_html

HTML = """<!doctype html>
<html>
<head>
  <title>  A Light in the Attic  </title>
  <meta name="description" content="A poetry book.">
  <link rel="canonical" href="http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html">
  <meta property="og:title" content="A Light in the Attic">
  <meta property="og:description" content="Poems.">
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"Product","name":"A Light in the Attic",
   "offers":{"@type":"Offer","price":"51.77","priceCurrency":"GBP"}}
  </script>
</head>
<body>
  <h1>A Light in the Attic</h1>
  <p class="price_color">£51.77</p>
</body>
</html>
"""


def test_extracts_core_fields_and_jsonld():
    got = extract_html(HTML)
    assert got["title"] == "A Light in the Attic"
    assert got["h1"] == "A Light in the Attic"
    assert got["description"] == "A poetry book."
    assert got["canonical"].endswith("a-light-in-the-attic_1000/index.html")
    assert got["og:title"] == "A Light in the Attic"
    assert got["og:description"] == "Poems."
    assert got["name"] == "A Light in the Attic"
    assert got["price"] == "51.77"
    assert got["currency"] == "GBP"
    assert got["price_text"] == "£51.77"


def test_price_regex_fallback():
    html = "<html><head><title>Shop</title></head><body><p>Only $19.99 today</p></body></html>"
    got = extract_html(html)
    assert got["price_text"] == "$19.99"
    assert got["price"] is None


def test_json_payload():
    got = extract_html('{"title":"Widget","price":12.5,"priceCurrency":"USD"}', "application/json")
    assert got["title"] == "Widget"
    assert got["price"] == "12.5"
    assert got["currency"] == "USD"
