from __future__ import annotations

from nara_catalog.models import SearchRequest
from nara_catalog.downloads import destination_name
from nara_catalog.models import DigitalObject
from nara_catalog.service import NaraCatalogService, search_params
from tests.conftest import load_fixture


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def search(self, params, *, timeout=None):
        self.calls.append(params)
        return self.response


class SequenceClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def search(self, params, *, timeout=None):
        self.calls.append(params)
        return self.responses.pop(0)


def test_search_params_map_cli_names_to_nara_api_names() -> None:
    params = search_params(SearchRequest(
        query="Variell",
        online=True,
        start_date="1903",
        end_date="1904",
        ancestor_naid="200",
    ))

    assert params["availableOnline"] == "true"
    assert params["startDate"] == "1903"
    assert params["endDate"] == "1904"
    assert params["ancestorNaId"] == "200"


def test_service_search_returns_compact_records() -> None:
    client = FakeClient(load_fixture("search_variell_passport.json"))
    service = NaraCatalogService(client, key_source="test")

    result = service.search_records(SearchRequest(query="Variell", online=True))

    assert result.total == 2
    assert result.returned == 2
    assert result.records[0].na_id == "235845496"
    assert client.calls[0]["availableOnline"] == "true"


def test_service_list_digital_objects_fetches_full_record() -> None:
    client = FakeClient(load_fixture("record_passport_with_digital_objects.json"))
    service = NaraCatalogService(client, key_source="test")

    objects = service.list_digital_objects("235845496")

    assert [obj.index for obj in objects] == [1, 2]
    assert objects[0].file_name == "page1.jpg"
    assert client.calls[0]["naId_is"] == "235845496"


def test_service_list_digital_objects_marks_known_local_status(tmp_path) -> None:
    client = FakeClient(load_fixture("record_passport_with_digital_objects.json"))
    service = NaraCatalogService(client, key_source="test")
    expected = tmp_path / destination_name("235845496", DigitalObject(1, "Image", "Page 1", "page1.jpg", "https://catalog.archives.gov/fold3/page1.jpg"))
    expected.write_bytes(b"existing")

    objects = service.list_digital_objects("235845496", local_dir=tmp_path)

    assert objects[0].downloaded is True
    assert objects[0].local_path == str(expected)


def test_search_request_validates_limits() -> None:
    import pytest

    with pytest.raises(ValueError):
        SearchRequest(query="Variell", limit=0)
    with pytest.raises(ValueError):
        SearchRequest(query="Variell", page=0)


def test_service_summarize_record_is_agent_api() -> None:
    client = FakeClient(load_fixture("record_passport_with_digital_objects.json"))
    service = NaraCatalogService(client, key_source="test")
    record = service.get_record("235845496").record

    summary = service.summarize_record(record)

    assert summary.na_id == "235845496"
    assert summary.digital_object_count == 2


def test_browse_hierarchy_finds_parent_and_series() -> None:
    client = FakeClient(load_fixture("record_passport_with_digital_objects.json"))
    service = NaraCatalogService(client, key_source="test")

    result = service.browse_hierarchy("235845496")

    assert result.parent["naId"] == "200"
    assert result.likely_series["title"] == "Passport Applications"


def test_browse_hierarchy_can_include_sibling_search_results() -> None:
    client = SequenceClient([
        load_fixture("record_passport_with_digital_objects.json"),
        load_fixture("search_variell_passport.json"),
    ])
    service = NaraCatalogService(client, key_source="test")

    result = service.browse_hierarchy("235845496", include_siblings=True, sibling_limit=2)

    assert result.siblings is not None
    assert result.siblings.total == 2
    assert client.calls[1]["ancestorNaId"] == "200"


def test_related_rejects_unknown_mode_without_extra_search() -> None:
    import pytest

    client = FakeClient(load_fixture("record_passport_with_digital_objects.json"))
    service = NaraCatalogService(client, key_source="test")

    with pytest.raises(ValueError):
        service.find_related_records("235845496", mode="unknown")
