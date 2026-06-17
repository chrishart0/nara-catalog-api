from __future__ import annotations

from pathlib import Path

import pytest

from nara_catalog.downloads import destination_name, download_objects, safe_filename, select_objects
from nara_catalog.models import DigitalObject


def objects() -> list[DigitalObject]:
    return [
        DigitalObject(1, "Image", "Page 1", "page 1.jpg", "https://example.test/page1.jpg"),
        DigitalObject(2, "Image", "Page 2", "page2.jpg", "https://example.test/page2.jpg"),
    ]


def test_safe_filename_and_destination_name() -> None:
    assert safe_filename("bad / file:name.jpg") == "bad-file-name.jpg"
    assert destination_name("123", objects()[0]).startswith("nara-123-img0001-page-1")


def test_select_objects_accepts_ranges_and_indexes() -> None:
    selected = select_objects(objects(), "1-1,2")

    assert [obj.index for obj in selected] == [1, 2]


def test_select_objects_rejects_invalid_ranges() -> None:
    with pytest.raises(ValueError):
        select_objects(objects(), "0")
    with pytest.raises(ValueError):
        select_objects(objects(), "2-1")


def test_download_objects_skips_existing_files_without_overwrite(tmp_path: Path) -> None:
    existing = tmp_path / destination_name("123", objects()[0])
    existing.write_bytes(b"already here")

    manifest = download_objects(na_id="123", objects=objects()[:1], destination=tmp_path, force=False)

    assert manifest.results[0].status == "skipped_exists"
    assert manifest.results[0].sha256 is not None
    assert (tmp_path / "nara-123-download-manifest.json").exists()


class FakeResponse:
    def __init__(self, chunks: list[bytes], *, fail: bool = False) -> None:
        self.chunks = chunks
        self.fail = fail

    def raise_for_status(self) -> None:
        if self.fail:
            raise RuntimeError("boom")

    def iter_content(self, chunk_size: int):
        yield from self.chunks


def test_download_objects_streams_success_and_writes_manifest(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("nara_catalog.downloads.requests.get", lambda *args, **kwargs: FakeResponse([b"abc", b"123"]))

    manifest = download_objects(na_id="123", objects=objects()[:1], destination=tmp_path)

    result = manifest.results[0]
    assert result.status == "downloaded"
    assert result.bytes_written == 6
    assert result.sha256
    assert Path(result.local_path).read_bytes() == b"abc123"


def test_download_objects_cleans_temp_file_on_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("nara_catalog.downloads.requests.get", lambda *args, **kwargs: FakeResponse([b"abc"], fail=True))

    manifest = download_objects(na_id="123", objects=objects()[:1], destination=tmp_path)

    assert manifest.results[0].status == "failed"
    assert not list(tmp_path.glob(".*.tmp"))
