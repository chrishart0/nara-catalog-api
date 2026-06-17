from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import DownloadManifest, NegativeSearchDraft, RecordResponse, SearchRequest, SourcePacket, to_plain

RIGHTS_NOTE = (
    "NARA Catalog metadata and public digital objects should be attributed to the "
    "National Archives and Records Administration. Verify item-level rights and use "
    "restrictions before publication."
)
SOURCE_ID_PATTERN = re.compile(r"^[SRCN]\d{3}[A-Za-z0-9_-]*$")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_source_id(source_id: str) -> str:
    if not SOURCE_ID_PATTERN.fullmatch(source_id):
        raise ValueError("source_id must match S###, R###, C###, or N### with optional letters/numbers/_/- suffix")
    return source_id


def make_source_packet(
    record: RecordResponse,
    source_id: str,
    archive_root: Path,
    *,
    download_manifest: DownloadManifest | None = None,
) -> SourcePacket:
    if not record.found or not record.record or not record.compact:
        raise ValueError(f"NAID {record.na_id} was not found")
    source_id = validate_source_id(source_id)
    archive_base = (archive_root / "archive" / "nara").resolve()
    packet_dir = (archive_base / source_id).resolve()
    if not packet_dir.is_relative_to(archive_base):
        raise ValueError("source packet path must stay under archive/nara")
    packet_dir.mkdir(parents=True, exist_ok=True)
    raw_text = json.dumps(to_plain(record.raw), indent=2, ensure_ascii=False) + "\n"
    raw_json_path = packet_dir / f"{source_id}-nara-{record.na_id}.json"
    packet_path = packet_dir / f"{source_id}-nara-{record.na_id}-source-packet.md"
    _preflight_no_overwrite([raw_json_path, packet_path])
    raw_hash = sha256_text(raw_text)
    downloaded_paths, downloaded_hashes, downloaded_text, manifest_rows = _downloaded_object_metadata(download_manifest)
    registry_stub = _registry_stub(record, source_id, raw_json_path, raw_hash)
    manifest_rows = [f"| {raw_json_path} | {raw_hash} | NARA API raw JSON for NAID {record.na_id} |", *manifest_rows]
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
        f"{downloaded_text}\n\n"
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
    _atomic_write_text(raw_json_path, raw_text)
    try:
        _atomic_write_text(packet_path, packet_text)
    except Exception:
        raw_json_path.unlink(missing_ok=True)
        raise
    return SourcePacket(
        source_id=source_id,
        na_id=record.na_id,
        catalog_url=record.compact.catalog_url or "",
        raw_json_path=str(raw_json_path),
        raw_json_sha256=raw_hash,
        downloaded_object_paths=downloaded_paths,
        downloaded_object_sha256=downloaded_hashes,
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


def _preflight_no_overwrite(paths: list[Path]) -> None:
    for path in paths:
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing source packet file: {path}")


def _atomic_write_text(path: Path, text: str) -> None:
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp_path.open("x", encoding="utf-8") as handle:
        handle.write(text)
    temp_path.replace(path)


def _downloaded_object_metadata(download_manifest: DownloadManifest | None) -> tuple[list[str], dict[str, str], str, list[str]]:
    if not download_manifest:
        return (
            [],
            {},
            "None recorded in this source packet. Use `images --download-dir` to download digital objects, then register those files in the manifest.",
            [],
        )
    paths: list[str] = []
    hashes: dict[str, str] = {}
    rows: list[str] = []
    lines: list[str] = []
    for result in download_manifest.results:
        if result.status != "downloaded" and result.status != "skipped_exists":
            continue
        if not result.local_path or not result.sha256:
            continue
        paths.append(result.local_path)
        hashes[result.local_path] = result.sha256
        rows.append(f"| {result.local_path} | {result.sha256} | NARA digital object {result.index} for NAID {download_manifest.na_id} |")
        lines.append(f"- `{result.local_path}` SHA-256 `{result.sha256}`")
    if not lines:
        lines.append("Download manifest was provided, but it contained no downloaded or existing hashed objects.")
    return paths, hashes, "\n".join(lines), rows
