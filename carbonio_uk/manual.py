"""Offline manual export/import workflow; never merges translations."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import yaml

from .fetch import LANGUAGES, cache_path
from .formats.catalog import load_catalog
from .manifest import audit_components, load_manifest
from .validate import markup_signature, placeholder_signature


TSV_FIELDS = ("component", "key", "EN", "RU reference", "UK candidate", "placeholders", "markup", "status")


def _counter_rows(value: Any) -> list[dict[str, Any]]:
    return [{"token": token, "count": count} for token, count in sorted(value.items(), key=lambda item: str(item[0]))]


def export_manual(manifest: Path, cache_root: Path, glossary: Path) -> dict[str, Any]:
    rows = []
    data = load_manifest(manifest)
    for component_name, component in audit_components(data).items():
        translation = component["translation"]
        catalogs = {}
        for language, field in LANGUAGES.items():
            path = cache_path(cache_root, component_name, component["commit"], language, translation[field])
            catalogs[language], errors = load_catalog(path, translation["type"])
            if errors:
                raise ValueError(f"cannot export {component_name}:{language}: {errors}")
        en, ru, uk = catalogs["en"], catalogs["ru"], catalogs["uk"]
        needed = sorted(key for key in en if key not in uk or uk[key] is None or (isinstance(uk[key], str) and not uk[key].strip()))
        for key in needed:
            identity = hashlib.sha256(f"{component_name}\0{key}".encode()).hexdigest()[:20]
            source_status = ("missing_uk" if key not in uk else "null_uk" if uk[key] is None else "empty_uk")
            rows.append({
                "id": identity, "component": component_name, "repository": component["repository"],
                "commit": component["commit"], "key": key, "en": en[key], "ru_reference": ru.get(key),
                "placeholders": _counter_rows(placeholder_signature(en[key])),
                "markup": [{"closing": closing == "/", "tag": tag, "count": count}
                           for (closing, tag), count in sorted(markup_signature(en[key]).items())],
                "uk_candidate": "", "status": source_status,
            })
    return {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "mode": "manual/offline",
        "automatic_merge": False,
        "instructions": "Fill only UK candidate. Preserve placeholders and markup exactly; translate from EN; RU is reference-only.",
        "rows": rows,
    }


def render_manual(document: dict[str, Any]) -> str:
    sections = [
        "# Offline manual translation pilot",
        "",
        "Fill `uk_candidate` in `review/manual-pilot.yaml`; this Markdown file is a read-only review view.",
        "Automatic merge: `disabled`.",
        "",
    ]
    for index, row in enumerate(document["rows"], 1):
        context = ", ".join(f"{key} → {value}" for key, value in row.get("glossary_context", {}).items()) or "none"
        placeholders = ", ".join(f"{item['token']} × {item['count']}" for item in row["placeholders"]) or "none"
        markup = ", ".join(
            f"{'closing ' if item['closing'] else 'opening '}{item['tag']} × {item['count']}" for item in row["markup"]
        ) or "none"
        ru = row["ru_reference"] if row["ru_reference"] is not None else "missing"
        sections.extend(
            [
                f"## {index}. {row['component']}: `{row['key']}`",
                "",
                f"- EN: `{row['en']}`",
                f"- RU reference: `{ru}`",
                f"- Glossary context: {context}",
                f"- Placeholders: {placeholders}",
                f"- Markup: {markup}",
                "- UK candidate: ``",
                f"- Status: `{row['status']}`",
                "",
            ]
        )
    return "\n".join(sections)


def write_export(document: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".tsv":
        with output.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=TSV_FIELDS, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            for row in document["rows"]:
                writer.writerow({
                    "component": row["component"], "key": row["key"], "EN": row["en"],
                    "RU reference": "" if row["ru_reference"] is None else row["ru_reference"],
                    "UK candidate": row["uk_candidate"],
                    "placeholders": json.dumps(row["placeholders"], ensure_ascii=False, separators=(",", ":")),
                    "markup": json.dumps(row["markup"], ensure_ascii=False, separators=(",", ":")),
                    "status": row["status"],
                })
    else:
        output.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_tsv(source: Path) -> dict[str, Any]:
    try:
        content = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"manual TSV is not valid UTF-8: {error}") from error
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    if tuple(reader.fieldnames or ()) != TSV_FIELDS:
        raise ValueError(f"manual TSV columns must be exactly: {', '.join(TSV_FIELDS)}")
    rows = []
    for number, raw in enumerate(reader, 2):
        try:
            placeholders = json.loads(raw["placeholders"])
            markup = json.loads(raw["markup"])
        except json.JSONDecodeError as error:
            raise ValueError(f"manual TSV line {number}: invalid placeholders/markup JSON: {error}") from error
        component, key = raw["component"], raw["key"]
        rows.append({
            "id": hashlib.sha256(f"{component}\0{key}".encode()).hexdigest()[:20],
            "component": component, "key": key, "en": raw["EN"],
            "ru_reference": raw["RU reference"] or None, "uk_candidate": raw["UK candidate"],
            "placeholders": placeholders, "markup": markup, "status": raw["status"],
        })
    return {"schema": 1, "mode": "manual/offline-tsv", "automatic_merge": False, "rows": rows}


def validate_manual(document: dict[str, Any]) -> dict[str, Any]:
    results = []
    for row in document.get("rows", []):
        candidate = row.get("uk_candidate")
        non_empty = isinstance(candidate, str) and bool(candidate.strip())
        placeholders = non_empty and placeholder_signature(row["en"]) == placeholder_signature(candidate)
        markup = non_empty and markup_signature(row["en"]) == markup_signature(candidate)
        expected_placeholders = _counter_rows(placeholder_signature(row["en"]))
        expected_markup = [{"closing": closing == "/", "tag": tag, "count": count}
                           for (closing, tag), count in sorted(markup_signature(row["en"]).items())]
        validation = {
            "utf8": isinstance(candidate, str),
            "non_empty": non_empty,
            "placeholders": bool(placeholders),
            "markup": bool(markup),
            "metadata_placeholders": row.get("placeholders", expected_placeholders) == expected_placeholders,
            "metadata_markup": row.get("markup", expected_markup) == expected_markup,
        }
        results.append(
            {
                **row,
                "validation": validation,
                "status": "pending_review" if all(validation.values()) else "manual_validation_failed",
                "automatic_merge": False,
            }
        )
    return {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "mode": "manual/import",
        "automatic_merge": False,
        "valid": sum(row["status"] == "pending_review" for row in results),
        "invalid": sum(row["status"] != "pending_review" for row in results),
        "rows": results,
    }


def render_validation(report: dict[str, Any]) -> str:
    sections = [
        "# Manual pilot import validation",
        "",
        f"Valid: `{report['valid']}`. Invalid: `{report['invalid']}`. Automatic merge: `disabled`.",
        "",
    ]
    for row in report["rows"]:
        sections.extend(
            [
                f"## {row['component']}: `{row['key']}`",
                "",
                f"- EN: `{row['en']}`",
                f"- UK candidate: `{row['uk_candidate']}`",
                f"- Validation: `{row['validation']}`",
                f"- Status: `{row['status']}`",
                "",
            ]
        )
    return "\n".join(sections)


def import_manual(source: Path, pending_root: Path, report_path: Path) -> dict[str, Any]:
    if source.suffix.lower() == ".tsv":
        document = read_tsv(source)
    else:
        try:
            document = yaml.safe_load(source.read_text(encoding="utf-8"))
        except UnicodeDecodeError as error:
            raise ValueError(f"manual pilot is not valid UTF-8: {error}") from error
    report = validate_manual(document)
    for row in report["rows"]:
        target = pending_root / row["component"] / f"{row['id']}.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(row, allow_unicode=True, sort_keys=False), encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.with_suffix(".md").write_text(render_validation(report), encoding="utf-8")
    return report


def run_export(args: argparse.Namespace) -> int:
    document = export_manual(Path(args.manifest), Path(args.cache_root), Path(args.glossary))
    output = Path(args.output)
    write_export(document, output)
    print(f"exported {len(document['rows'])} missing/empty manual rows -> {output}")
    print("automatic merge: disabled")
    return 0


def run_import(args: argparse.Namespace) -> int:
    report = import_manual(Path(args.source), Path(args.pending_root), Path(args.report))
    print(f"manual import: valid={report['valid']} invalid={report['invalid']}; automatic merge: disabled")
    return 0 if report["invalid"] == 0 else 1


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("manual", help="offline manual pilot export/import")
    commands = parser.add_subparsers(dest="manual_command", required=True)
    export_parser = commands.add_parser("export", help="export all missing/empty UK values for offline translation")
    export_parser.add_argument("--manifest", default="manifest.yaml")
    export_parser.add_argument("--cache-root", default=".cache/upstream")
    export_parser.add_argument("--glossary", default="glossary/uk.yaml")
    export_parser.add_argument("--output", default="review/manual-pilot.tsv")
    export_parser.set_defaults(handler=run_export)
    import_parser = commands.add_parser("import", help="validate a filled manual workbook into pending sidecars")
    import_parser.add_argument("--source", default="review/manual-pilot.tsv")
    import_parser.add_argument("--pending-root", default="review/pending")
    import_parser.add_argument("--report", default="reports/manual-pilot-validation.json")
    import_parser.set_defaults(handler=run_import)
