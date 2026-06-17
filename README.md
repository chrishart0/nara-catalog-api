# NARA Catalog API Helper

Agent-first, read-only helper for the National Archives Catalog API v2.

The command-line tool is intentionally thin. Shared package code under `src/nara_catalog/`
does the API calls, parsing, compaction, downloads, preservation drafts, and MCP
tool wiring.

## Setup

1. Get an API key by emailing `Catalog_API@nara.gov` for a read-only key.
2. Save it as `NARA_API_KEY=your-key-here` in the project `.env` file, or pass
   `--secret-file /path/to/env`.

The tool never prints the key.

## Common Commands

From this tool directory:

```bash
# Verify configuration
python nara_api.py check-key --live

# Search. Compact human-readable output is the default.
python nara_api.py search --query '"Arthur Davis Variell"' --limit 10 --online

# Machine-readable normalized JSON
python nara_api.py search --query 'Variell AND passport' --online --json

# Raw NARA API JSON
python nara_api.py search --query 'Variell AND passport' --online --full

# Count-only scoping for negative-search work
python nara_api.py search --query 'Variell' --online --count

# Fetch a specific record by NAID
python nara_api.py record --naid 235845496 --save /tmp/nara-235845496.json

# List digital object URLs in a flat format
python nara_api.py images --naid 235845496

# Download selected digital objects without overwriting existing files
python nara_api.py images --naid 235845496 --download-dir /tmp/nara-235845496 --range 1-5

# Browse hierarchy context
python nara_api.py browse --naid 235845496

# Related records
python nara_api.py related --naid 235845496 --mode same-series --limit 10

# Repository-style source packet draft
python nara_api.py source-packet --naid 235845496 --source-id S061 --archive-root ../..

# Negative-search draft
python nara_api.py negative-search --query '"Arthur D. Variell" passport' --online
```

## Credential Resolution

The helper looks for `NARA_API_KEY` in this order:

1. `NARA_API_KEY` environment variable
2. `--secret-file /path/to/file`, if passed
3. `.env` in the current working directory
4. `~/.hermes/secrets/nara.env`

## Output Modes

`search` prints compact text by default:

```text
Total: 2 results
Returned: 2
[1] NAID 235845496 - Volume 994: April 22 to 30, 1903
    fileUnit | RG-59 | 816 digital objects | Fold3
    https://catalog.archives.gov/id/235845496
```

Use `--json` for normalized structured output. Use `--full` for raw NARA API
JSON. `--save PATH` writes JSON output to disk.

## Date Filters

The CLI uses Python-friendly option names:

- `--start-date` maps to NARA API parameter `startDate`
- `--end-date` maps to NARA API parameter `endDate`

NARA records often describe archival date ranges rather than event dates. Treat
date filters as catalog search constraints, not proof that an event occurred
inside the queried range.

Examples:

```bash
python nara_api.py search --query 'passport Variell' --start-date 1903 --end-date 1903
python nara_api.py search --query 'Variell' --start-date 1900 --end-date 1910
python nara_api.py search --query '"Arthur Davis Variell"' --start-date 1903-04-01 --end-date 1903-04-30
```

## Downloads

Downloads:

- require an explicit destination;
- do not overwrite existing files unless `--force` is passed;
- compute SHA-256 for downloaded or existing skipped files;
- write `nara-{naid}-download-manifest.json`.

When downloading from search results, use `--download-record-limit` and `--yes`
to make bulk intent explicit.

## Rate Limit Awareness

NARA documents a default Catalog API limit of 10,000 queries per month per API
key. The limit resets on the first day of each month; higher limits require
contacting `Catalog_API@nara.gov` with a use case and justification. Keep search
limits small, prefer `--count` for scoping, and avoid unbounded search-result
downloads.

## Python API

```python
from nara_catalog.models import SearchRequest
from nara_catalog.service import NaraCatalogService

service = NaraCatalogService.from_environment()
result = service.search_records(SearchRequest(
    query='"Arthur Davis Variell" passport',
    online=True,
    limit=10,
))
```

## MCP Server

The MCP server is local stdio-first and uses the official Python SDK through the
optional `mcp` extra:

```bash
pip install -e '.[mcp]'
nara-mcp
```

The implementation targets the MCP `2025-11-25` specification and the stable
`mcp` Python SDK v1 line. It exposes read-only tools for search, count, record
fetch, image listing/download, hierarchy, related records, source-packet drafts,
and negative-search drafts. MCP outputs scrub key-source metadata so API key
locations are not returned to clients.

## Development

```bash
pip install -e '.[test]'
pytest
RUN_NARA_INTEGRATION=1 pytest tests/integration
```

Unit tests are offline and use fixtures. Integration tests are opt-in, require a
configured `NARA_API_KEY`, and assert only broad live API invariants.
