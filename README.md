# NARA Catalog Agent CLI

Agent-first command-line tool for the National Archives Catalog API v2, with a
shared Python API and optional MCP server.

The CLI is designed for research agents and humans who need scan-friendly
search results, structured JSON, direct digital-object workflows, and
preservation-safe source packets without hand-inspecting nested API responses.

This project is read-only against NARA and is not affiliated with the National
Archives and Records Administration.

## Why Agent-First?

- Compact terminal output by default; JSON when agents need structured data.
- One shared service layer for CLI, Python API, and MCP tools.
- Explicit safeguards for downloads, filesystem writes, and API-key handling.
- Source-packet and negative-search helpers for auditable research workflows.
- Offline-first tests so behavior is not coupled to live NARA responses.

## Install

```bash
git clone <repo-url>
cd nara-catalog-api
python -m pip install -e '.[test]'
```

For the optional MCP server:

```bash
python -m pip install -e '.[mcp]'
```

## Configure

Get a NARA Catalog API key by emailing `Catalog_API@nara.gov`, then use one of:

```bash
export NARA_API_KEY=your-key
# or, from the directory where you run commands:
printf 'NARA_API_KEY=your-key\n' > .env
# or:
nara-api --secret-file /path/to/nara.env check-key --live
```

Credential lookup order is environment, `--secret-file`, current working
directory `.env`, then `~/.hermes/secrets/nara.env`. The tool never prints the
key.

## Quick Start

```bash
# Readable compact search results
nara-api search --query '"SEARCH TERMS"' --online

# Normalized JSON for agents
nara-api search --query '"SEARCH TERMS"' --online --json

# Count-only scoping, optionally with a negative-search draft
nara-api search --query '"SEARCH TERMS"' --online --count
nara-api search --query '"SEARCH TERMS"' --online --count --negative-search-draft

# Fetch a record and create a preservation draft
nara-api record --naid NAID --save /tmp/nara-NAID.json
nara-api source-packet --naid NAID --source-id S001 --archive-root /path/to/archive-root

# List or download digital objects
nara-api images --naid NAID
nara-api images --naid NAID --download-dir /tmp/nara-NAID --range 1-5

# Browse hierarchy and related records
nara-api browse --naid NAID --siblings
nara-api related --naid NAID --mode same-series
```

Use `--json` for normalized JSON and `--full` for raw NARA API JSON. Run
`nara-api COMMAND --help` for command-specific options.

## Output And Safety Notes

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
    query='"SEARCH TERMS"',
    online=True,
    limit=10,
))
```

## MCP Server

```bash
nara-mcp
```

The MCP server is local stdio-first and targets the MCP `2025-11-25`
specification with the stable `mcp` Python SDK v1 line. Write tools are disabled
unless `NARA_MCP_WRITE_ROOT` is set; paths outside that root are rejected and MCP
responses scrub local filesystem details.

## Development

```bash
python -m pip install -e '.[test]'
pytest
RUN_NARA_INTEGRATION=1 pytest tests/integration
```

Unit tests are offline. Live NARA tests are opt-in and assert broad API shape
only.

## License

MIT. See [LICENSE](LICENSE).
