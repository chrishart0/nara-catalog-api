from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from .models import DigitalObject, DownloadManifest, DownloadResult, to_plain


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    value = re.sub(r"-{2,}", "-", value).strip(".-")
    return value or "file"


def select_objects(objects: list[DigitalObject], selection: str | None = None) -> list[DigitalObject]:
    if selection in (None, "", "all"):
        return objects
    wanted: set[int] = set()
    for part in selection.split(","):
        item = part.strip()
        if not item:
            continue
        if "-" in item:
            start, end = item.split("-", 1)
            wanted.update(range(int(start), int(end) + 1))
        else:
            wanted.add(int(item))
    return [obj for obj in objects if obj.index in wanted]


def destination_name(na_id: str, obj: DigitalObject) -> str:
    ext = _extension(obj.object_url or obj.file_name)
    title = safe_filename(obj.file_name or obj.title or f"object-{obj.index}")
    stem = title.rsplit(".", 1)[0] if "." in title else title
    return f"nara-{na_id}-img{obj.index:04d}-{stem}{ext}"


def download_objects(
    *,
    na_id: str,
    objects: list[DigitalObject],
    destination: Path,
    selection: str | None = None,
    force: bool = False,
    timeout: int = 60,
) -> DownloadManifest:
    destination.mkdir(parents=True, exist_ok=True)
    selected = select_objects(objects, selection)
    results: list[DownloadResult] = []
    for obj in selected:
        if not obj.object_url:
            results.append(DownloadResult(obj.index, None, None, None, "skipped_no_url"))
            continue
        path = destination / destination_name(na_id, obj)
        if path.exists() and not force:
            results.append(DownloadResult(obj.index, obj.object_url, str(path), sha256_file(path), "skipped_exists"))
            continue
        try:
            response = requests.get(obj.object_url, timeout=timeout)
            response.raise_for_status()
            path.write_bytes(response.content)
            results.append(DownloadResult(
                index=obj.index,
                url=obj.object_url,
                local_path=str(path),
                sha256=sha256_file(path),
                status="downloaded",
                bytes_written=len(response.content),
            ))
        except Exception as exc:
            results.append(DownloadResult(obj.index, obj.object_url, str(path), None, "failed", error=str(exc)[:500]))
    manifest = DownloadManifest(na_id=na_id, destination=str(destination), results=results)
    manifest_path = destination / f"nara-{na_id}-download-manifest.json"
    manifest_path.write_text(json.dumps(to_plain(manifest), indent=2, ensure_ascii=False) + "\n")
    return manifest


def _extension(value: str | None) -> str:
    if not value:
        return ".bin"
    path = urlparse(value).path
    name = Path(path).name
    if "." not in name:
        return ".bin"
    suffix = Path(name).suffix
    return suffix if suffix else ".bin"
