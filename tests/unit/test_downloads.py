from __future__ import annotations

from pathlib import Path

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


def test_download_objects_skips_existing_files_without_overwrite(tmp_path: Path) -> None:
    existing = tmp_path / destination_name("123", objects()[0])
    existing.write_bytes(b"already here")

    manifest = download_objects(na_id="123", objects=objects()[:1], destination=tmp_path, force=False)

    assert manifest.results[0].status == "skipped_exists"
    assert manifest.results[0].sha256 is not None
    assert (tmp_path / "nara-123-download-manifest.json").exists()
