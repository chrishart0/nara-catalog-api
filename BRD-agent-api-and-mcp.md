# Business Requirements Document: NARA Agent API and MCP Server

Date: 2026-06-17

Owner: Arthur Davis Variell historical research project

Tool path: `tools/nara-catalog-api/`

Current implementation: `nara_api.py`

## 1. Executive Summary

The current NARA Catalog helper is a useful read-only Python CLI for checking API access, searching records, fetching records by NAID, saving JSON, and summarizing saved JSON. Recent research use shows that the basic search-inspect-record-save loop works, but the interface is too raw for repeated agent-driven historical research.

The next version should become an agent-first NARA research API with a thin CLI and a Model Context Protocol (MCP) server built on top of the same core logic. The objective is to make NARA research faster, more auditable, and easier for agents to use without losing the repository's source-preservation discipline.

The highest-value change is not a larger API surface. It is a better research workflow: compact human-readable search results, direct digital-object listing and download, source-packet creation, negative-search support, and MCP tools/resources that expose those capabilities safely.

## 2. Background

This repository is a source-grounded historical research project on Arthur Davis Variell. NARA Catalog records are especially relevant for passport applications, State Department records, travel evidence, honors/title leads, related individuals, and archival hierarchy discovery.

The existing helper:

- reads `NARA_API_KEY` from environment, project `.env`, a secret file, or a global fallback;
- provides `check-key`, `search`, `record`, `summarize-file`, and `make-secret`;
- supports filters such as online-only records, extracted text, type of material, object type, record group, reference unit, ancestor NAID, and dates;
- can save raw JSON for preservation.

The helper is effective as a low-level script, but agents using it still have to manually format search results, inspect nested JSON for image URLs, and compose preservation workflows themselves.

## 3. Goals

1. Provide an agent-first Python API with typed request and response models.
2. Preserve the current CLI behavior while improving default usability.
3. Add direct digital-object workflows for listing, selecting, and downloading NARA images/files.
4. Add source-preservation helpers aligned with this repository's archival workflow.
5. Add an MCP server following the latest MCP specification available during planning, version `2025-11-25`.
6. Keep the implementation read-only against NARA unless a future explicit requirement authorizes contribution-writing.
7. Prevent accidental exposure of API keys or repository-private research files.
8. Make negative searches and source packets easier to log.

## 4. Non-Goals

- Do not implement NARA write APIs for tags, comments, transcriptions, or account actions.
- Do not scrape or mass-download all NARA data.
- Do not bypass NARA rate limits or access controls.
- Do not infer historical claims from NARA metadata without source-ledger review.
- Do not replace `sources/source-registry.yaml`, `sources/source-manifest.md`, or the project evidence workflow.
- Do not expose a remote MCP HTTP server until local stdio MCP is stable and reviewed.

## 5. Users and Use Cases

### 5.1 Historical Research Agent

Needs to search NARA, inspect candidate records, retrieve full records, list and download digital objects, and preserve evidence with enough metadata for later citation.

Primary success criterion: an agent can move from query to preserved source packet with minimal manual JSON inspection.

### 5.2 Human Researcher

Needs fast terminal commands that print readable search results, support copy/paste source URLs, and save raw data when needed.

Primary success criterion: common commands are readable by default and raw JSON is available intentionally through `--json`, `--full`, or `--save`.

### 5.3 Evidence Manager

Needs local files, hashes, custody notes, source IDs, and negative-search records.

Primary success criterion: NARA downloads produce manifest-ready metadata and do not silently overwrite original evidence.

### 5.4 MCP Client / AI Host

Needs discoverable tools and resources with clear schemas.

Primary success criterion: the MCP server exposes safe, read-only NARA research actions with structured results.

## 6. Current Access Patterns Observed

The following patterns were reported by an agent using the current script:

1. Search, inspect, record, summarize.
   Search with a query, inspect results, fetch a full record by NAID, save JSON, and summarize it later.

2. Search with `--online`.
   Online records are usually preferred because non-online records are less actionable from the local environment.

3. Search piped to `python3` for formatting.
   Raw JSON is too verbose for quick scanning.

4. `summarize-file` on saved JSON.
   Useful for quick re-reading after preservation.

5. `check-key --live`.
   Useful sanity check before starting a NARA research session.

## 7. Pain Points

### 7.1 Raw JSON Is Too Verbose

Search output currently exposes nested API response structures. Agents repeatedly need a compact display:

```text
Total: 3 results
[1] NAID 235845496 - Volume 994: April 22 to 30, 1903
    fileUnit | RG-59 Passport Applications | 816 digital objects | Fold3
    https://catalog.archives.gov/id/235845496
```

### 7.2 Digital Object URLs Are Buried

To find image files, users currently fetch a record, save JSON, open it, and inspect `digitalObjects` arrays for `objectUrl` fields.

### 7.3 Record Hierarchy Is Hard to Browse

Records contain ancestors, but the CLI does not help researchers walk from file unit to series, record group, parent, siblings, or related file units.

### 7.4 Downloading Requires Manual Glue

Search can identify records with digital objects, but cannot download those objects directly with sensible filenames and custody metadata.

### 7.5 Date Filtering Is Opaque

The CLI exposes `--start-date` and `--end-date`, while the API uses parameters such as `startDate` and `endDate`. Researchers need clearer help text and examples for NARA date behavior.

### 7.6 Hit Counts Are Not First-Class

Negative-search logging often needs only the hit count, not a full result page.

### 7.7 Related Records Require Guesswork

Researchers want to find records in the same series, same record group, same parent hierarchy, or otherwise related to a known NAID.

## 8. Business Requirements

### BR-001: Agent-First Core API

The project shall provide a Python package that exposes stable functions for NARA research workflows independent of CLI or MCP presentation.

Minimum functions:

- `check_key(live: bool)`;
- `search_records(request)`;
- `count_records(request)`;
- `get_record(naid, include_extracted_text)`;
- `summarize_record(record)`;
- `list_digital_objects(naid)`;
- `download_digital_objects(naid, destination, selection)`;
- `browse_hierarchy(naid)`;
- `find_related_records(naid, mode)`;
- `make_source_packet(naid, source_id, archive_root)`;
- `make_negative_search_record(request)`.

### BR-002: Shared Logic Across CLI and MCP

The CLI and MCP server shall call the same agent API. No NARA search, record parsing, download, or preservation logic should exist only in the CLI or only in the MCP layer.

### BR-003: Compact Search Output

The CLI shall support compact human-readable search output. Compact output should become the default for terminal stdout unless raw JSON is explicitly requested.

Acceptance criteria:

- Search prints total count, returned count, NAID, title, level, record group or collection context when available, digital object count, likely source platform when available, and catalog URL.
- `--save` still writes full JSON or a documented structured result file.
- `--json` or `--full` can emit machine-readable output to stdout.

### BR-004: Digital Object Listing

The CLI and MCP server shall expose a way to list digital objects for a NAID in a flat, greppable, structured form.

Fields should include:

- index;
- object type;
- title or caption;
- file name where available;
- object URL;
- thumbnail URL;
- extracted-text availability;
- local download status when known.

### BR-005: Digital Object Download

The tool shall support downloading digital objects for a record.

Acceptance criteria:

- Downloads use safe, stable filenames.
- Existing files are not overwritten unless explicitly requested.
- SHA-256 is computed for every downloaded file.
- A JSON download manifest is produced.
- Download selection supports all objects, numeric ranges, and explicit indexes.

### BR-006: Search Download Workflow

Search shall optionally download digital objects from returned records.

Example target command:

```bash
nara_api.py search --query '"Arthur Davis Variell" passport' --online --download-dir /tmp/nara-passport
```

Acceptance criteria:

- Search result metadata and downloaded objects are grouped by NAID.
- Limits and confirmation safeguards prevent accidental bulk downloads.
- The output states how many records and digital objects were downloaded or skipped.

### BR-007: Hierarchy Browsing

The tool shall help users browse record hierarchy around a NAID.

Minimum modes:

- show ancestors;
- show parent;
- show likely series;
- list sibling file units when practical;
- search within ancestor or parent NAID.

### BR-008: Related Records

The tool shall support related-record discovery around a known NAID.

Minimum modes:

- same parent;
- same series or ancestor;
- same record group;
- similar title/query terms;
- records referencing the same NAID if supported by API fields.

### BR-009: Count-Only Search

The tool shall support count-only queries for quick scoping and negative-search logging.

Example target command:

```bash
nara_api.py search --query 'Variell' --count
```

Acceptance criteria:

- Prints query, filters, total hit count, and timestamp.
- Does not fetch unnecessary result pages.
- Can save a negative-search draft if total is zero or below a researcher-specified threshold.

### BR-010: Date Filter Documentation

The CLI help and README shall document date filter behavior and known uncertainty.

Acceptance criteria:

- `--start-date` and `--end-date` help text maps clearly to NARA API parameters.
- Examples show exact date, year-only, and range searches where supported.
- Documentation warns that archival date ranges may not behave like event dates.

### BR-011: Source Packet Creation

The tool shall generate source-packet metadata aligned with repository workflow.

Minimum source packet contents:

- source ID;
- NAID;
- catalog URL;
- API path and request parameters;
- fetched timestamp;
- raw JSON local path;
- downloaded object local paths;
- SHA-256 for every local file;
- suggested source-registry stub;
- suggested source-manifest rows;
- rights/use note including NARA attribution language;
- gaps and next-action placeholders.

### BR-012: Negative Search Support

The tool shall help create negative-search drafts for `research/negative-searches.md` and `sources/negative-search-registry.yaml`.

Minimum fields:

- query;
- filters;
- NARA API endpoint;
- date searched;
- total hits;
- false positives inspected;
- scope limits;
- confidence;
- related ticket/source IDs;
- next action.

### BR-013: MCP Server

The project shall provide an MCP server exposing read-only NARA research capabilities.

Initial MCP tools:

- `nara_check_key`;
- `nara_search_records`;
- `nara_count_records`;
- `nara_get_record`;
- `nara_list_digital_objects`;
- `nara_download_digital_objects`;
- `nara_browse_hierarchy`;
- `nara_find_related_records`;
- `nara_make_source_packet`;
- `nara_make_negative_search_record`.

Initial MCP resources:

- `nara://record/{naid}`;
- `nara://record/{naid}/compact`;
- `nara://record/{naid}/digital-objects`;
- `nara://search/{encoded_query}`;

Initial MCP prompts:

- `nara_person_search_plan`;
- `nara_source_note_from_record`;
- `nara_negative_search_log`;
- `nara_passport_record_review`.

### BR-014: MCP Standards Alignment

The MCP server shall target the latest MCP specification confirmed during planning: `2025-11-25`.

Relevant standard expectations:

- use JSON-RPC via the official SDK rather than hand-rolled protocol code;
- support `stdio` first;
- add Streamable HTTP only after local stdio is stable;
- for Streamable HTTP, use a single MCP endpoint, bind local development servers to localhost, validate `Origin`, and respect protocol version/session headers;
- expose tools with clear names, descriptions, input schemas, and structured output.

### BR-015: Rate Limit Awareness

The tool shall make NARA API usage visible.

Acceptance criteria:

- Every result includes enough request metadata to audit API usage.
- Documentation states NARA's default monthly query limit.
- Commands that may download many records or files require explicit limits or confirmation flags.

### BR-016: Secret Safety

The tool shall never print or save the NARA API key.

Acceptance criteria:

- Logs and errors identify key source only by safe label/path.
- MCP tool results never include secret values.
- HTTP MCP mode, if added, does not expose the key to remote clients.

## 9. Functional Requirements by Interface

### 9.1 CLI

Target commands:

```bash
nara_api.py check-key --live
nara_api.py search --query QUERY --online
nara_api.py search --query QUERY --online --json
nara_api.py search --query QUERY --count
nara_api.py search --query QUERY --download-dir PATH --limit 5
nara_api.py record --naid NAID --save PATH
nara_api.py images --naid NAID
nara_api.py images --naid NAID --download-dir PATH --range 1-5
nara_api.py browse --naid NAID
nara_api.py related --naid NAID --mode same-parent
nara_api.py source-packet --naid NAID --source-id S061 --archive-root ../..
nara_api.py negative-search --query QUERY --online
```

### 9.2 Python API

The Python API should use typed request and response objects. Pydantic is preferred for schema reuse with MCP and clear validation.

Suggested modules:

```text
src/nara_catalog/
  client.py
  models.py
  compact.py
  archive.py
  agent_api.py
  cli.py
  mcp_server.py
```

### 9.3 MCP

The MCP implementation should use the official Python MCP SDK or a compatible high-level framework that tracks the current spec. The MCP server should initially be local-only over stdio.

MCP tools should return structured data first, with short text summaries as convenience content.

## 10. Prioritization

### P0: Foundation

- Refactor current script into package modules.
- Add tests for current search/record compaction behavior using fixtures.
- Preserve existing commands.

### P1: Research Usability

- Compact search output.
- `images` list command.
- Count-only search.
- Better date help.

### P2: Preservation Workflows

- Digital-object download.
- Search `--download-dir`.
- Source-packet generation.
- Negative-search draft generation.

### P3: Discovery Workflows

- `browse --naid`.
- `related --naid`.
- Sibling/series traversal.

### P4: MCP

- Local stdio MCP server.
- MCP tools/resources/prompts.
- MCP contract tests.

### P5: Remote/HTTP MCP

- Streamable HTTP transport.
- Localhost binding and origin validation.
- Optional authentication design if remote use is ever required.

## 11. Data and Output Standards

All preserved NARA files should follow repository naming conventions:

```text
S###-nara-{naid}.json
S###-nara-{naid}-img{n}.{ext}
S###-nara-{naid}-download-manifest.json
```

Every preservation action should produce:

- local path;
- SHA-256;
- source URL;
- access date;
- NAID;
- API request parameters;
- rights/use note;
- overwrite/skipped status.

Raw source files must not be overwritten. Derivatives should be explicitly marked.

## 12. Security, Compliance, and Historical Method

- Treat NARA API keys as secrets.
- Keep API keys out of source files, markdown logs, MCP results, and error messages.
- Use the API respectfully and within NARA terms.
- Preserve source uncertainty; NARA metadata identifies records but does not by itself prove every historical interpretation.
- Keep negative searches.
- Do not infer honors, titles, legal status, or family relationships from catalog metadata alone.

## 13. Success Metrics

1. A researcher can run a NARA search and scan results without piping to a custom formatter.
2. A researcher can list image URLs for a NAID in one command.
3. A researcher can download selected digital objects with hashes and a manifest in one command.
4. An agent can create a source-packet draft from a NAID without hand-editing nested JSON.
5. The MCP server can be connected by an MCP client and expose NARA search, record fetch, image listing, and source-packet tools.
6. Existing CLI use cases continue to work.

## 14. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| NARA API schema varies across record types | Centralize parsing in `compact.py`; preserve raw JSON; include warnings for missing fields. |
| Large digital object sets cause accidental bulk download | Require explicit limits/ranges; show counts; default to listing, not downloading. |
| API key exposure through MCP | Local stdio first; never return env values; avoid remote HTTP until reviewed. |
| MCP spec drift | Use official SDK; document target spec version; add contract tests. |
| CLI/MCP behavior drift | Make both call the same `agent_api.py` functions. |
| Historical over-interpretation | Source packets carry metadata and evidence status, not narrative conclusions. |

## 15. Open Questions

1. Should compact output become the default immediately, or should it be introduced as `--compact` first?
2. What should the default maximum digital-object download count be?
3. Should source-packet generation directly edit registry/manifest files, or only emit suggested stubs for review?
4. Which MCP clients are primary targets for local configuration?
5. Should the MCP server expose repository-writing tools, or only return source-packet drafts?
6. Do we want a local SQLite cache for NARA records and digital-object metadata?

## 16. Proposed Implementation Plan

1. Create Python package skeleton and move current functions into modules.
2. Add fixture-based tests for `compact_hit`, search response parsing, and record parsing.
3. Implement compact CLI output and `--json` output mode.
4. Implement `images --naid` listing.
5. Implement count-only search.
6. Implement digital-object download with hashes and manifests.
7. Implement source-packet generation.
8. Implement hierarchy browse and related-record helpers.
9. Implement stdio MCP server.
10. Add README examples and MCP client configuration notes.

## 17. Reference Notes

Planning references checked on 2026-06-17:

- NARA API help page: `https://www.archives.gov/research/catalog/help/api`
- NARA Catalog API GitHub: `https://github.com/usnationalarchives/Catalog-API`
- MCP specification, latest observed version: `https://modelcontextprotocol.io/specification/2025-11-25`
- MCP transports: `https://modelcontextprotocol.io/specification/2025-11-25/basic/transports`
- MCP tools: `https://modelcontextprotocol.io/specification/2025-11-25/server/tools`
- MCP resources: `https://modelcontextprotocol.io/specification/2025-11-25/server/resources`
- MCP Python SDK: `https://pypi.org/project/mcp/`
