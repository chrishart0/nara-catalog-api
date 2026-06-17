from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import NegativeSearchDraft, RecordResponse, SearchRequest, SourcePacket, to_plain

RIGHTS_NOTE = (
    "NARA Catalog metadata and public digital objects should be attributed to the "
    "National Archives and Records Administration. Verify item-level rights and use "
    "restrictions before publication."
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_source_packet(record: RecordResponse, source_id: str, archive_root: Path) -> SourcePacket:
    if not record.found or not record.record or not record.compact:
        raise ValueError(f"NAID {record.na_id} was not found")
    packet_dir = archive_root / "archive" / "nara" / source_id
    packet_dir.mkdir(parents=True, exist_ok=True)
    raw_text = json.dumps(to_plain(record.raw), indent=2, ensure_ascii=False) + "\n"
    raw_json_path = packet_dir / f"{source_id}-nara-{record.na_id}.json"
    if raw_json_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing source packet file: {raw_json_path}")
    raw_json_path.write_text(raw_text)
    raw_hash = sha256_text(raw_text)
    packet_path = packet_dir / f"{source_id}-nara-{record.na_id}-source-packet.md"
    registry_stub = _registry_stub(record, source_id, raw_json_path, raw_hash)
    manifest_rows = [f"| {raw_json_path} | {raw_hash} | NARA API raw JSON for NAID {record.na_id} |"]
    packet_text = (
        f"# {source_id} NARA Source Packet\n\n"
        f"- Source ID: {source_id}\n"
        f"- NAID: {record.na_id}\n"
        f"- Catalog URL: {record.compact.catalog_url}\n"
        f"- Title: {record.compact.title}\n"
        f"- API path: `{record.request.endpoint}`\n"
        f"- API request params: `{json.dumps(record.request.params, sort_keys=True)}`\n"
        f"- Fetched epoch: {record.request.fetched_at_epoch}\n"
        f"- Raw JSON: `{raw_json_path}`\n"
        f"- Raw JSON SHA-256: `{raw_hash}`\n\n"
        "## Downloaded Objects\n\n"
        "None recorded in this source packet. Use `images --download-dir` to download digital objects, then register those files in the manifest.\n\n"
        "## Suggested Registry Stub\n\n"
        "```yaml\n"
        f"{registry_stub}"
        "```\n\n"
        "## Suggested Manifest Rows\n\n"
        + "\n".join(manifest_rows)
        + "\n\n## Rights / Use\n\n"
        + RIGHTS_NOTE
        + "\n\n## Gaps\n\n- Verify citation details and item-level rights.\n\n## Next Actions\n\n- Extract facts into the fact ledger before narrative use.\n"
    )
    packet_path.write_text(packet_text)
    return SourcePacket(
        source_id=source_id,
        na_id=record.na_id,
        catalog_url=record.compact.catalog_url or "",
        raw_json_path=str(raw_json_path),
        raw_json_sha256=raw_hash,
        downloaded_object_paths=[],
        downloaded_object_sha256={},
        packet_path=str(packet_path),
        suggested_registry_stub=registry_stub,
        suggested_manifest_rows=manifest_rows,
        rights_note=RIGHTS_NOTE,
    )


def make_negative_search_draft(request: SearchRequest, total_hits: int | None, confidence: str = "searched-no-record") -> NegativeSearchDraft:
    filters = {k: v for k, v in asdict(request).items() if k != "query" and v not in (None, False)}
    searched_at = int(time.time())
    markdown = (
        "## NARA Negative Search Draft\n\n"
        f"- Query: `{request.query}`\n"
        f"- Endpoint: `/records/search`\n"
        f"- Filters: `{json.dumps(filters, sort_keys=True)}`\n"
        f"- Date searched epoch: {searched_at}\n"
        f"- Total hits: {total_hits}\n"
        "- False positives inspected: not recorded\n"
        "- Scope limits: NARA Catalog API only; result quality depends on catalog metadata and OCR.\n"
        f"- Confidence: {confidence}\n"
        "- Related tickets/source IDs: TBD\n"
        "- Next action: Review query variants or close as searched-no-record if scope is adequate.\n"
    )
    return NegativeSearchDraft(
        query=request.query,
        filters=filters,
        endpoint="/records/search",
        searched_at_epoch=searched_at,
        total_hits=total_hits,
        confidence=confidence,
        markdown=markdown,
    )


def _registry_stub(record: RecordResponse, source_id: str, raw_json_path: Path, raw_hash: str) -> str:
    title = (record.compact.title if record.compact else None) or f"NARA NAID {record.na_id}"
    url = record.compact.catalog_url if record.compact else f"https://catalog.archives.gov/id/{record.na_id}"
    return (
        f"{source_id}:\n"
        f"  title: {json.dumps(title)}\n"
        "  repository: National Archives and Records Administration\n"
        f"  catalog_url: {json.dumps(url)}\n"
        f"  naid: {json.dumps(record.na_id)}\n"
        f"  local_paths:\n"
        f"    - {json.dumps(str(raw_json_path))}\n"
        f"  sha256:\n"
        f"    {json.dumps(str(raw_json_path))}: {json.dumps(raw_hash)}\n"
        "  status: not-yet-verified\n"
    )
