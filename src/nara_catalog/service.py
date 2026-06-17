from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import compact, downloads, parse, preservation
from .client import BASE_URL, NaraCatalogClient
from .config import get_api_key
from .models import (
    CompactRecord,
    DownloadManifest,
    HierarchyResult,
    KeyStatus,
    NegativeSearchDraft,
    RecordResponse,
    RelatedRecordsResponse,
    RequestMetadata,
    SearchRequest,
    SearchResponse,
    SourcePacket,
)


class MissingApiKeyError(RuntimeError):
    def __init__(self, key_source: str) -> None:
        super().__init__(
            "NARA_API_KEY not found. Checked environment, project .env, and "
            f"{key_source}. Create a .env in the project root or request a key from Catalog_API@nara.gov."
        )

RELATED_MODES = {"same-parent", "same-series", "same-ancestor", "same-record-group", "similar-title", "references"}


def search_params(request: SearchRequest) -> dict[str, Any]:
    params: dict[str, Any] = {"q": request.query, "limit": request.limit, "page": request.page}
    if request.online:
        params["availableOnline"] = "true"
    if request.abbreviated:
        params["abbreviated"] = "true"
    if request.include_extracted_text:
        params["includeExtractedText"] = "true"
    if request.type_of_materials:
        params["typeOfMaterials"] = request.type_of_materials
    if request.object_type:
        params["objectType"] = request.object_type
    if request.record_group_number:
        params["recordGroupNumber"] = request.record_group_number
    if request.reference_units:
        params["referenceUnits"] = request.reference_units
    if request.ancestor_naid:
        params["ancestorNaId"] = request.ancestor_naid
    if request.start_date:
        params["startDate"] = request.start_date
    if request.end_date:
        params["endDate"] = request.end_date
    if request.source_includes:
        params["sourceIncludes"] = request.source_includes
    return params


class NaraCatalogService:
    def __init__(self, client: NaraCatalogClient, *, key_source: str | None = None) -> None:
        self.client = client
        self.key_source = key_source

    @classmethod
    def from_environment(
        cls,
        *,
        secret_file: str | None = None,
        project_dir: Path | None = None,
        timeout: int = 60,
    ) -> "NaraCatalogService":
        key, source = get_api_key(secret_file=secret_file, project_dir=project_dir)
        if not key:
            raise MissingApiKeyError(source)
        return cls(NaraCatalogClient(key, timeout=timeout), key_source=source)

    @classmethod
    def optional_from_environment(
        cls,
        *,
        secret_file: str | None = None,
        project_dir: Path | None = None,
        timeout: int = 60,
    ) -> tuple["NaraCatalogService | None", str | None]:
        key, source = get_api_key(secret_file=secret_file, project_dir=project_dir)
        if not key:
            return None, source
        return cls(NaraCatalogClient(key, timeout=timeout), key_source=source), source

    @staticmethod
    def check_key(
        *,
        live: bool = False,
        secret_file: str | None = None,
        require: bool = False,
        project_dir: Path | None = None,
    ) -> KeyStatus:
        service, source = NaraCatalogService.optional_from_environment(secret_file=secret_file, project_dir=project_dir)
        status = KeyStatus(key_present=bool(service), key_source=source if service else None, api_base=BASE_URL)
        if live and service:
            try:
                result = service.search_records(SearchRequest("constitution", limit=1, abbreviated=True))
                status.live_status = "ok"
                status.total = result.total
            except Exception as exc:
                status.live_status = "failed"
                status.error = str(exc)[:500]
        elif live:
            status.live_status = "skipped_no_key"
        if require and not service:
            status.error = status.error or "missing required NARA_API_KEY"
        return status

    def search_records(self, request: SearchRequest, *, timeout: int | None = None) -> SearchResponse:
        params = search_params(request)
        raw = self.client.search(params, timeout=timeout)
        hits = parse.search_hits(raw)
        records = [compact.compact_record_from_hit(hit) for hit in hits]
        return SearchResponse(
            request=RequestMetadata("/records/search", params, int(time.time()), self.key_source),
            query=request.query,
            total=parse.total_hits(raw),
            returned=len(hits),
            records=records,
            raw=raw,
        )

    def count_records(self, request: SearchRequest, *, timeout: int | None = None) -> SearchResponse:
        count_request = SearchRequest(**{**asdict(request), "limit": 1, "page": 1})
        return self.search_records(count_request, timeout=timeout)

    def get_record(self, na_id: str, *, include_extracted_text: bool = False, timeout: int | None = None) -> RecordResponse:
        params: dict[str, Any] = {"naId_is": na_id, "limit": 1}
        if include_extracted_text:
            params["includeExtractedText"] = "true"
        raw = self.client.search(params, timeout=timeout)
        hits = parse.search_hits(raw)
        record = parse.record_from_hit(hits[0]) if hits else None
        compact_record = compact.compact_record(record, digital_object_limit=5) if record else None
        return RecordResponse(
            request=RequestMetadata("/records/search", params, int(time.time()), self.key_source),
            na_id=na_id,
            found=bool(record),
            record=record,
            compact=compact_record,
            raw=raw,
        )

    def summarize_record(self, record: dict[str, Any]) -> CompactRecord:
        return compact.compact_record(record)

    def list_digital_objects(self, na_id: str, *, local_dir: Path | None = None, timeout: int | None = None) -> list:
        record = self.get_record(na_id, include_extracted_text=True, timeout=timeout)
        if not record.record:
            return []
        objects = compact.summarize_digital_objects(parse.digital_objects(record.record), limit=None)
        if local_dir:
            for obj in objects:
                path = local_dir / downloads.destination_name(na_id, obj)
                obj.local_path = str(path)
        return _mark_local_download_status(objects)

    def download_digital_objects(
        self,
        na_id: str,
        destination: Path,
        *,
        selection: str | None = None,
        force: bool = False,
        timeout: int = 60,
        max_bytes: int | None = None,
    ) -> DownloadManifest:
        objects = self.list_digital_objects(na_id, timeout=timeout)
        return downloads.download_objects(
            na_id=na_id,
            objects=objects,
            destination=destination,
            selection=selection,
            force=force,
            timeout=timeout,
            max_bytes=max_bytes,
        )

    def browse_hierarchy(
        self,
        na_id: str,
        *,
        include_siblings: bool = False,
        sibling_limit: int = 10,
        timeout: int | None = None,
    ) -> HierarchyResult:
        record = self.get_record(na_id, timeout=timeout)
        ancestors = record.compact.ancestors if record.compact else []
        parent = ancestors[-1] if ancestors else None
        likely_series = next((a for a in reversed(ancestors) if "series" in str(a.get("level") or "").lower()), None)
        siblings = None
        if include_siblings and parent and parent.get("naId"):
            siblings = self.search_records(SearchRequest(query="*", ancestor_naid=str(parent["naId"]), limit=sibling_limit), timeout=timeout)
        return HierarchyResult(na_id=na_id, ancestors=ancestors, parent=parent, likely_series=likely_series, siblings=siblings)

    def find_related_records(
        self,
        na_id: str,
        *,
        mode: str = "same-parent",
        limit: int = 10,
        timeout: int | None = None,
    ) -> RelatedRecordsResponse:
        if mode not in RELATED_MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(RELATED_MODES))}")
        record = self.get_record(na_id, timeout=timeout)
        hierarchy = _hierarchy_from_record(record)
        basis: dict[str, Any] = {}
        search: SearchResponse | None = None
        if mode == "same-parent" and hierarchy.parent and hierarchy.parent.get("naId"):
            basis = {"ancestor_naid": str(hierarchy.parent["naId"])}
            search = self.search_records(SearchRequest(query="*", ancestor_naid=basis["ancestor_naid"], limit=limit), timeout=timeout)
        elif mode in ("same-series", "same-ancestor") and hierarchy.likely_series and hierarchy.likely_series.get("naId"):
            basis = {"ancestor_naid": str(hierarchy.likely_series["naId"])}
            search = self.search_records(SearchRequest(query="*", ancestor_naid=basis["ancestor_naid"], limit=limit), timeout=timeout)
        elif mode == "same-record-group" and record.compact and record.compact.record_group_number:
            basis = {"record_group_number": record.compact.record_group_number}
            search = self.search_records(SearchRequest(query="*", record_group_number=record.compact.record_group_number, limit=limit), timeout=timeout)
        elif mode == "references":
            basis = {"query": na_id}
            search = self.search_records(SearchRequest(query=na_id, limit=limit), timeout=timeout)
        elif mode == "similar-title" and record.compact and record.compact.title:
            terms = " ".join(str(record.compact.title).split()[:6])
            basis = {"query": terms}
            search = self.search_records(SearchRequest(query=terms, limit=limit), timeout=timeout)
        return RelatedRecordsResponse(na_id=na_id, mode=mode, search=search, basis=basis)

    def make_source_packet(
        self,
        na_id: str,
        source_id: str,
        archive_root: Path,
        *,
        download_manifest: DownloadManifest | None = None,
        timeout: int | None = None,
    ) -> SourcePacket:
        record = self.get_record(na_id, include_extracted_text=True, timeout=timeout)
        return preservation.make_source_packet(record, source_id, archive_root, download_manifest=download_manifest)

    def make_negative_search_record(
        self,
        request: SearchRequest,
        *,
        threshold: int = 0,
        confidence: str = "searched-no-record",
        timeout: int | None = None,
    ) -> NegativeSearchDraft:
        result = self.count_records(request, timeout=timeout)
        if result.total is not None and result.total > threshold:
            confidence = "not-yet-verified"
        return preservation.make_negative_search_draft(request, result.total, confidence=confidence)


def _hierarchy_from_record(record: RecordResponse) -> HierarchyResult:
    ancestors = record.compact.ancestors if record.compact else []
    parent = ancestors[-1] if ancestors else None
    likely_series = next((a for a in reversed(ancestors) if "series" in str(a.get("level") or "").lower()), None)
    return HierarchyResult(na_id=record.na_id, ancestors=ancestors, parent=parent, likely_series=likely_series)


def _mark_local_download_status(objects: list) -> list:
    for obj in objects:
        if obj.local_path and Path(obj.local_path).exists():
            obj.downloaded = True
    return objects
