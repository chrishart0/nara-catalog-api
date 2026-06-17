from __future__ import annotations

import pytest

from nara_catalog import mcp_server
from nara_catalog.service import MissingApiKeyError


def test_mcp_module_imports_without_optional_dependency() -> None:
    assert callable(mcp_server.create_server)


def test_mcp_safe_removes_key_source_recursively() -> None:
    data = mcp_server.mcp_safe({"request": {"key_source": "/secret/path", "params": {"q": "Variell"}}})

    assert data == {"request": {"params": {"q": "Variell"}}}


def test_mcp_safe_scrubs_absolute_paths_relative_to_write_root(tmp_path) -> None:
    root = tmp_path / "root"
    path = root / "downloads" / "file.jpg"
    data = mcp_server.mcp_safe(
        {
            "destination": str(root / "downloads"),
            "downloaded_object_paths": [str(path)],
            "suggested_manifest_rows": [f"| {path} | hash | note |"],
            "downloaded_object_sha256": {str(path): "hash"},
        },
        write_root=root,
    )

    assert data["destination"] == "downloads"
    assert data["downloaded_object_paths"] == ["downloads/file.jpg"]
    assert str(root) not in data["suggested_manifest_rows"][0]
    assert data["downloaded_object_sha256"] == {"downloads/file.jpg": "hash"}


def test_mcp_write_root_requires_env(monkeypatch) -> None:
    monkeypatch.delenv("NARA_MCP_WRITE_ROOT", raising=False)

    with pytest.raises(mcp_server.McpConfigurationError):
        mcp_server.mcp_write_root()


def test_mcp_path_under_write_root_rejects_escape(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(ValueError):
        mcp_server.path_under_write_root(str(tmp_path / "outside"), root)


def test_mcp_missing_key_error_is_sanitized(monkeypatch) -> None:
    def raise_missing(*args, **kwargs):
        raise MissingApiKeyError("/tmp/secret/nara.env")

    monkeypatch.setattr(mcp_server.NaraCatalogService, "from_environment", raise_missing)

    with pytest.raises(RuntimeError) as exc:
        mcp_server.service_from_environment()

    assert "NARA_API_KEY missing" in str(exc.value)
    assert "/tmp/secret" not in str(exc.value)


def test_create_server_reports_missing_dependency_when_mcp_not_installed() -> None:
    try:
        import mcp  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="optional MCP dependency"):
            mcp_server.create_server()


def test_mcp_contract_registration_with_sdk_when_available() -> None:
    try:
        import mcp  # noqa: F401
    except ImportError:
        pytest.skip("mcp SDK is not installed")

    import asyncio

    async def inspect_contract():
        server = mcp_server.create_server()
        tools = await server.list_tools()
        resources = await server.list_resource_templates()
        prompts = await server.list_prompts()
        return (
            {tool.name for tool in tools},
            {str(resource.uriTemplate) for resource in resources},
            {prompt.name for prompt in prompts},
        )

    tools, resources, prompts = asyncio.run(inspect_contract())

    assert {
        "nara_check_key",
        "nara_search_records",
        "nara_count_records",
        "nara_get_record",
        "nara_list_digital_objects",
        "nara_download_digital_objects",
        "nara_browse_hierarchy",
        "nara_find_related_records",
        "nara_make_source_packet",
        "nara_make_negative_search_record",
    } <= tools
    assert {
        "nara://record/{naid}",
        "nara://record/{naid}/compact",
        "nara://record/{naid}/digital-objects",
        "nara://search/{encoded_query}",
    } <= resources
    assert {
        "nara_person_search_plan",
        "nara_source_note_from_record",
        "nara_negative_search_log",
        "nara_passport_record_review",
    } <= prompts
