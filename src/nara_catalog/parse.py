from __future__ import annotations

from typing import Any


def hit_source(hit: dict[str, Any]) -> dict[str, Any]:
    return hit.get("_source") or hit.get("source") or hit


def record_from_hit(hit: dict[str, Any]) -> dict[str, Any]:
    source = hit_source(hit)
    return source.get("record") or source.get("metadata", {}).get("record") or source


def search_hits(data: dict[str, Any]) -> list[dict[str, Any]]:
    return (((data.get("body") or {}).get("hits") or {}).get("hits") or [])


def total_hits(data: dict[str, Any]) -> int | None:
    total = (((data.get("body") or {}).get("hits") or {}).get("total"))
    if isinstance(total, dict):
        value = total.get("value")
        return int(value) if value is not None else None
    if isinstance(total, int):
        return total
    return None


def naid(record: dict[str, Any], fallback: Any = None) -> str | None:
    control = record.get("controlGroup") or {}
    value = record.get("naId") or record.get("naIds") or control.get("naId") or fallback
    if isinstance(value, list):
        value = value[0] if value else None
    return str(value) if value is not None else None


def title(record: dict[str, Any]) -> str | None:
    value = record.get("title") or record.get("heading") or record.get("name")
    return str(value) if value is not None else None


def ancestors(record: dict[str, Any]) -> list[dict[str, Any]]:
    raw = record.get("ancestors") or []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append({
            "naId": item.get("naId"),
            "title": item.get("title"),
            "level": item.get("levelOfDescription") or item.get("descriptionType"),
        })
    return out


def digital_objects(record: dict[str, Any]) -> list[dict[str, Any]]:
    raw = record.get("digitalObjects") or []
    return raw if isinstance(raw, list) else []


def catalog_url(na_id: str | None) -> str | None:
    return f"https://catalog.archives.gov/id/{na_id}" if na_id else None
