"""Harder bakeoff: public priced pages, honest claim vs planted price lie."""
from __future__ import annotations

import json
import time
from pathlib import Path

from extractcheck.compare import compare_claim
from extractcheck.extract import extract_from_bytes
from extractcheck.fetch import fetch_url

DELAY = 0.4
OUT = Path("/workspace/extractcheck/bakeoff_hard.json")

URLS = [
    "http://books.toscrape.com/",
    "http://books.toscrape.com/catalogue/category/books_1/index.html",
    "http://books.toscrape.com/catalogue/category/books/travel_2/index.html",
    "http://books.toscrape.com/catalogue/category/books/mystery_3/index.html",
    "http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
    "http://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html",
    "http://books.toscrape.com/catalogue/soumission_998/index.html",
    "http://books.toscrape.com/catalogue/sharp-objects_997/index.html",
    "http://books.toscrape.com/catalogue/sapiens-a-brief-history-of-humankind_996/index.html",
    "http://books.toscrape.com/catalogue/the-requiem-red_995/index.html",
    "http://books.toscrape.com/catalogue/the-dirty-little-secrets-of-getting-your-dream-job_994/index.html",
    "http://books.toscrape.com/catalogue/the-coming-woman-a-novel-based-on-the-life-of-the-infamous-feminist-victoria-woodhull_993/index.html",
    "https://dummyjson.com/products/1",
    "https://fakestoreapi.com/products/1",
    "https://scrapeme.live/shop/",
]


def honest_claim(extract: dict) -> dict:
    claim: dict = {}
    for key in ("name", "title", "h1"):
        if extract.get(key):
            claim[key] = extract[key]
            break
    if extract.get("price") is not None:
        claim["price"] = extract["price"]
    if extract.get("currency"):
        claim["currency"] = extract["currency"]
    if extract.get("price_text"):
        claim["price_text"] = extract["price_text"]
    if not claim and extract.get("og:title"):
        claim["og:title"] = extract["og:title"]
    return claim


def planted_lie(extract: dict, honest: dict) -> dict:
    lie = dict(honest)
    if "price" in lie:
        lie["price"] = "999999.00"
    elif "price_text" in lie:
        lie["price_text"] = "$999,999.00"
    else:
        lie["price_text"] = "$999,999.00"
        if "title" in lie:
            lie["title"] = "TOTALLY FAKE TITLE 12345"
        elif "name" in lie:
            lie["name"] = "TOTALLY FAKE NAME 12345"
        elif "h1" in lie:
            lie["h1"] = "TOTALLY FAKE H1 12345"
    return lie


def main() -> None:
    rows = []
    for i, url in enumerate(URLS, 1):
        print(f"[{i}/{len(URLS)}] {url}", flush=True)
        got = fetch_url(url)
        time.sleep(DELAY)
        if not got.get("ok"):
            rows.append({"url": url, "fetched": False, "error": got.get("error")})
            continue
        extract = extract_from_bytes(got["raw"], got.get("content_type") or "text/html")
        honest = honest_claim(extract)
        lie = planted_lie(extract, honest)
        honest_r = compare_claim(honest, extract)
        lie_r = compare_claim(lie, extract)
        rows.append(
            {
                "url": url,
                "fetched": True,
                "http_status": got.get("http_status"),
                "sha256": got.get("snapshot_sha256"),
                "bytes": got.get("bytes"),
                "extract": extract,
                "honest_claim": honest,
                "lie_claim": lie,
                "honest_pass": honest_r["pass"],
                "lie_fail": not lie_r["pass"],
                "lie_diffs": lie_r["diffs"],
            }
        )

    fetched = [r for r in rows if r.get("fetched")]
    honest_ok = sum(1 for r in fetched if r["honest_pass"])
    lie_ok = sum(1 for r in fetched if r["lie_fail"])
    n = len(fetched)
    honest_rate = (honest_ok / n) if n else 0.0
    lie_rate = (lie_ok / n) if n else 0.0
    reasons = []
    if n < 8:
        reasons.append(f"fewer than 8 pages fetched ({n})")
    if lie_rate < 0.85:
        reasons.append(f"lie_catch_rate {lie_rate:.3f} < 0.85")
    if honest_rate < 0.75:
        reasons.append(f"honest_pass_rate {honest_rate:.3f} < 0.75")
    summary = {
        "urls": len(URLS),
        "fetched": n,
        "fetch_failures": len(rows) - n,
        "honest_pass": honest_ok,
        "honest_pass_rate": honest_rate,
        "lies_caught": lie_ok,
        "lie_catch_rate": lie_rate,
        "kill": bool(reasons),
        "kill_reasons": reasons,
    }
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {OUT}")
    if reasons:
        print("KILL CRITERIA HIT: " + "; ".join(reasons))


if __name__ == "__main__":
    main()
