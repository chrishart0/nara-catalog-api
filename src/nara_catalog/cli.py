from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config import DEFAULT_SECRET_FILE
from .models import SearchRequest, to_plain
from .service import MissingApiKeyError, NaraCatalogService


def emit_json(data: object, save: str | None = None) -> None:
    text = json.dumps(to_plain(data), indent=2, ensure_ascii=False)
    if save:
        path = Path(save).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n")
        print(f"saved={path}")
    else:
        print(text)


def emit_search_compact(response) -> None:
    print(f"Total: {response.total} results")
    print(f"Returned: {response.returned}")
    for i, record in enumerate(response.records, 1):
        title = record.title or "(untitled)"
        na_id = record.na_id or "unknown"
        print(f"[{i}] NAID {na_id} - {title}")
        context = _context_line(record)
        if context:
            print(f"    {context}")
        if record.catalog_url:
            print(f"    {record.catalog_url}")


def emit_digital_objects(objects) -> None:
    print(f"Digital objects: {len(objects)}")
    for obj in objects:
        file_name = obj.file_name or "(no filename)"
        obj_type = obj.object_type or "object"
        text = "text" if obj.has_extracted_text else "no-text"
        print(f"[{obj.index}] {obj_type} | {file_name} | {text}")
        if obj.title:
            print(f"    {obj.title}")
        if obj.object_url:
            print(f"    {obj.object_url}")


def _context_line(record) -> str:
    parts = []
    if record.level_of_description:
        parts.append(record.level_of_description)
    if record.record_group_number:
        parts.append(f"RG-{record.record_group_number}")
    elif record.collection_identifier:
        parts.append(str(record.collection_identifier))
    if record.digital_object_count is not None:
        parts.append(f"{record.digital_object_count} digital objects")
    if record.source_platform:
        parts.append(record.source_platform)
    return " | ".join(parts)


def request_from_args(args: argparse.Namespace, *, limit_override: int | None = None) -> SearchRequest:
    return SearchRequest(
        query=args.query,
        limit=limit_override if limit_override is not None else args.limit,
        page=args.page,
        online=args.online,
        abbreviated=args.abbreviated,
        include_extracted_text=args.include_extracted_text,
        type_of_materials=args.type_of_materials,
        object_type=args.object_type,
        record_group_number=args.record_group_number,
        reference_units=args.reference_units,
        ancestor_naid=args.ancestor_naid,
        start_date=args.start_date,
        end_date=args.end_date,
        source_includes=args.source_includes,
    )


def service_from_args(args: argparse.Namespace) -> NaraCatalogService:
    return NaraCatalogService.from_environment(secret_file=args.secret_file, timeout=getattr(args, "timeout", 60))


def cmd_check_key(args: argparse.Namespace) -> int:
    result = NaraCatalogService.check_key(live=args.live, secret_file=args.secret_file, require=args.require)
    emit_json(result, args.save)
    return 0 if result.key_present or not args.require else 2


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


def cmd_search(args: argparse.Namespace) -> int:
    service = service_from_args(args)
    request = request_from_args(args)
    if args.count:
        response = service.count_records(request, timeout=args.timeout)
        if args.json or args.save:
            emit_json(response, args.save)
        else:
            print(f"Query: {request.query}")
            print(f"Filters: {json.dumps(response.request.params, ensure_ascii=False)}")
            print(f"Total: {response.total}")
            print(f"Fetched epoch: {response.request.fetched_at_epoch}")
        return 0

    response = service.search_records(request, timeout=args.timeout)
    download_manifests = []
    if args.download_dir:
        if response.returned > args.download_record_limit and not args.yes:
            print(
                f"Refusing to download from {response.returned} records without --yes; "
                f"use --download-record-limit or lower --limit.",
                file=sys.stderr,
            )
            return 2
        for record in response.records[: args.download_record_limit]:
            if record.na_id:
                dest = Path(args.download_dir).expanduser() / str(record.na_id)
                download_manifests.append(
                    service.download_digital_objects(record.na_id, dest, selection=args.range, force=args.force, timeout=args.timeout)
                )
    if args.json or args.full:
        payload = response.raw if args.full else response
        if download_manifests:
            payload = {"search": payload, "downloads": download_manifests}
        emit_json(payload, args.save)
    elif args.save:
        payload = {"search": response, "downloads": download_manifests} if download_manifests else response
        emit_json(payload, args.save)
    else:
        emit_search_compact(response)
        if download_manifests:
            _print_download_totals(download_manifests)
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    service = service_from_args(args)
    response = service.get_record(args.naid, include_extracted_text=args.include_extracted_text, timeout=args.timeout)
    emit_json(response.raw if args.full else response, args.save)
    return 0 if response.found else 1


def cmd_images(args: argparse.Namespace) -> int:
    service = service_from_args(args)
    objects = service.list_digital_objects(args.naid, timeout=args.timeout)
    if args.download_dir:
        manifest = service.download_digital_objects(
            args.naid,
            Path(args.download_dir).expanduser(),
            selection=args.range,
            force=args.force,
            timeout=args.timeout,
        )
        emit_json(manifest, args.save) if args.json or args.save else _print_manifest(manifest)
    elif args.json or args.save:
        emit_json(objects, args.save)
    else:
        emit_digital_objects(objects)
    return 0


def cmd_browse(args: argparse.Namespace) -> int:
    service = service_from_args(args)
    result = service.browse_hierarchy(args.naid, include_siblings=args.siblings, sibling_limit=args.limit, timeout=args.timeout)
    if args.json or args.save:
        emit_json(result, args.save)
        return 0
    print(f"NAID: {result.na_id}")
    if result.parent:
        print(f"Parent: {result.parent.get('naId')} - {result.parent.get('title')}")
    if result.likely_series:
        print(f"Likely series: {result.likely_series.get('naId')} - {result.likely_series.get('title')}")
    print("Ancestors:")
    for item in result.ancestors:
        print(f"- {item.get('naId')} | {item.get('level')} | {item.get('title')}")
    if result.siblings:
        print("Sibling/search-within-parent results:")
        emit_search_compact(result.siblings)
    return 0


def cmd_related(args: argparse.Namespace) -> int:
    service = service_from_args(args)
    result = service.find_related_records(args.naid, mode=args.mode, limit=args.limit, timeout=args.timeout)
    if args.json or args.save:
        emit_json(result, args.save)
    elif result.search:
        print(f"Mode: {result.mode}")
        print(f"Basis: {json.dumps(result.basis, ensure_ascii=False)}")
        emit_search_compact(result.search)
    else:
        print(f"No related-record search basis found for NAID {args.naid} mode {args.mode}")
    return 0


def cmd_source_packet(args: argparse.Namespace) -> int:
    service = service_from_args(args)
    packet = service.make_source_packet(args.naid, args.source_id, Path(args.archive_root).expanduser(), timeout=args.timeout)
    emit_json(packet, args.save) if args.json or args.save else print(f"source_packet={packet.packet_path}")
    return 0


def cmd_negative_search(args: argparse.Namespace) -> int:
    service = service_from_args(args)
    draft = service.make_negative_search_record(request_from_args(args), threshold=args.threshold, timeout=args.timeout)
    if args.json or args.save:
        emit_json(draft, args.save)
    else:
        print(draft.markdown)
    return 0


def cmd_summarize_file(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.path).expanduser().read_text())
    if "records" in data:
        print(f"query: {data.get('query')}")
        print(f"returned: {data.get('returned')} total: {data.get('total')}")
        for i, result in enumerate(data.get("records") or [], 1):
            print(f"\n[{i}] NAID {result.get('na_id')} - {result.get('title')}")
            print(f"    level: {result.get('level_of_description')} dates: {result.get('dates')}")
            print(f"    url: {result.get('catalog_url')}")
    elif "results" in data:
        print(f"query: {data.get('query')}")
        print(f"params: {json.dumps(data.get('params'), ensure_ascii=False)}")
        print(f"returned: {data.get('returned')} total: {data.get('total')}")
        for i, result in enumerate(data.get("results") or [], 1):
            print(f"\n[{i}] NAID {result.get('naId')} - {result.get('title')}")
            print(f"    level: {result.get('levelOfDescription')} dates: {result.get('dates')}")
            print(f"    url: {result.get('catalogUrl')}")
    elif "record" in data:
        compact = data.get("compact") or {}
        print(f"NAID: {data.get('naId') or data.get('na_id')} found={data.get('found')}")
        print(f"title: {compact.get('title')}")
        print(f"level: {compact.get('levelOfDescription') or compact.get('level_of_description')} dates: {compact.get('dates')}")
        print(f"url: {compact.get('catalogUrl') or compact.get('catalog_url')}")
    else:
        print("Unrecognized JSON structure", file=sys.stderr)
        return 1
    return 0


def _print_manifest(manifest) -> None:
    downloaded = sum(1 for r in manifest.results if r.status == "downloaded")
    skipped = sum(1 for r in manifest.results if r.status.startswith("skipped"))
    failed = sum(1 for r in manifest.results if r.status == "failed")
    print(f"Download manifest: {manifest.destination}")
    print(f"downloaded={downloaded} skipped={skipped} failed={failed}")


def _print_download_totals(manifests) -> None:
    records = len(manifests)
    downloaded = sum(1 for m in manifests for r in m.results if r.status == "downloaded")
    skipped = sum(1 for m in manifests for r in m.results if r.status.startswith("skipped"))
    failed = sum(1 for m in manifests for r in m.results if r.status == "failed")
    print(f"Downloads: records={records} downloaded={downloaded} skipped={skipped} failed={failed}")


def add_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--query", required=True, help='Query string; supports API boolean syntax such as AND/OR and exact phrases.')
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--online", action="store_true", help="Set NARA API availableOnline=true.")
    parser.add_argument("--abbreviated", action="store_true")
    parser.add_argument("--include-extracted-text", action="store_true")
    parser.add_argument("--type-of-materials")
    parser.add_argument("--object-type")
    parser.add_argument("--record-group-number")
    parser.add_argument("--reference-units")
    parser.add_argument("--ancestor-naid")
    parser.add_argument("--start-date", help="Maps to NARA API startDate. Date-range behavior depends on catalog metadata.")
    parser.add_argument("--end-date", help="Maps to NARA API endDate. Date-range behavior depends on catalog metadata.")
    parser.add_argument("--source-includes")


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

    search = sub.add_parser("search", help="Search NARA Catalog records. Compact text is the default output.")
    add_search_args(search)
    search.add_argument("--count", action="store_true", help="Only fetch enough data to report the total hit count.")
    search.add_argument("--compact", action="store_true", help="Explicitly request compact text output; this is already the default.")
    search.add_argument("--json", action="store_true", help="Print normalized machine-readable JSON.")
    search.add_argument("--full", action="store_true", help="Print/save raw NARA API JSON.")
    search.add_argument("--save", help="Save JSON output to a file.")
    search.add_argument("--download-dir", help="Download digital objects from returned records into this directory.")
    search.add_argument("--download-record-limit", type=int, default=5)
    search.add_argument("--range", help="Digital-object indexes or ranges to download, e.g. 1,3-5. Default all.")
    search.add_argument("--force", action="store_true", help="Allow downloads to overwrite existing files.")
    search.add_argument("--yes", action="store_true", help="Confirm potentially large search-result downloads.")
    search.add_argument("--timeout", type=int, default=60)
    search.set_defaults(func=cmd_search)

    record = sub.add_parser("record", help="Fetch a single record by NAID using naId_is.")
    record.add_argument("--naid", required=True)
    record.add_argument("--include-extracted-text", action="store_true")
    record.add_argument("--json", action="store_true", help="Accepted for consistency; record output is JSON by default.")
    record.add_argument("--full", action="store_true", help="Print/save raw NARA API JSON.")
    record.add_argument("--save")
    record.add_argument("--timeout", type=int, default=60)
    record.set_defaults(func=cmd_record)

    images = sub.add_parser("images", help="List or download digital objects for a NAID.")
    images.add_argument("--naid", required=True)
    images.add_argument("--json", action="store_true")
    images.add_argument("--save")
    images.add_argument("--download-dir")
    images.add_argument("--range", help="Digital-object indexes or ranges, e.g. 1,3-5. Default all.")
    images.add_argument("--force", action="store_true")
    images.add_argument("--timeout", type=int, default=60)
    images.set_defaults(func=cmd_images)

    browse = sub.add_parser("browse", help="Show hierarchy around a NAID.")
    browse.add_argument("--naid", required=True)
    browse.add_argument("--json", action="store_true")
    browse.add_argument("--save")
    browse.add_argument("--siblings", action="store_true", help="Also list records under the same parent when a parent NAID is available.")
    browse.add_argument("--limit", type=int, default=10, help="Sibling/search-within-parent result limit.")
    browse.add_argument("--timeout", type=int, default=60)
    browse.set_defaults(func=cmd_browse)

    related = sub.add_parser("related", help="Find related records around a NAID.")
    related.add_argument("--naid", required=True)
    related.add_argument("--mode", default="same-parent", choices=["same-parent", "same-series", "same-ancestor", "same-record-group", "similar-title"])
    related.add_argument("--limit", type=int, default=10)
    related.add_argument("--json", action="store_true")
    related.add_argument("--save")
    related.add_argument("--timeout", type=int, default=60)
    related.set_defaults(func=cmd_related)

    packet = sub.add_parser("source-packet", help="Create a repository-style NARA source-packet draft.")
    packet.add_argument("--naid", required=True)
    packet.add_argument("--source-id", required=True)
    packet.add_argument("--archive-root", required=True)
    packet.add_argument("--json", action="store_true")
    packet.add_argument("--save")
    packet.add_argument("--timeout", type=int, default=60)
    packet.set_defaults(func=cmd_source_packet)

    neg = sub.add_parser("negative-search", help="Create a negative-search draft from a NARA query.")
    add_search_args(neg)
    neg.add_argument("--threshold", type=int, default=0)
    neg.add_argument("--json", action="store_true")
    neg.add_argument("--save")
    neg.add_argument("--timeout", type=int, default=60)
    neg.set_defaults(func=cmd_negative_search)

    summarize = sub.add_parser("summarize-file", help="Summarize JSON saved by this helper.")
    summarize.add_argument("path")
    summarize.set_defaults(func=cmd_summarize_file)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileExistsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except MissingApiKeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
