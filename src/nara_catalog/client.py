from __future__ import annotations

from typing import Any

import requests

BASE_URL = "https://catalog.archives.gov/api/v2"
USER_AGENT = "Hermes NARA Catalog research helper (read-only historical research)"


class NaraApiError(RuntimeError):
    pass


class NaraCatalogClient:
    def __init__(self, api_key: str, *, base_url: str = BASE_URL, timeout: int = 60) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_json(self, path: str, params: dict[str, Any] | None = None, *, timeout: int | None = None) -> dict[str, Any]:
        url = self.base_url + "/" + path.lstrip("/")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self.api_key,
            "User-Agent": USER_AGENT,
        }
        response = requests.get(url, headers=headers, params=params or {}, timeout=timeout or self.timeout)
        ctype = response.headers.get("content-type", "")
        if not response.ok:
            raise NaraApiError(f"HTTP {response.status_code} from {response.url}: {response.text[:500]}")
        if "json" not in ctype.lower():
            raise NaraApiError(
                f"Expected JSON but got content-type {ctype!r} from {response.url}. "
                "If this is the Catalog single-page app HTML, check that the API key is valid."
            )
        return response.json()

    def search(self, params: dict[str, Any], *, timeout: int | None = None) -> dict[str, Any]:
        return self.get_json("/records/search", params=params, timeout=timeout)
