from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote

from .models import SearchRequest, to_plain
from .service import MissingApiKeyError, NaraCatalogService


PATH_KEYS = {"local_path", "raw_json_path", "packet_path", "destination"}
LIST_PATH_KEYS = {"downloaded_object_paths"}


class McpConfigurationError(RuntimeError):
    pass


def mcp_safe(value, *, write_root: Path | None = None):
    """Return MCP-safe structured data without key source labels or secret paths."""
    data = to_plain(value)
    return _scrub(data, write_root=write_root)


def _scrub(value, *, key: str | None = None, write_root: Path | None = None):
    if isinstance(value, dict):
        if key == "downloaded_object_sha256":
            return {_scrub_path(str(k), write_root): _scrub(v, write_root=write_root) for k, v in value.items()}
        return {k: _scrub(v, key=k, write_root=write_root) for k, v in value.items() if k != "key_source"}
    if isinstance(value, list):
        return [_scrub(v, key=key, write_root=write_root) for v in value]
    if key in PATH_KEYS and isinstance(value, str):
        return _scrub_path(value, write_root)
    if key in LIST_PATH_KEYS and isinstance(value, str):
        return _scrub_path(value, write_root)
    if isinstance(value, str) and write_root:
        return value.replace(str(write_root.resolve()) + "/", "")
    return value


def _scrub_path(value: str, write_root: Path | None) -> str:
    path = Path(value)
    if not path.is_absolute():
        return value
    if write_root:
        try:
            return str(path.resolve().relative_to(write_root.resolve()))
        except ValueError:
            pass
    return "<local-path-redacted>"


def service_from_environment() -> NaraCatalogService:
    try:
        return NaraCatalogService.from_environment(project_dir=Path.cwd())
    except MissingApiKeyError as exc:
        raise RuntimeError("NARA_API_KEY missing or not readable") from exc


def mcp_write_root() -> Path:
    value = os.environ.get("NARA_MCP_WRITE_ROOT")
    if not value:
        raise McpConfigurationError("MCP write tools require NARA_MCP_WRITE_ROOT")
    root = Path(value).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def path_under_write_root(value: str, root: Path) -> Path:
    candidate = Path(value).expanduser()
    path = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if not path.is_relative_to(root):
        raise ValueError("MCP write path must stay under NARA_MCP_WRITE_ROOT")
    return path


def create_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Install the optional MCP dependency with: pip install '.[mcp]'") from exc

    mcp = FastMCP("nara-catalog", json_response=True)

    @mcp.tool()
    def nara_check_key(live: bool = False) -> dict:
        """Check whether a NARA API key is configured without returning the key."""
        return mcp_safe(NaraCatalogService.check_key(live=live))

    @mcp.tool()
    def nara_search_records(query: str, online: bool = True, limit: int = 10, page: int = 1) -> dict:
        """Search NARA Catalog records and return normalized compact records."""
        service = service_from_environment()
        return mcp_safe(service.search_records(SearchRequest(query=query, online=online, limit=limit, page=page)))

    @mcp.tool()
    def nara_count_records(query: str, online: bool = True) -> dict:
        """Return a count-focused NARA Catalog search result."""
        service = service_from_environment()
        return mcp_safe(service.count_records(SearchRequest(query=query, online=online)))

    @mcp.tool()
    def nara_get_record(naid: str, include_extracted_text: bool = False) -> dict:
        """Fetch one NARA Catalog record by NAID."""
        service = service_from_environment()
        return mcp_safe(service.get_record(naid, include_extracted_text=include_extracted_text))

    @mcp.tool()
    def nara_list_digital_objects(naid: str) -> dict:
        """List digital objects for a NARA Catalog record."""
        service = service_from_environment()
        return mcp_safe({"naid": naid, "digital_objects": service.list_digital_objects(naid)})

    @mcp.tool()
    def nara_download_digital_objects(naid: str, destination: str, selection: str = "all", force: bool = False) -> dict:
        """Download selected digital objects for a NARA record into an explicit local destination."""
        root = mcp_write_root()
        service = service_from_environment()
        manifest = service.download_digital_objects(naid, path_under_write_root(destination, root), selection=selection, force=force)
        return mcp_safe(manifest, write_root=root)

    @mcp.tool()
    def nara_browse_hierarchy(naid: str) -> dict:
        """Show ancestor, parent, and likely series context for a NAID."""
        service = service_from_environment()
        return mcp_safe(service.browse_hierarchy(naid))

    @mcp.tool()
    def nara_find_related_records(naid: str, mode: str = "same-parent", limit: int = 10) -> dict:
        """Find records related by parent, series, record group, or similar title."""
        service = service_from_environment()
        return mcp_safe(service.find_related_records(naid, mode=mode, limit=limit))

    @mcp.tool()
    def nara_make_source_packet(naid: str, source_id: str, archive_root: str) -> dict:
        """Create a repository-style NARA source-packet draft."""
        root = mcp_write_root()
        service = service_from_environment()
        packet = service.make_source_packet(naid, source_id, path_under_write_root(archive_root, root))
        return mcp_safe(packet, write_root=root)

    @mcp.tool()
    def nara_make_negative_search_record(query: str, online: bool = True, threshold: int = 0) -> dict:
        """Create a negative-search draft from a NARA query and filters."""
        service = service_from_environment()
        return mcp_safe(service.make_negative_search_record(SearchRequest(query=query, online=online), threshold=threshold))

    @mcp.resource("nara://record/{naid}")
    def nara_record_resource(naid: str) -> dict:
        service = service_from_environment()
        return mcp_safe(service.get_record(naid))

    @mcp.resource("nara://record/{naid}/compact")
    def nara_record_compact_resource(naid: str) -> dict:
        service = service_from_environment()
        return mcp_safe(service.get_record(naid).compact)

    @mcp.resource("nara://record/{naid}/digital-objects")
    def nara_record_objects_resource(naid: str) -> dict:
        service = service_from_environment()
        return mcp_safe({"naid": naid, "digital_objects": service.list_digital_objects(naid)})

    @mcp.resource("nara://search/{encoded_query}")
    def nara_search_resource(encoded_query: str) -> dict:
        service = service_from_environment()
        return mcp_safe(service.search_records(SearchRequest(query=unquote(encoded_query), online=True, limit=10)))

    @mcp.prompt()
    def nara_person_search_plan(person_name: str) -> str:
        return (
            f"Plan NARA searches for {person_name}. Include name variants, online-only searches, "
            "passport/state department terms, count-only scoping, and negative-search logging."
        )

    @mcp.prompt()
    def nara_source_note_from_record(naid: str) -> str:
        return f"Draft a source note from NARA NAID {naid}. Separate metadata from historical claims."

    @mcp.prompt()
    def nara_negative_search_log(query: str) -> str:
        return f"Draft a negative-search log entry for this NARA query: {query}"

    @mcp.prompt()
    def nara_passport_record_review(naid: str) -> str:
        return f"Review NARA passport-related record {naid}; extract only source-supported facts."

    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
