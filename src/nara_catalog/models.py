from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

MAX_SEARCH_LIMIT = 100


def to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_plain(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_plain(v) for v in value]
    return value


@dataclass(slots=True)
class KeyStatus:
    key_present: bool
    key_source: str | None
    api_base: str
    live_status: str | None = None
    total: int | None = None
    error: str | None = None


@dataclass(slots=True)
class RequestMetadata:
    endpoint: str
    params: dict[str, Any]
    fetched_at_epoch: int
    key_source: str | None = None


@dataclass(slots=True)
class SearchRequest:
    query: str
    limit: int = 10
    page: int = 1
    online: bool = False
    abbreviated: bool = False
    include_extracted_text: bool = False
    type_of_materials: str | None = None
    object_type: str | None = None
    record_group_number: str | None = None
    reference_units: str | None = None
    ancestor_naid: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    source_includes: str | None = None

    def __post_init__(self) -> None:
        if not str(self.query).strip():
            raise ValueError("query must not be empty")
        if self.limit < 1 or self.limit > MAX_SEARCH_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_SEARCH_LIMIT}")
        if self.page < 1:
            raise ValueError("page must be 1 or greater")


@dataclass(slots=True)
class DigitalObject:
    index: int
    object_type: str | None
    title: str | None
    file_name: str | None
    object_url: str | None
    thumbnail_url: str | None = None
    has_extracted_text: bool = False
    local_path: str | None = None
    downloaded: bool = False


@dataclass(slots=True)
class CompactRecord:
    na_id: str | None
    title: str | None
    level_of_description: str | None = None
    dates: Any = None
    type_of_materials: Any = None
    record_group_number: str | None = None
    collection_identifier: str | None = None
    available_online: bool | None = None
    digital_object_count: int = 0
    digital_objects: list[DigitalObject] = field(default_factory=list)
    ancestors: list[dict[str, Any]] = field(default_factory=list)
    catalog_url: str | None = None
    source_platform: str | None = None


@dataclass(slots=True)
class SearchResponse:
    request: RequestMetadata
    query: str
    total: int | None
    returned: int
    records: list[CompactRecord]
    raw: dict[str, Any]


@dataclass(slots=True)
class RecordResponse:
    request: RequestMetadata
    na_id: str
    found: bool
    record: dict[str, Any] | None
    compact: CompactRecord | None
    raw: dict[str, Any]


@dataclass(slots=True)
class DownloadResult:
    index: int
    url: str | None
    local_path: str | None
    sha256: str | None
    status: str
    bytes_written: int = 0
    error: str | None = None


@dataclass(slots=True)
class DownloadManifest:
    na_id: str
    destination: str
    results: list[DownloadResult]


@dataclass(slots=True)
class HierarchyResult:
    na_id: str
    ancestors: list[dict[str, Any]]
    parent: dict[str, Any] | None
    likely_series: dict[str, Any] | None
    siblings: SearchResponse | None = None


@dataclass(slots=True)
class RelatedRecordsResponse:
    na_id: str
    mode: str
    search: SearchResponse | None
    basis: dict[str, Any]


@dataclass(slots=True)
class SourcePacket:
    source_id: str
    na_id: str
    catalog_url: str
    raw_json_path: str
    raw_json_sha256: str
    downloaded_object_paths: list[str]
    downloaded_object_sha256: dict[str, str]
    packet_path: str
    suggested_registry_stub: str
    suggested_manifest_rows: list[str]
    rights_note: str


@dataclass(slots=True)
class NegativeSearchDraft:
    query: str
    filters: dict[str, Any]
    endpoint: str
    searched_at_epoch: int
    total_hits: int | None
    confidence: str
    markdown: str
