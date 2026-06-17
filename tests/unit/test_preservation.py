from __future__ import annotations

from pathlib import Path

from nara_catalog.models import SearchRequest
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

    packet = service.make_source_packet("235845496", "S061", tmp_path)

    assert Path(packet.raw_json_path).exists()
    assert Path(packet.packet_path).exists()
    assert packet.raw_json_sha256
    assert packet.downloaded_object_paths == []
    assert packet.downloaded_object_sha256 == {}
    assert "S061:" in packet.suggested_registry_stub
    packet_text = Path(packet.packet_path).read_text()
    assert "API path" in packet_text
    assert "naId_is" in packet_text
