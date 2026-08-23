from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from extractcheck.normalize import collapse

PRICE_RE = re.compile(
    r"(?:(?<![A-Za-z])(?:USD|EUR|GBP|CAD|AUD|JPY)\s*)?"
    r"(?:₹|€|£|\$)\s*\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?"
    r"|\b\d{1,3}(?:,\d{3})*(?:\.\d{2})\s*(?:USD|EUR|GBP|CAD|AUD)\b",
    re.IGNORECASE,
)


def _text(node: Tag | None) -> str | None:
    if not node:
        return None
    value = collapse(node.get_text(" ", strip=True))
    return value or None


def _attr(node: Tag | None, name: str) -> str | None:
    if not node:
        return None
    raw = node.get(name)
    if isinstance(raw, list):
        raw = " ".join(str(x) for x in raw)
    value = collapse(raw)
    return value or None


def _meta(soup: BeautifulSoup, **attrs: str) -> str | None:
    tag = soup.find("meta", attrs=attrs)
    if not isinstance(tag, Tag):
        return None
    return _attr(tag, "content")


def _first_ld_items(blob: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                walk(child)
            return
        if not isinstance(node, dict):
            return
        graph = node.get("@graph")
        if graph:
            walk(graph)
        items.append(node)

    walk(blob)
    return items


def _types(node: dict[str, Any]) -> set[str]:
    raw = node.get("@type")
    if isinstance(raw, list):
        return {str(x).split("/")[-1].casefold() for x in raw}
    if raw:
        return {str(raw).split("/")[-1].casefold()}
    return set()


def _offer_fields(node: dict[str, Any]) -> tuple[str | None, str | None]:
    price = node.get("price")
    if price is None:
        price = node.get("lowPrice") or node.get("highPrice")
    currency = node.get("priceCurrency")
    return (
        collapse(price) or None,
        collapse(currency) or None,
    )


def _from_jsonld(soup: BeautifulSoup) -> dict[str, str | None]:
    name = price = currency = None
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            blob = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in _first_ld_items(blob):
            types = _types(item)
            if name is None and types & {"product", "offer"}:
                name = collapse(item.get("name")) or name
            offers = item.get("offers")
            offer_nodes: list[dict[str, Any]] = []
            if isinstance(offers, dict):
                offer_nodes = [offers]
            elif isinstance(offers, list):
                offer_nodes = [o for o in offers if isinstance(o, dict)]
            if types & {"offer"}:
                offer_nodes.append(item)
            for offer in offer_nodes:
                p, c = _offer_fields(offer)
                if price is None and p:
                    price = p
                if currency is None and c:
                    currency = c
            if name and price and currency:
                break
    return {"name": name, "price": price, "currency": currency}


def _price_text(html: str, soup: BeautifulSoup) -> str | None:
    for sel in (".price_color", ".price", "[itemprop=price]", ".product-price"):
        node = soup.select_one(sel)
        text = _text(node)
        if text and PRICE_RE.search(text):
            return PRICE_RE.search(text).group(0)
        if text and re.search(r"\d", text) and len(text) < 40:
            return text
    visible = soup.get_text(" ", strip=True)
    match = PRICE_RE.search(visible) or PRICE_RE.search(html)
    return match.group(0) if match else None


def extract_html(html: str, content_type: str = "text/html") -> dict[str, Any]:
    ctype = (content_type or "").lower()
    if "json" in ctype and "ld+json" not in ctype:
        try:
            data = json.loads(html)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            title = collapse(data.get("title") or data.get("name") or data.get("url")) or None
            return {
                "kind": "json",
                "title": title,
                "h1": None,
                "description": collapse(data.get("description")) or None,
                "canonical": collapse(data.get("url")) or None,
                "og:title": None,
                "og:description": None,
                "name": collapse(data.get("name")) or title,
                "price": collapse(data.get("price")) or None,
                "currency": collapse(data.get("currency") or data.get("priceCurrency")) or None,
                "price_text": None,
            }

    soup = BeautifulSoup(html, "lxml")
    title = _text(soup.find("title"))
    h1 = _text(soup.find("h1"))
    tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    description = _attr(tag, "content") if isinstance(tag, Tag) else None
    canon_tag = soup.find("link", rel=re.compile(r"canonical", re.I))
    canonical = _attr(canon_tag if isinstance(canon_tag, Tag) else None, "href")
    og_title = _meta(soup, property="og:title")
    og_description = _meta(soup, property="og:description")
    ld = _from_jsonld(soup)
    price_text = _price_text(html, soup)
    return {
        "kind": "html",
        "title": title,
        "h1": h1,
        "description": description,
        "canonical": canonical,
        "og:title": og_title,
        "og:description": og_description,
        "name": ld["name"],
        "price": ld["price"],
        "currency": ld["currency"],
        "price_text": price_text,
    }


def extract_from_bytes(raw: bytes, content_type: str = "text/html") -> dict[str, Any]:
    html = raw.decode("utf-8", errors="replace")
    return extract_html(html, content_type)
