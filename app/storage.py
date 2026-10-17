from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .normalize import PRODUCT_ORDER, zone_rank
from .provinces import BY_SLUG, PROVINCES


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read existing data file {path}: {exc}") from exc
    if not isinstance(value, list):
        raise ValueError(f"existing data file {path} is not a JSON array")
    return [item for item in value if isinstance(item, dict)]


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("date") or ""), str(row.get("zone") or "")


def merge_rows(existing: Iterable[dict[str, Any]], incoming: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for row in existing:
        if row.get("date"):
            merged[row_key(row)] = row
    for row in incoming:
        if row.get("date"):
            merged[row_key(row)] = row
    return sorted(
        merged.values(),
        key=lambda item: (
            str(item["date"]),
            zone_rank(str(item.get("zone") or "")),
            str(item.get("zone") or ""),
        ),
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, separators=(",", ": ")) + "\n"
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _ordered_products(rows: Iterable[dict[str, Any]]) -> list[str]:
    present = {key for row in rows for key in row if key not in {"date", "zone"}}
    return [key for key in PRODUCT_ORDER if key in present] + sorted(present - set(PRODUCT_ORDER))


def _ordered_zones(rows: Iterable[dict[str, Any]]) -> list[str]:
    zones = {str(row["zone"]) for row in rows if row.get("zone")}
    return sorted(zones, key=lambda name: (zone_rank(name), name))


def build_index(data_dir: Path, source_url: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    total_records = 0

    for path in sorted(data_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        slug = path.stem
        province = BY_SLUG.get(slug)
        rows = read_rows(path)
        if not rows:
            continue
        dates = [str(row["date"]) for row in rows if row.get("date")]
        products = _ordered_products(rows)
        entry: dict[str, Any] = {
            "slug": slug,
            "name": province.name if province else slug,
            "code": province.code if province else None,
            "file": path.name,
            "records": len(rows),
            "latest": max(dates) if dates else None,
            "earliest": min(dates) if dates else None,
            "products": products,
            "zones": _ordered_zones(rows),
        }
        entries.append(entry)
        total_records += len(rows)

    known_order = {province.slug: index for index, province in enumerate(PROVINCES)}
    entries.sort(key=lambda item: (known_order.get(item["slug"], 999), item["name"]))
    index_path = data_dir / "index.json"
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if (
            isinstance(existing, dict)
            and existing.get("provinces") == entries
            and existing.get("total_records") == total_records
        ):
            return existing

    index = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source_url,
        "total_records": total_records,
        "provinces": entries,
    }
    write_json(index_path, index)
    return index
