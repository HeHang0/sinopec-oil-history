from __future__ import annotations

import re
from typing import Any


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Output key -> candidate field names in the upstream JSON.
PRODUCT_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("89", ("GAS_89",)),
    ("92", ("GAS_92",)),
    ("95", ("GAS_95",)),
    ("98", ("GAS_98",)),
    ("E92", ("E92",)),
    ("E95", ("E95",)),
    ("E98", ("E98",)),
    ("aipao95", ("AIPAO_GAS_95", "AIPAO95")),
    ("aipao98", ("AIPAO_GAS_98", "AIPAO98")),
    ("aipao_e92", ("AIPAOE_GAS_92", "AIPAOE92")),
    ("aipao_e95", ("AIPAOE_GAS_95", "AIPAOE95")),
    ("aipao_e98", ("AIPAOE_GAS_98", "AIPAOE98")),
    ("0", ("CHECHAI_0", "CHAI_0")),
    ("-10", ("CHECHAI_10", "CHAI_10")),
    ("-20", ("CHAI_20", "CHECHAI_20")),
    ("-35", ("CHAI_35", "CHECHAI_35")),
)

PRODUCT_ORDER = [key for key, _ in PRODUCT_FIELDS]

ZONE_NUMERALS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _as_price(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        price = float(value)
    elif isinstance(value, str):
        try:
            price = float(value)
        except ValueError:
            return None
    else:
        return None
    if price <= 0:
        return None
    return round(price, 2)


def normalize_row(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert one upstream price period into the public JSON shape."""
    if not isinstance(raw, dict):
        return None
    date = str(raw.get("queryDate") or raw.get("STR_START_DATE") or "")[:10]
    if not DATE_RE.match(date):
        date = str(raw.get("START_TIME") or "")[:10]
    if not DATE_RE.match(date):
        return None

    row: dict[str, Any] = {"date": date}
    for key, candidates in PRODUCT_FIELDS:
        for field in candidates:
            price = _as_price(raw.get(field))
            if price is not None:
                row[key] = price
                break
    if len(row) == 1:
        return None
    return row


def zone_rank(name: str) -> int:
    for char in name:
        if char in ZONE_NUMERALS:
            return ZONE_NUMERALS[char]
    return 99


def parse_payload(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Extract province name and normalized history rows from initOilPrice."""
    if not isinstance(payload, dict):
        raise ValueError("upstream response is not an object")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("upstream response has no data object")

    check = data.get("provinceCheck") or {}
    province_name = str(check.get("PROVINCE_NAME") or "").strip()
    rows: list[dict[str, Any]] = []

    areas = data.get("area") or []
    if isinstance(areas, list):
        for index, area in enumerate(areas):
            if not isinstance(area, dict):
                continue
            area_check = area.get("areaCheck") or {}
            zone = str(area_check.get("AREA_NAME") or "").strip() or f"价区{index + 1}"
            for raw in area.get("areaData") or []:
                row = normalize_row(raw)
                if row is not None:
                    row["zone"] = zone
                    rows.append(row)

    if not rows:
        for raw in data.get("provinceData") or []:
            row = normalize_row(raw)
            if row is not None:
                rows.append(row)

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        deduped[(row["date"], str(row.get("zone") or ""))] = row
    ordered = sorted(
        deduped.values(),
        key=lambda item: (item["date"], zone_rank(str(item.get("zone") or "")), str(item.get("zone") or "")),
    )
    return province_name, ordered
