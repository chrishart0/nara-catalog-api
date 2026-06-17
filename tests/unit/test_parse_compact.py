from __future__ import annotations

from nara_catalog import compact, parse
from tests.conftest import load_fixture


def test_search_hits_total_and_schema_variants() -> None:
    data = load_fixture("search_variell_passport.json")

    hits = parse.search_hits(data)

    assert parse.total_hits(data) == 2
    assert parse.naid(parse.record_from_hit(hits[0])) == "235845496"
    assert parse.naid(parse.record_from_hit(hits[1])) == "143620632"


def test_compact_record_summarizes_key_fields() -> None:
    data = load_fixture("search_variell_passport.json")

    record = compact.compact_record_from_hit(parse.search_hits(data)[0])

    assert record.na_id == "235845496"
    assert record.title == "Volume 994: April 22 to 30, 1903"
    assert record.record_group_number == "59"
    assert record.digital_object_count == 2
    assert record.digital_objects[0].has_extracted_text is True
    assert record.catalog_url == "https://catalog.archives.gov/id/235845496"
    assert record.source_platform == "Fold3"
