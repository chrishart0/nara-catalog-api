# NARA Tool Architecture and Testing Plan

Date: 2026-06-17

Scope: implementation architecture for the NARA Catalog API helper described in `BRD-agent-api-and-mcp.md`.

Reviewer input: code quality/project architecture subagent review completed 2026-06-17.

## 1. Architecture Decision

Promote the current single-file CLI into a small Python package with one shared research core. The CLI and MCP server should be adapters over the same service layer, not separate implementations.

The current `nara_api.py` should remain as a compatibility entrypoint so existing symlinks and commands continue to work.

Target wrapper:

```python
#!/usr/bin/env python3
from nara_catalog.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

## 2. Target Project Layout

```text
tools/nara-catalog-api/
  pyproject.toml
  README.md
  BRD-agent-api-and-mcp.md
  ARCHITECTURE-and-TESTING.md
  nara_api.py
  src/
    nara_catalog/
      __init__.py
      config.py
      client.py
      models.py
      parse.py
      compact.py
      downloads.py
      preservation.py
      service.py
      cli.py
      mcp_server.py
  tests/
    conftest.py
    fixtures/
      nara/
        search_variell_passport.json
        search_empty.json
        record_passport_with_digital_objects.json
        record_without_digital_objects.json
        record_schema_variant_source.json
        record_schema_variant_metadata_record.json
    unit/
      test_config.py
      test_client_params.py
      test_parse.py
      test_compact.py
      test_downloads.py
      test_preservation.py
      test_service.py
      test_cli.py
      test_mcp_contract.py
    integration/
      test_live_nara_api.py
```

## 3. Module Responsibilities

### `config.py`

Owns environment and secret-file resolution.

Responsibilities:

- read `.env` style files;
- resolve `NARA_API_KEY` precedence;
- return safe key-source labels;
- avoid printing or returning secret values except to callers that need the key for HTTP.

No HTTP, parsing, CLI formatting, or MCP logic belongs here.

### `client.py`

Owns direct NARA API communication.

Responsibilities:

- build API URLs and query parameters;
- set request headers;
- execute GET requests;
- enforce timeouts;
- return raw JSON plus request metadata;
- raise clear API/client errors.

The client should not compact records, print results, write archive files, or know about MCP.

### `models.py`

Owns stable internal contracts.

Use Pydantic if we want schema reuse for MCP and runtime validation. Otherwise use dataclasses with clear serialization helpers. Pydantic is preferred for this project because the MCP layer benefits from typed schemas.

Core models:

- `KeyStatus`;
- `RequestMetadata`;
- `SearchRequest`;
- `SearchResponse`;
- `RecordResponse`;
- `CompactRecord`;
- `DigitalObject`;
- `DownloadResult`;
- `SourcePacket`;
- `NegativeSearchDraft`;
- `HierarchyResult`;
- `RelatedRecordsResponse`.

Model rule: normalized models are finding aids and workflow objects. Raw NARA JSON must remain available for preservation and audit when a source is cited.

### `parse.py`

Owns schema-tolerant extraction from raw NARA JSON.

Responsibilities:

- absorb NARA response variants such as `_source`, `source`, `record`, and `metadata.record`;
- extract hits and totals from search responses;
- extract records from hits;
- extract NAID, title, dates, ancestors, digital objects, record group, and online availability;
- preserve unknown/raw structures for audit.

This is the only module that should know the messy shape of NARA JSON.

### `compact.py`

Owns display-neutral summaries.

Responsibilities:

- convert parsed records into `CompactRecord`;
- summarize digital objects;
- summarize ancestors;
- produce stable fields used by CLI and MCP.

Do not put terminal formatting here. Return structured summaries only.

### `downloads.py`

Owns digital-object download mechanics.

Responsibilities:

- flatten digital objects into downloadable items;
- select objects by all, range, or explicit indexes;
- create safe filenames;
- prevent accidental overwrite by default;
- download files;
- compute SHA-256;
- return `DownloadResult` records.

This module should not update source registries or research logs.

### `preservation.py`

Owns repository-aligned preservation outputs.

Responsibilities:

- create source-packet structures;
- write raw JSON and download manifests;
- generate source-registry stubs;
- generate source-manifest row suggestions;
- generate negative-search draft text/data;
- include NARA rights/use and attribution notes.

Initial behavior should emit stubs and files, not silently mutate `sources/source-registry.yaml` or `sources/source-manifest.md`. Direct registry edits can be added later behind an explicit flag.

### `service.py`

Owns agent-facing use cases.

Responsibilities:

- `check_key`;
- `search_records`;
- `count_records`;
- `get_record`;
- `list_digital_objects`;
- `download_digital_objects`;
- `browse_hierarchy`;
- `find_related_records`;
- `make_source_packet`;
- `make_negative_search_record`.

The service layer coordinates `client.py`, `parse.py`, `compact.py`, `downloads.py`, and `preservation.py`. It should not parse CLI args or register MCP tools.

### `cli.py`

Owns command-line interaction.

Responsibilities:

- parse arguments;
- call `service.py`;
- choose compact text vs JSON output;
- handle exit codes;
- print user-facing errors.

The CLI should preserve current commands and add new ones incrementally.

### `mcp_server.py`

Owns MCP registration only.

Responsibilities:

- register MCP tools, resources, and prompts;
- convert MCP input to service-layer request models;
- return structured content and short text summaries;
- keep API keys and local filesystem details out of responses.

The first MCP implementation should be stdio-only. Streamable HTTP can follow after the core and stdio MCP are stable.

## 4. Dependency Direction

Allowed direction:

```text
cli.py ┐
mcp_server.py ├──> service.py ───> client.py ───> requests/httpx
api users ┘        │
                   ├──> parse.py
                   ├──> compact.py
                   ├──> downloads.py
                   └──> preservation.py

models.py and config.py are shared support modules.
```

Rules:

- `client.py` must not import `cli.py`, `mcp_server.py`, or `service.py`.
- `parse.py` and `compact.py` must not perform HTTP or filesystem writes.
- `downloads.py` may write downloaded files but should not edit repository ledgers.
- `preservation.py` may write explicit packet artifacts, but registry/manifest mutation must be opt-in.
- `cli.py` and `mcp_server.py` must not duplicate NARA query logic.
- Package code should not depend on `Path.cwd()` except at adapter boundaries.

## 5. CLI Contract

Preserve current commands:

- `check-key`;
- `make-secret`;
- `search`;
- `record`;
- `summarize-file`.

Add commands incrementally:

- `images`;
- `count`;
- `browse`;
- `related`;
- `source-packet`;
- `negative-search`.

Output rules:

- compact human-readable output should be the terminal default for `search`;
- `--json` should emit stable machine-readable output to stdout;
- `--full` should mean raw NARA hit/record data where applicable;
- `--save` behavior must be explicit in help text: raw API JSON vs normalized tool output;
- downloads must require a destination and must not overwrite existing files unless `--force` is set.

Documentation fix:

- README currently documents `--endDate`; parser uses `--end-date`. Standardize on `--end-date` and explain that the API parameter sent to NARA is `endDate`.

## 6. Python API Contract

The Python API should be the most stable interface. CLI and MCP are adapters.

Example shape:

```python
from nara_catalog.service import NaraCatalogService
from nara_catalog.models import SearchRequest

service = NaraCatalogService.from_environment()
result = service.search_records(SearchRequest(
    query='"Arthur Davis Variell" passport',
    online=True,
    limit=10,
))
```

Every service response should carry:

- request metadata;
- fetched timestamp;
- safe key-source label where appropriate;
- raw response path or raw response object where appropriate;
- normalized records or workflow artifacts;
- warnings for schema gaps or skipped operations.

## 7. MCP Contract

Initial MCP tools:

- `nara_check_key`;
- `nara_search_records`;
- `nara_count_records`;
- `nara_get_record`;
- `nara_list_digital_objects`;
- `nara_download_digital_objects`;
- `nara_make_source_packet`;
- `nara_make_negative_search_record`.

Initial MCP resources:

- `nara://record/{naid}`;
- `nara://record/{naid}/compact`;
- `nara://record/{naid}/digital-objects`;
- `nara://search/{encoded_query}`.

Contract rules:

- use the official MCP Python SDK or a compatible high-level framework that tracks the current spec;
- verify current MCP spec and SDK behavior immediately before implementation;
- local stdio comes first;
- Streamable HTTP must wait until there is explicit need and a security pass;
- tool results should include structured content first and concise text summaries second;
- do not expose API key values, environment contents, or local secret paths;
- download/source-packet tools must require explicit destination or source ID parameters.

## 8. Pytest Strategy

Testing should be offline-first. Live NARA tests are compatibility checks, not the correctness suite.

### Unit Tests

Unit tests should run without network or credentials.

Required coverage:

- `.env` parsing and key precedence;
- secret safety in `KeyStatus` and error messages;
- request parameter construction for search, record, count, online-only, dates, and source includes;
- NARA response parsing for schema variants;
- compact summaries for records with and without digital objects;
- digital-object flattening and extracted-text flags;
- filename normalization;
- no-overwrite download behavior;
- SHA-256 calculation;
- source-packet stub generation;
- negative-search draft generation;
- CLI output mode selection and exit codes;
- MCP tool schema registration where possible without launching a live server.

### Integration Tests

Integration tests should be opt-in.

Rules:

- mark with `@pytest.mark.integration`;
- skip unless `RUN_NARA_INTEGRATION=1`;
- require `NARA_API_KEY`;
- use small `limit=1` requests;
- do not assert exact live hit counts;
- assert broad invariants only, such as response shape, JSON content type, and presence of expected top-level fields.

Commands:

```bash
pytest tests/unit
RUN_NARA_INTEGRATION=1 pytest tests/integration
```

### Fixture Strategy

Store representative raw NARA JSON under `tests/fixtures/nara/`.

Fixture categories:

- normal search with passport-related Variell results;
- empty search;
- full record with digital objects;
- record without digital objects;
- hit using `_source`;
- hit using `source`;
- hit using `metadata.record`;
- record with unusual or missing dates;
- record with malformed or absent digital object URLs.

Use pytest factories:

```python
@pytest.fixture
def fixture_json(load_fixture):
    return load_fixture("nara/search_variell_passport.json")

@pytest.fixture
def fake_client(fixture_json):
    return FakeNaraClient({"records/search": fixture_json})
```

Recommended shared fixtures:

- `api_key`: dummy key, never a real secret;
- `load_fixture`: JSON fixture loader;
- `fake_client`: deterministic client stub;
- `tmp_archive_root`: temporary repository-like archive tree;
- `tmp_secret_file`: local env file with dummy key;
- `capsys`: CLI stdout/stderr assertions;
- `monkeypatch`: environment and cwd isolation.

### HTTP Mocking

Use one mocking strategy consistently:

- If the client uses `requests`, use `requests-mock` or `responses`.
- If the client moves to `httpx`, use `respx`.

Do not mix HTTP libraries in the first implementation unless there is a concrete reason.

## 9. Quality Gates

Before adding MCP:

- current CLI commands still work;
- unit tests cover parser and compact output;
- raw JSON save behavior is unchanged or intentionally documented;
- `search` compact output is stable;
- `images --naid` is covered by fixture tests.

Before adding downloads:

- filename safety and no-overwrite tests pass;
- range/index selection is tested;
- failed download behavior is explicit;
- SHA-256 manifest output is tested.

Before adding source packets:

- source-packet output is tested against a temporary archive root;
- generated stubs are deterministic;
- no registry or manifest mutation occurs without an explicit flag.

Before adding MCP:

- service-layer contracts are stable;
- MCP tools are thin adapters only;
- MCP test verifies tool registration and representative tool calls with a fake service.

## 10. Anti-Patterns To Avoid

- Separate CLI and MCP implementations.
- Live API calls in ordinary unit tests.
- Silently overwriting downloaded evidence.
- Silently mutating registry or manifest files.
- Treating compact summaries as historical claims.
- Removing or replacing raw NARA JSON with normalized summaries.
- Letting API key paths or values leak through MCP responses.
- Unbounded downloads from search results.
- Coupling core package logic to the current working directory.
- Spreading NARA schema assumptions across many modules.

## 11. Recommended Build Sequence

1. Add `pyproject.toml`, `src/nara_catalog/`, and `tests/`.
2. Move config/key loading into `config.py`.
3. Move API calls into `client.py`.
4. Move NARA response extraction into `parse.py`.
5. Move compact summary logic into `compact.py`.
6. Define request/response models in `models.py`.
7. Add `service.py` and migrate `check-key`, `search`, and `record`.
8. Convert `nara_api.py` to a compatibility wrapper around `cli.py`.
9. Add fixture-backed unit tests.
10. Add compact default search output and `--json`.
11. Add `images`.
12. Add count-only search.
13. Add downloads and preservation workflows.
14. Add stdio MCP server.

This order keeps behavior stable while gradually improving structure.
