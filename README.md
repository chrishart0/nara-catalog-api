# NARA Catalog API Helper

Agent-first, read-only helper for the National Archives Catalog API v2. The CLI,
Python API, and MCP server share the same package code under `src/nara_catalog/`.

## Setup

Get a NARA Catalog API key by emailing `Catalog_API@nara.gov`, then use one of:

```bash
export NARA_API_KEY=your-key
# or, from the repo root you run commands in:
printf 'NARA_API_KEY=your-key\n' > .env
# or:
python nara_api.py --secret-file /path/to/nara.env check-key --live
```

Credential lookup order is environment, `--secret-file`, current working
directory `.env`, then `~/.hermes/secrets/nara.env`. The tool never prints the
key.

## Quick Start

```bash
# Readable search results
python nara_api.py search --query '"Arthur Davis Variell"' --online

# Count-only scoping, optionally with a negative-search draft
python nara_api.py search --query 'Variell' --online --count
python nara_api.py search --query '"Arthur D. Variell" passport' --online --count --negative-search-draft

# Fetch and preserve a record
python nara_api.py record --naid 235845496 --save /tmp/nara-235845496.json
python nara_api.py source-packet --naid 235845496 --source-id S061 --archive-root ../..

# List or download digital objects
python nara_api.py images --naid 235845496
python nara_api.py images --naid 235845496 --download-dir /tmp/nara-235845496 --range 1-5

# Browse related context
python nara_api.py browse --naid 235845496 --siblings
python nara_api.py related --naid 235845496 --mode same-series
```

Use `--json` for normalized JSON and `--full` for raw NARA API JSON. Run
`python nara_api.py COMMAND --help` for command-specific options.

## Workflow Notes

- `search` defaults to compact terminal output.
- `--start-date` and `--end-date` map to NARA `startDate` and `endDate`.
- Date filters are catalog constraints, not proof of event dates.
- Downloads never overwrite unless `--force` is passed.
- Downloads stream to temporary files, compute SHA-256, and write
  `nara-{naid}-download-manifest.json`.
- Search-result downloads enforce `--download-record-limit` and
  `--download-object-limit`; use `--range` or `--yes` for explicit bulk intent.
- Source IDs must match `S###`, `R###`, `C###`, or `N###` with an optional
  alphanumeric, underscore, or dash suffix.

NARA documents a default Catalog API limit of 10,000 queries per month per API
key. Keep searches small and prefer `--count` for scoping.

## Python API

```python
from pathlib import Path
from nara_catalog.models import SearchRequest
from nara_catalog.service import NaraCatalogService

service = NaraCatalogService.from_environment(project_dir=Path.cwd())
result = service.search_records(SearchRequest(
    query='"Arthur Davis Variell" passport',
    online=True,
    limit=10,
))
```

## MCP Server

```bash
pip install -e '.[mcp]'
nara-mcp
```

The MCP server is local stdio-first and targets the MCP `2025-11-25`
specification with the stable `mcp` Python SDK v1 line. Write tools are disabled
unless `NARA_MCP_WRITE_ROOT` is set; paths outside that root are rejected and MCP
responses scrub local filesystem details.

## Development

```bash
pip install -e '.[test]'
pytest
RUN_NARA_INTEGRATION=1 pytest tests/integration
```

Unit tests are offline. Live NARA tests are opt-in and assert broad API shape
only.
