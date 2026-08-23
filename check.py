#!/usr/bin/env python3
"""ExtractCheck bakeoff: catch planted lies in claimed page extracts."""
from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

UA = "ExtractCheckBakeoff/0.1 (+research; not a crawler product)"
TIMEOUT = 12
CTX = ssl.create_default_context()

URLS = [
    "https://example.com/",
    "https://www.wikipedia.org/",
    "https://en.wikipedia.org/wiki/HTTP",
    "https://github.com/",
    "https://docs.python.org/3/",
    "https://httpbin.org/html",
    "https://news.ycombinator.com/",
    "https://www.rfc-editor.org/rfc/rfc9110",
    "https://developer.mozilla.org/en-US/docs/Web/HTTP",
    "https://www.w3.org/",
    "https://nodejs.org/en",
    "https://go.dev/",
    "https://www.rust-lang.org/",
    "https://www.ietf.org/",
    "https://httpbin.org/get",
    "https://en.wikipedia.org/wiki/Python_(programming_language)",
    "https://www.iana.org/",
    "https://www.gutenberg.org/",
    "https://jsonplaceholder.typicode.com/",
    "https://www.cloudflare.com/",
]


class TitleH1Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self._in_h1 = False
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self._h1_done = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if tag == "h1" and not self._h1_done:
            self._in_h1 = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "h1" and self._in_h1:
            self._in_h1 = False
            self._h1_done = True

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if self._in_h1:
            self.h1_parts.append(data)


def norm(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def extract(html: str, content_type: str, raw: bytes) -> dict:
    if "json" in content_type or (raw[:1] in (b"{", b"[")):
        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
            title = None
            if isinstance(data, dict):
                title = str(data.get("url") or data.get("title") or data.get("id") or "json")
            return {"title": title or "json", "h1": None, "kind": "json"}
        except json.JSONDecodeError:
            pass
    parser = TitleH1Parser()
    try:
        parser.feed(html)
    except Exception:
        pass
    title = "".join(parser.title_parts).strip() or None
    h1 = "".join(parser.h1_parts).strip() or None
    return {"title": title, "h1": h1, "kind": "html"}


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as resp:
            raw = resp.read(2_000_000)
            ctype = resp.headers.get("Content-Type", "")
            status = resp.status
            final = resp.geturl()
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"http {e.code}", "http_status": e.code}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}

    html = raw.decode("utf-8", errors="replace")
    if not raw.strip():
        return {"ok": False, "error": "empty body", "http_status": status}

    fields = extract(html, ctype, raw)
    if not fields.get("title") and not fields.get("h1"):
        # last-ditch: first 80 chars of text-ish
        text = re.sub(r"<[^>]+>", " ", html)
        text = norm(text)[:80]
        if not text:
            return {"ok": False, "error": "no extractable fields", "http_status": status}
        fields["title"] = text

    return {
        "ok": True,
        "http_status": status,
        "final_url": final,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "extract": fields,
    }


def compare(claim: dict, found: dict) -> dict:
    diffs = []
    passed = True
    for key in ("title", "h1"):
        if key not in claim:
            continue
        c, f = claim.get(key), found.get(key)
        if norm(c) != norm(f):
            passed = False
            diffs.append({"path": key, "claimed": c, "found": f})
    return {"pass": passed, "diffs": diffs}


def main() -> None:
    rows = []
    for i, url in enumerate(URLS, 1):
        print(f"[{i}/20] {url}", flush=True)
        got = fetch(url)
        time.sleep(0.4)
        if not got.get("ok"):
            rows.append({"url": url, "fetched": False, "error": got.get("error")})
            continue
        honest = {
            k: got["extract"][k]
            for k in ("title", "h1")
            if got["extract"].get(k)
        }
        lie = dict(honest)
        if "title" in lie:
            lie["title"] = "TOTALLY FAKE TITLE 12345"
        elif "h1" in lie:
            lie["h1"] = "TOTALLY FAKE H1 12345"
        honest_r = compare(honest, got["extract"])
        lie_r = compare(lie, got["extract"])
        rows.append(
            {
                "url": url,
                "fetched": True,
                "http_status": got["http_status"],
                "sha256": got["sha256"],
                "bytes": got["bytes"],
                "extract": got["extract"],
                "honest_pass": honest_r["pass"],
                "lie_fail": not lie_r["pass"],
                "lie_diffs": lie_r["diffs"],
            }
        )

    fetched = [r for r in rows if r.get("fetched")]
    honest_ok = sum(1 for r in fetched if r["honest_pass"])
    lie_ok = sum(1 for r in fetched if r["lie_fail"])
    summary = {
        "urls": len(URLS),
        "fetched": len(fetched),
        "fetch_failures": len(rows) - len(fetched),
        "honest_pass": honest_ok,
        "honest_pass_rate": (honest_ok / len(fetched)) if fetched else 0,
        "lies_caught": lie_ok,
        "lie_catch_rate": (lie_ok / len(fetched)) if fetched else 0,
        "kill": (not fetched) or (lie_ok / len(fetched) < 0.9) or (honest_ok / len(fetched) < 0.9),
    }
    out = {"summary": summary, "rows": rows}
    path = Path("/workspace/extractcheck/bakeoff.json")
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
