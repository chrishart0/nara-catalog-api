from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from . import parse
from .models import CompactRecord, DigitalObject


def summarize_digital_objects(objs: Any, limit: int | None = 5) -> list[DigitalObject]:
    if not isinstance(objs, list):
        return []
    out: list[DigitalObject] = []
    selected = objs if limit is None else objs[:limit]
    for i, obj in enumerate(selected, 1):
        if not isinstance(obj, dict):
            continue
        url = obj.get("objectUrl") or obj.get("url") or obj.get("fileUrl")
        file_name = obj.get("fileName") or _file_name_from_url(url)
        out.append(DigitalObject(
            index=i,
            object_type=obj.get("objectType"),
            title=obj.get("title") or obj.get("caption"),
            file_name=file_name,
            object_url=url,
            thumbnail_url=obj.get("thumbnailUrl"),
            has_extracted_text=bool(obj.get("extractedText") or obj.get("otherExtractedText")),
        ))
    return out


def compact_record_from_hit(hit: dict[str, Any], *, digital_object_limit: int | None = 5) -> CompactRecord:
    record = parse.record_from_hit(hit)
    return compact_record(record, fallback_naid=hit.get("_id"), digital_object_limit=digital_object_limit)


def compact_record(
    record: dict[str, Any],
    *,
    fallback_naid: Any = None,
    digital_object_limit: int | None = 5,
) -> CompactRecord:
    na_id = parse.naid(record, fallback=fallback_naid)
    digital_objects = parse.digital_objects(record)
    return CompactRecord(
        na_id=na_id,
        title=parse.title(record),
        level_of_description=record.get("levelOfDescription") or record.get("descriptionType"),
        dates=record.get("dates") or record.get("date") or record.get("inclusiveDates"),
        type_of_materials=record.get("typeOfMaterials"),
        record_group_number=record.get("recordGroupNumber"),
        collection_identifier=record.get("collectionIdentifier"),
        available_online=record.get("availableOnline"),
        digital_object_count=int(record.get("digitalObjectCount") or len(digital_objects)),
        digital_objects=summarize_digital_objects(digital_objects, limit=digital_object_limit),
        ancestors=parse.ancestors(record),
        catalog_url=parse.catalog_url(na_id),
        source_platform=_guess_source_platform(digital_objects),
    )


def _file_name_from_url(url: str | None) -> str | None:
    if not url:
        return None
    path = urlparse(url).path
    name = PurePosixPath(path).name
    return name or None


def _guess_source_platform(objs: list[dict[str, Any]]) -> str | None:
    text = " ".join(str(o.get("objectUrl") or o.get("url") or o.get("fileUrl") or "") for o in objs if isinstance(o, dict))
    lowered = text.lower()
    if "fold3" in lowered:
        return "Fold3"
    if "ancestry" in lowered:
        return "Ancestry"
    return None
