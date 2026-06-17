from __future__ import annotations

import os

import pytest

from nara_catalog.models import SearchRequest
from nara_catalog.service import NaraCatalogService


pytestmark = pytest.mark.integration


def test_live_search_shape() -> None:
    if os.environ.get("RUN_NARA_INTEGRATION") != "1":
        pytest.skip("set RUN_NARA_INTEGRATION=1 to run live NARA API tests")

    service = NaraCatalogService.from_environment(timeout=30)
    result = service.search_records(SearchRequest(query="constitution", limit=1, abbreviated=True), timeout=30)

    assert result.request.endpoint == "/records/search"
    assert result.returned <= 1
    assert result.total is None or result.total >= 0
