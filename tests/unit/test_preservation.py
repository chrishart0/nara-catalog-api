from __future__ import annotations

from pathlib import Path

import pytest

from nara_catalog.models import DownloadManifest, DownloadResult, SearchRequest
from nara_catalog.preservation import make_negative_search_draft
from nara_catalog.service import NaraCatalogService
from tests.conftest import load_fixture


class FakeClient:
    def __init__(self, response):
        self.response = response

    def search(self, params, *, timeout=None):
        return self.response


def test_negative_search_draft_contains_query_filters_and_count() -> None:
    draft = make_negative_search_draft(SearchRequest(query="Variell", online=True), 0)

    assert "Variell" in draft.markdown
    assert draft.total_hits == 0
    assert draft.filters["online"] is True


def test_source_packet_writes_raw_json_and_markdown(tmp_path: Path) -> None:
    service = NaraCatalogService(FakeClient(load_fixture("record_passport_with_digital_objects.json")), key_source="test")
    assert not (tmp_path / "archive" / "nara").exists()

    packet = service.make_source_packet("235845496", "S061", tmp_path)

    assert (tmp_path / "archive" / "nara" / "S061").is_dir()
    assert Path(packet.raw_json_path).exists()
    assert Path(packet.packet_path).exists()
    assert packet.raw_json_sha256
    assert packet.downloaded_object_paths == []
    assert packet.downloaded_object_sha256 == {}
    assert "S061:" in packet.suggested_registry_stub
    packet_text = Path(packet.packet_path).read_text()
    assert "API path" in packet_text
    assert "naId_is" in packet_text


def test_source_packet_rejects_invalid_source_id(tmp_path: Path) -> None:
    service = NaraCatalogService(FakeClient(load_fixture("record_passport_with_digital_objects.json")), key_source="test")

    with pytest.raises(ValueError, match="source_id"):
        service.make_source_packet("235845496", "../S061", tmp_path)


def test_source_packet_refuses_existing_markdown_without_writing_raw_json(tmp_path: Path) -> None:
    service = NaraCatalogService(FakeClient(load_fixture("record_passport_with_digital_objects.json")), key_source="test")
    packet_dir = tmp_path / "archive" / "nara" / "S061"
    packet_dir.mkdir(parents=True)
    existing_packet = packet_dir / "S061-nara-235845496-source-packet.md"
    existing_packet.write_text("preserved")

    with pytest.raises(FileExistsError):
        service.make_source_packet("235845496", "S061", tmp_path)

    assert existing_packet.read_text() == "preserved"
    assert not (packet_dir / "S061-nara-235845496.json").exists()


def test_source_packet_includes_download_manifest_paths_and_hashes(tmp_path: Path) -> None:
    service = NaraCatalogService(FakeClient(load_fixture("record_passport_with_digital_objects.json")), key_source="test")
    manifest = DownloadManifest(
        na_id="235845496",
        destination=str(tmp_path / "downloads"),
        results=[DownloadResult(1, "https://example.test/1.jpg", str(tmp_path / "downloads" / "1.jpg"), "abc123", "downloaded", 3)],
    )

    packet = service.make_source_packet("235845496", "S061", tmp_path, download_manifest=manifest)

    assert packet.downloaded_object_paths == [str(tmp_path / "downloads" / "1.jpg")]
    assert packet.downloaded_object_sha256[str(tmp_path / "downloads" / "1.jpg")] == "abc123"
    assert "abc123" in Path(packet.packet_path).read_text()
