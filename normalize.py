from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

_WS = re.compile(r"\s+")


def collapse(value: Any) -> str:
    if value is None:
        return ""
    return _WS.sub(" ", str(value)).strip()


def casefold_text(value: Any) -> str:
    return collapse(value).casefold()


def as_number(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    text = collapse(value)
    if not text:
        return None
    cleaned = re.sub(r"[^\d.,\-]", "", text)
    if cleaned.count(",") == 1 and cleaned.count(".") == 0:
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None
