from __future__ import annotations

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

        def download_digital_objects(self, na_id, destination, *, selection=None, force=False, timeout=60):
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


class FakeClient:
    def __init__(self, response):
        self.response = response

    def search(self, params, *, timeout=None):
        return self.response
