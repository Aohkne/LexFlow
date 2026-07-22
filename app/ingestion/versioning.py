"""Versioning Engine: xác định điều khoản nào đang hiệu lực tại một thời điểm.

Nguyên tắc: một chunk hiệu lực tại `as_of` nếu:
  valid_from <= as_of  AND  (valid_to rỗng HOẶC as_of <= valid_to)  AND  not superseded
Điều khoản không có valid_from riêng thì kế thừa của văn bản.
"""
from __future__ import annotations

from datetime import date


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return None


def today_iso() -> str:
    return date.today().isoformat()


def is_effective(
    valid_from: str | None,
    valid_to: str | None,
    superseded: bool,
    as_of: str | None = None,
) -> bool:
    """Điều khoản có đang hiệu lực tại thời điểm `as_of` không."""
    if superseded:
        return False
    ref = parse_date(as_of) or date.today()
    vf = parse_date(valid_from)
    vt = parse_date(valid_to)
    if vf and ref < vf:
        return False
    if vt and ref > vt:
        return False
    return True


def effective_dates(
    article_from: str | None,
    article_to: str | None,
    article_superseded: bool,
    doc_from: str | None,
    doc_to: str | None,
) -> tuple[str | None, str | None, bool]:
    """Gộp hiệu lực cấp điều khoản với cấp văn bản (điều khoản override)."""
    vf = article_from or doc_from
    vt = article_to or doc_to
    return vf, vt, article_superseded
