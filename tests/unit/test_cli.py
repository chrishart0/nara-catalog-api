from __future__ import annotations

import json

from nara_catalog import cli
from nara_catalog.models import DownloadManifest, DownloadResult
from nara_catalog.service import NaraCatalogService
from tests.conftest import load_fixture


def test_search_cli_defaults_to_compact_output(monkeypatch, capsys) -> None:
    class FakeService:
        def search_records(self, request, *, timeout=None):
            service = NaraCatalogService(FakeClient(load_fixture("search_variell_passport.json")), key_source="test")
            return service.search_records(request)

    monkeypatch.setattr(cli, "service_from_args", lambda args: FakeService())

    status = cli.main(["search", "--query", "Variell", "--online"])

    out = capsys.readouterr().out
    assert status == 0
    assert "Total: 2 results" in out
    assert "NAID 235845496" in out


def test_search_cli_json_output(monkeypatch, capsys) -> None:
    class FakeService:
        def search_records(self, request, *, timeout=None):
            service = NaraCatalogService(FakeClient(load_fixture("search_empty.json")), key_source="test")
            return service.search_records(request)

    monkeypatch.setattr(cli, "service_from_args", lambda args: FakeService())

    status = cli.main(["search", "--query", "Nope", "--json"])

    out = capsys.readouterr().out
    assert status == 0
    assert '"query": "Nope"' in out
    assert '"total": 0' in out


def test_search_download_dir_prints_totals(monkeypatch, capsys, tmp_path) -> None:
    class FakeService:
        def search_records(self, request, *, timeout=None):
            service = NaraCatalogService(FakeClient(load_fixture("search_variell_passport.json")), key_source="test")
            return service.search_records(request)

        def download_digital_objects(self, na_id, destination, *, selection=None, force=False, timeout=60, max_bytes=None):
            return DownloadManifest(
                na_id=na_id,
                destination=str(destination),
                results=[DownloadResult(1, "https://example.test/1.jpg", str(tmp_path / "1.jpg"), "abc", "downloaded", 3)],
            )

    monkeypatch.setattr(cli, "service_from_args", lambda args: FakeService())

    status = cli.main(["search", "--query", "Variell", "--download-dir", str(tmp_path), "--limit", "1"])

    out = capsys.readouterr().out
    assert status == 0
    assert "Downloads: records=2 downloaded=2 skipped=0 failed=0" in out


def test_search_download_quiet_suppresses_search_listing(monkeypatch, capsys, tmp_path) -> None:
    class FakeService:
        def search_records(self, request, *, timeout=None):
            service = NaraCatalogService(FakeClient(load_fixture("search_variell_passport.json")), key_source="test")
            return service.search_records(request)

        def download_digital_objects(self, na_id, destination, *, selection=None, force=False, timeout=60, max_bytes=None):
            return DownloadManifest(
                na_id=na_id,
                destination=str(destination),
                results=[DownloadResult(1, "https://example.test/1.jpg", str(tmp_path / "1.jpg"), "abc", "downloaded", 3)],
            )

    monkeypatch.setattr(cli, "service_from_args", lambda args: FakeService())

    status = cli.main(["search", "--query", "Variell", "--download-dir", str(tmp_path), "--limit", "1", "--quiet"])

    out = capsys.readouterr().out
    assert status == 0
    assert "NAID 235845496" not in out
    assert "Downloads: records=2 downloaded=2 skipped=0 failed=0" in out


def test_record_cli_defaults_to_compact_output(monkeypatch, capsys) -> None:
    class FakeService:
        def get_record(self, naid, *, include_extracted_text=False, timeout=None):
            service = NaraCatalogService(FakeClient(load_fixture("record_passport_with_digital_objects.json")), key_source="test")
            return service.get_record(naid, include_extracted_text=include_extracted_text, timeout=timeout)

    monkeypatch.setattr(cli, "service_from_args", lambda args: FakeService())

    status = cli.main(["record", "--naid", "235845496"])

    out = capsys.readouterr().out
    assert status == 0
    assert "NAID: 235845496 found=True" in out
    assert "Volume 994" in out
    assert not out.lstrip().startswith("{")


def test_search_count_text_includes_timestamp(monkeypatch, capsys) -> None:
    class FakeService:
        def count_records(self, request, *, timeout=None):
            service = NaraCatalogService(FakeClient(load_fixture("search_empty.json")), key_source="test")
            return service.count_records(request)

    monkeypatch.setattr(cli, "service_from_args", lambda args: FakeService())

    status = cli.main(["search", "--query", "Nope", "--count"])

    out = capsys.readouterr().out
    assert status == 0
    assert "Total: 0" in out
    assert "Fetched epoch:" in out


def test_search_count_can_emit_negative_search_draft(monkeypatch, capsys) -> None:
    class FakeService:
        def count_records(self, request, *, timeout=None):
            service = NaraCatalogService(FakeClient(load_fixture("search_empty.json")), key_source="test")
            return service.count_records(request)

        def make_negative_search_record(self, request, *, threshold=0, timeout=None):
            service = NaraCatalogService(FakeClient(load_fixture("search_empty.json")), key_source="test")
            return service.make_negative_search_record(request, threshold=threshold)

    monkeypatch.setattr(cli, "service_from_args", lambda args: FakeService())

    status = cli.main(["search", "--query", "Nope", "--count", "--negative-search-draft"])

    out = capsys.readouterr().out
    assert status == 0
    assert "NARA Negative Search Draft" in out


def test_search_download_refuses_too_many_objects_without_confirmation(monkeypatch, capsys, tmp_path) -> None:
    class FakeService:
        def search_records(self, request, *, timeout=None):
            service = NaraCatalogService(FakeClient(load_fixture("search_variell_passport.json")), key_source="test")
            return service.search_records(request)

    monkeypatch.setattr(cli, "service_from_args", lambda args: FakeService())

    status = cli.main([
        "search",
        "--query",
        "Variell",
        "--download-dir",
        str(tmp_path),
        "--download-object-limit",
        "1",
    ])

    err = capsys.readouterr().err
    assert status == 2
    assert "Refusing to download up to" in err


def test_summarize_file_handles_saved_source_packet(tmp_path, capsys) -> None:
    path = tmp_path / "packet.json"
    path.write_text(json.dumps({
        "source_id": "S001",
        "na_id": "123",
        "packet_path": "/tmp/archive/nara/S001/packet.md",
        "raw_json_path": "/tmp/archive/nara/S001/raw.json",
        "downloaded_object_paths": ["/tmp/1.jpg"],
    }))

    status = cli.main(["summarize-file", str(path)])

    out = capsys.readouterr().out
    assert status == 0
    assert "source_id: S001 naid: 123" in out
    assert "downloaded_objects: 1" in out


def test_summarize_file_handles_saved_images(tmp_path, capsys) -> None:
    path = tmp_path / "images.json"
    path.write_text(json.dumps([
        {"index": 1, "object_type": "Image", "file_name": "page1.jpg", "object_url": "https://example.test/page1.jpg", "downloaded": True}
    ]))

    status = cli.main(["summarize-file", str(path)])

    out = capsys.readouterr().out
    assert status == 0
    assert "digitalObjects: 1" in out
    assert "downloaded" in out


def test_summarize_file_handles_saved_browse_related_and_negative_search(tmp_path, capsys) -> None:
    browse = tmp_path / "browse.json"
    browse.write_text(json.dumps({"na_id": "123", "ancestors": [{"naId": "1"}], "parent": {"naId": "1"}, "likely_series": None}))
    related = tmp_path / "related.json"
    related.write_text(json.dumps({"na_id": "123", "mode": "same-parent", "basis": {"ancestor_naid": "1"}, "search": {"returned": 2, "total": 2}}))
    negative = tmp_path / "negative.json"
    negative.write_text(json.dumps({"query": "Nope", "total_hits": 0, "confidence": "searched-no-record", "markdown": "draft"}))

    assert cli.main(["summarize-file", str(browse)]) == 0
    assert "ancestors: 1" in capsys.readouterr().out
    assert cli.main(["summarize-file", str(related)]) == 0
    assert "related_returned: 2" in capsys.readouterr().out
    assert cli.main(["summarize-file", str(negative)]) == 0
    assert "total_hits: 0" in capsys.readouterr().out


class FakeClient:
    def __init__(self, response):
        self.response = response

    def search(self, params, *, timeout=None):
        return self.response
