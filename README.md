# NARA Catalog API Helper

Read-only CLI for the National Archives Catalog API v2.

## Setup

1. Get an API key: email `Catalog_API@nara.gov` requesting a read-only key for
   noncommercial historical research
2. Save it as `NARA_API_KEY=your-key-here` in the project `.env` file

## Usage

From the project root:

```bash
# Verify your key works
python tools/nara-catalog-api/nara_api.py check-key --live

# Search for a person
python tools/nara-catalog-api/nara_api.py search --query '"Arthur Davis Variell"' --limit 10

# Search only records available online
python tools/nara-catalog-api/nara_api.py search --query 'Variell AND passport' --online

# Fetch a specific record by NAID (saves raw JSON)
python tools/nara-catalog-api/nara_api.py record --naid 235845456 --save archive/source-json/S061-nara-235845456.json

# Summarize a saved record
python tools/nara-catalog-api/nara_api.py summarize-file archive/source-json/S061-nara-235845456.json
```

## Credential Resolution

The script looks for `NARA_API_KEY` in this order:

1. `NARA_API_KEY` environment variable
2. `--secret-file /path/to/file` (if passed)
3. `.env` in the current working directory (project-local)
4. `~/.hermes/secrets/nara.env` (global fallback)

Run from the project root and the key in `.env` is picked up automatically.

## Options

### check-key
- `--live` — validate the key against the API
- `--require` — exit nonzero if key missing
- `--save <path>` — save result JSON

### search
- `--query` / `-q` (required) — query string, supports AND/OR and exact phrases in quotes
- `--limit` (default 10)
- `--page` (default 1)
- `--online` — only records with digital objects
- `--abbreviated` — compact response
- `--include-extracted-text` — include OCR/extracted text
- `--type-of-materials` — e.g. "Textual Records"
- `--record-group-number` — e.g. "388"
- `--ancestor-naid` — search within a series
- `--start-date` / `--endDate` — date range
- `--full` — raw hits instead of compact summaries
- `--save <path>` — save results

### record
- `--naid` (required)
- `--include-extracted-text`
- `--save <path>`
- `--timeout` (default 60)

### summarize-file
- `path` — JSON file saved by `search` or `record`
