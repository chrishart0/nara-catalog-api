#!/usr/bin/env python3
"""Read-only helper for the National Archives Catalog API v2.

The v2 API documentation says requests require an API key in the x-api-key
header. This helper reads NARA_API_KEY from (1) the NARA_API_KEY env var,
(2) --secret-file path, (3) .env in the current directory (project-local),
or (4) ~/.hermes/secrets/nara.env (global fallback). It never prints the key.

Examples:
  nara_api.py check-key
  nara_api.py search --query '"Arthur Davis Variell"' --limit 10 --online
  nara_api.py record --naid 123456 --include-extracted-text --save /tmp/nara-123456.json
  nara_api.py summarize-file /tmp/nara-123456.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

BASE_URL = "https://catalog.archives.gov/api/v2"
DEFAULT_SECRET_FILE = Path.home() / ".hermes/secrets/nara.env"
PROJECT_ENV_FILE = Path.cwd() / ".env"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_api_key(secret_file: str | None = None) -> tuple[str | None, str]:
    if os.environ.get("NARA_API_KEY"):
        return os.environ["NARA_API_KEY"], "environment:NARA_API_KEY"
    if secret_file:
        path = Path(secret_file).expanduser()
        values = load_env_file(path)
        if values.get("NARA_API_KEY"):
            return values["NARA_API_KEY"], str(path)
        return None, str(path)
    # Prefer project-local .env over global secret file
    for candidate in (PROJECT_ENV_FILE, DEFAULT_SECRET_FILE):
        values = load_env_file(candidate)
        if values.get("NARA_API_KEY"):
            return values["NARA_API_KEY"], str(candidate)
    return None, str(DEFAULT_SECRET_FILE)


def api_get(path: str, *, api_key: str, params: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    url = BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": api_key,
        "User-Agent": "Hermes NARA Catalog research helper (read-only historical research)",
    }
    response = requests.get(url, headers=headers, params=params or {}, timeout=timeout)
    ctype = response.headers.get("content-type", "")
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status_code} from {response.url}: {response.text[:500]}")
    if "json" not in ctype.lower():
        raise RuntimeError(
            f"Expected JSON but got content-type {ctype!r} from {response.url}. "
            "If this is the Catalog single-page app HTML, check that the API key is valid."
        )
    return response.json()


def hit_source(hit: dict[str, Any]) -> dict[str, Any]:
    return hit.get("_source") or hit.get("source") or hit


def record_from_hit(hit: dict[str, Any]) -> dict[str, Any]:
    source = hit_source(hit)
    return source.get("record") or source.get("metadata", {}).get("record") or source


def compact_hit(hit: dict[str, Any]) -> dict[str, Any]:
    record = record_from_hit(hit)
    control = record.get("controlGroup") or {}
    dates = record.get("dates") or record.get("date") or record.get("inclusiveDates")
    digital_objects = record.get("digitalObjects") or []
    ancestors = record.get("ancestors") or []
    title = record.get("title") or record.get("heading") or record.get("name")
    naid = record.get("naId") or record.get("naIds") or control.get("naId") or hit.get("_id")
    return {
        "naId": naid,
        "title": title,
        "levelOfDescription": record.get("levelOfDescription") or record.get("descriptionType"),
        "dates": dates,
        "typeOfMaterials": record.get("typeOfMaterials"),
        "recordGroupNumber": record.get("recordGroupNumber"),
        "collectionIdentifier": record.get("collectionIdentifier"),
        "availableOnline": record.get("availableOnline"),
        "digitalObjectCount": record.get("digitalObjectCount") or len(digital_objects),
        "digitalObjects": summarize_digital_objects(digital_objects),
        "ancestors": summarize_ancestors(ancestors),
        "catalogUrl": f"https://catalog.archives.gov/id/{naid}" if naid else None,
    }


def summarize_digital_objects(objs: Any, limit: int = 5) -> list[dict[str, Any]]:
    if not isinstance(objs, list):
        return []
    out: list[dict[str, Any]] = []
    for obj in objs[:limit]:
        if not isinstance(obj, dict):
            continue
        out.append({
            "objectType": obj.get("objectType"),
            "title": obj.get("title") or obj.get("caption"),
            "url": obj.get("objectUrl") or obj.get("url") or obj.get("fileUrl"),
            "thumbnailUrl": obj.get("thumbnailUrl"),
            "hasExtractedText": bool(obj.get("extractedText") or obj.get("otherExtractedText")),
        })
    return out


def summarize_ancestors(ancestors: Any, limit: int = 6) -> list[dict[str, Any]]:
    if not isinstance(ancestors, list):
        return []
    out: list[dict[str, Any]] = []
    for anc in ancestors[:limit]:
        if not isinstance(anc, dict):
            continue
        out.append({"naId": anc.get("naId"), "title": anc.get("title"), "level": anc.get("levelOfDescription")})
    return out


def emit(data: dict[str, Any], save: str | None) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if save:
        path = Path(save).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n")
        print(f"saved={path}")
    else:
        print(text)


def cmd_check_key(args: argparse.Namespace) -> int:
    key, source = get_api_key(args.secret_file)
    result = {
        "key_present": bool(key),
        "key_source": source if key else None,
        "secret_file_checked": source if not key else None,
        "api_base": BASE_URL,
    }
    if args.live and key:
        try:
            data = api_get("/records/search", api_key=key, params={"q": "constitution", "limit": 1, "abbreviated": "true"}, timeout=30)
            result["live_status"] = "ok"
            result["total"] = (((data.get("body") or {}).get("hits") or {}).get("total") or {}).get("value")
        except Exception as exc:
            result["live_status"] = "failed"
            result["error"] = str(exc)[:500]
    elif args.live and not key:
        result["live_status"] = "skipped_no_key"
    emit(result, args.save)
    return 0 if key or not args.require else 2


def cmd_search(args: argparse.Namespace) -> int:
    key, source = get_api_key(args.secret_file)
    if not key:
        print(f"NARA_API_KEY not found. Checked environment, project .env, and {source}. Create a .env in the project root or request a key from Catalog_API@nara.gov.", file=sys.stderr)
        return 2
    params: dict[str, Any] = {"q": args.query, "limit": args.limit, "page": args.page}
    if args.online:
        params["availableOnline"] = "true"
    if args.abbreviated:
        params["abbreviated"] = "true"
    if args.include_extracted_text:
        params["includeExtractedText"] = "true"
    if args.type_of_materials:
        params["typeOfMaterials"] = args.type_of_materials
    if args.object_type:
        params["objectType"] = args.object_type
    if args.record_group_number:
        params["recordGroupNumber"] = args.record_group_number
    if args.reference_units:
        params["referenceUnits"] = args.reference_units
    if args.ancestor_naid:
        params["ancestorNaId"] = args.ancestor_naid
    if args.start_date:
        params["startDate"] = args.start_date
    if args.end_date:
        params["endDate"] = args.end_date
    if args.source_includes:
        params["sourceIncludes"] = args.source_includes

    data = api_get("/records/search", api_key=key, params=params, timeout=args.timeout)
    hits_obj = ((data.get("body") or {}).get("hits") or {})
    hits = hits_obj.get("hits") or []
    total = hits_obj.get("total")
    out = {
        "query": args.query,
        "api_path": "/records/search",
        "params": {k: v for k, v in params.items() if k != "x-api-key"},
        "key_source": source,
        "total": total,
        "returned": len(hits),
        "results": hits if args.full else [compact_hit(h) for h in hits],
        "fetched_at_epoch": int(time.time()),
    }
    emit(out, args.save)
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    key, source = get_api_key(args.secret_file)
    if not key:
        print(f"NARA_API_KEY not found. Checked environment, project .env, and {source}. Create a .env in the project root or request a key from Catalog_API@nara.gov.", file=sys.stderr)
        return 2
    params: dict[str, Any] = {"naId_is": args.naid, "limit": 1}
    if args.include_extracted_text:
        params["includeExtractedText"] = "true"
    data = api_get("/records/search", api_key=key, params=params, timeout=args.timeout)
    hits = (((data.get("body") or {}).get("hits") or {}).get("hits") or [])
    out = {
        "naId": args.naid,
        "api_path": "/records/search",
        "params": params,
        "key_source": source,
        "found": bool(hits),
        "record": hits[0] if hits else None,
        "compact": compact_hit(hits[0]) if hits else None,
        "fetched_at_epoch": int(time.time()),
    }
    emit(out, args.save)
    return 0 if hits else 1


def cmd_summarize_file(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.path).expanduser().read_text())
    if "results" in data:
        print(f"query: {data.get('query')}")
        print(f"params: {json.dumps(data.get('params'), ensure_ascii=False)}")
        print(f"returned: {data.get('returned')} total: {data.get('total')}")
        for i, result in enumerate(data.get("results") or [], 1):
            print(f"\n[{i}] NAID {result.get('naId')} — {result.get('title')}")
            print(f"    level: {result.get('levelOfDescription')} dates: {result.get('dates')}")
            print(f"    url: {result.get('catalogUrl')}")
            if result.get("digitalObjects"):
                print(f"    digitalObjects: {len(result.get('digitalObjects'))} summarized")
    elif "record" in data:
        compact = data.get("compact") or {}
        print(f"NAID: {data.get('naId')} found={data.get('found')}")
        print(f"title: {compact.get('title')}")
        print(f"level: {compact.get('levelOfDescription')} dates: {compact.get('dates')}")
        print(f"url: {compact.get('catalogUrl')}")
        print(f"digitalObjects: {len(compact.get('digitalObjects') or [])}")
    else:
        print("Unrecognized JSON structure", file=sys.stderr)
        return 1
    return 0


def cmd_make_secret(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not args.force:
        print(f"exists={path}; not overwriting", file=sys.stderr)
        return 1
    path.write_text('# NARA_API_KEY=*** Request key from Catalog_API@nara.gov; keep this file outside project repos or in project .env (gitignored).\n')
    os.chmod(path, 0o600)
    print(f"created={path}")
    print("mode=0600")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only National Archives Catalog API v2 helper.")
    parser.add_argument("--secret-file", help=f"Secret env file; default {DEFAULT_SECRET_FILE}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check-key", help="Check whether a NARA API key is configured; never prints it.")
    check.add_argument("--live", action="store_true", help="If a key is present, run a one-result live API check.")
    check.add_argument("--require", action="store_true", help="Exit nonzero if key is missing.")
    check.add_argument("--save")
    check.set_defaults(func=cmd_check_key)

    mk = sub.add_parser("make-secret", help="Create a NARA API key placeholder file with 0600 permissions.")
    mk.add_argument("--path", default=str(DEFAULT_SECRET_FILE))
    mk.add_argument("--force", action="store_true")
    mk.set_defaults(func=cmd_make_secret)

    search = sub.add_parser("search", help="Search NARA Catalog records.")
    search.add_argument("--query", required=True, help='Query string; supports API boolean syntax such as AND/OR and exact phrases.')
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--page", type=int, default=1)
    search.add_argument("--online", action="store_true", help="Set availableOnline=true.")
    search.add_argument("--abbreviated", action="store_true")
    search.add_argument("--include-extracted-text", action="store_true")
    search.add_argument("--type-of-materials")
    search.add_argument("--object-type")
    search.add_argument("--record-group-number")
    search.add_argument("--reference-units")
    search.add_argument("--ancestor-naid")
    search.add_argument("--start-date")
    search.add_argument("--end-date")
    search.add_argument("--source-includes")
    search.add_argument("--full", action="store_true", help="Save/print raw hits rather than compact summaries.")
    search.add_argument("--save")
    search.add_argument("--timeout", type=int, default=60)
    search.set_defaults(func=cmd_search)

    record = sub.add_parser("record", help="Fetch a single record by NAID using naId_is.")
    record.add_argument("--naid", required=True)
    record.add_argument("--include-extracted-text", action="store_true")
    record.add_argument("--save")
    record.add_argument("--timeout", type=int, default=60)
    record.set_defaults(func=cmd_record)

    summarize = sub.add_parser("summarize-file", help="Summarize JSON saved by this helper.")
    summarize.add_argument("path")
    summarize.set_defaults(func=cmd_summarize_file)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
