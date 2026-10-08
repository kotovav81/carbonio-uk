"""Stage a reviewed manual TSV using the KEEP EXISTING UK policy."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import random
from typing import Any

from .fetch import LANGUAGES, cache_path
from .formats.catalog import load_catalog
from .manifest import audit_components, load_manifest
from .manual import read_tsv, validate_manual
from .merge import merge_flat_keep_existing, merge_with_flat_additions, usable
from .audit import audit as audit_overlay
from .validate import validate as validate_overlay, render_markdown as render_validation, render_findings


def _catalogs(name: str, component: dict[str, Any], cache_root: Path) -> dict[str, dict[str, Any]]:
    output = {}
    translation = component["translation"]
    for language, field in LANGUAGES.items():
        path = cache_path(cache_root, name, component["commit"], language, translation[field])
        output[language], errors = load_catalog(path, translation["type"])
        if errors:
            raise ValueError(f"invalid pinned catalog {name}:{language}: {errors}")
    return output


def stage(manifest_path: Path, cache_root: Path, source: Path, review_path: Path, output_root: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    components = audit_components(manifest)
    document = read_tsv(source)
    validation = validate_manual({"rows": [row for row in document["rows"] if row["uk_candidate"].strip()]})
    if validation["invalid"]:
        invalid = [f"{row['component']}:{row['key']}" for row in validation["rows"] if row["status"] != "pending_review"]
        raise ValueError(f"invalid manual candidates: {invalid}")
    review_rows = []
    if review_path.exists():
        with review_path.open(encoding="utf-8") as stream:
            import csv
            review_rows = list(csv.DictReader(stream, delimiter="\t"))

    catalogs = {name: _catalogs(name, component, cache_root) for name, component in components.items()}
    additions: dict[str, dict[str, Any]] = {name: {} for name in components}
    skipped_existing: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in document["rows"]:
        identity = (row["component"], row["key"])
        if identity in seen:
            raise ValueError(f"duplicate TSV row: {identity}")
        seen.add(identity)
        if row["component"] not in components:
            raise ValueError(f"unknown component: {row['component']}")
        pinned = catalogs[row["component"]]
        if row["key"] not in pinned["en"] or row["en"] != pinned["en"][row["key"]]:
            raise ValueError(f"EN mismatch: {row['component']}:{row['key']}")
        expected_ru = pinned["ru"].get(row["key"])
        if expected_ru == "":
            expected_ru = None
        if row["ru_reference"] != expected_ru:
            raise ValueError(f"RU reference mismatch: {row['component']}:{row['key']}")
        candidate = row["uk_candidate"]
        if not candidate.strip():
            continue
        existing = pinned["uk"].get(row["key"])
        if usable(existing):
            skipped_existing.append({"component": row["component"], "key": row["key"]})
            continue
        additions[row["component"]][row["key"]] = candidate

    results: dict[str, Any] = {}
    rng = random.Random(2924)
    for name, component in components.items():
        translation = component["translation"]
        en_path = cache_path(cache_root, name, component["commit"], "en", translation["english"])
        uk_path = cache_path(cache_root, name, component["commit"], "uk", translation["ukrainian"])
        target = output_root / name / Path(translation["ukrainian"]).name
        target.parent.mkdir(parents=True, exist_ok=True)
        if translation["type"] == "json":
            english_tree = json.loads(en_path.read_text(encoding="utf-8"))
            ukrainian_tree = json.loads(uk_path.read_text(encoding="utf-8"))
            merged = merge_with_flat_additions(english_tree, ukrainian_tree, additions[name], {})
            target.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            merged = merge_flat_keep_existing(catalogs[name]["en"], catalogs[name]["uk"], additions[name])
            target.write_text("".join(f"{key}={value}\n" for key, value in merged.items()), encoding="utf-8")
        keys = list(additions[name])
        sample_keys = rng.sample(keys, min(10, len(keys)))
        remaining = [key for key in catalogs[name]["en"] if not usable(catalogs[name]["uk"].get(key)) and key not in additions[name]]
        results[name] = {
            "repository": component["repository"], "commit": component["commit"], "output": str(target),
            "added": len(keys),
            "added_keys": keys,
            "remaining_missing_or_empty": len(remaining),
            "existing_uk_preserved": sum(usable(value) for value in catalogs[name]["uk"].values()),
            "examples": [{"key": key, "en": catalogs[name]["en"][key], "uk": additions[name][key]} for key in sample_keys],
            "review": [row for row in review_rows if row.get("component") == name],
        }
    return {
        "schema": 1, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": str(source), "output_root": str(output_root), "policy": "KEEP EXISTING UK",
        "candidates_validated": validation["valid"], "candidates_applied": sum(len(value) for value in additions.values()),
        "review_not_applied": len(review_rows), "existing_overwrite_attempts_skipped": skipped_existing,
        "components": results, "source_uk_unchanged": True,
    }


def render(report: dict[str, Any]) -> str:
    lines = ["# Staged manual merge 2924", "", f"Generated: `{report['generated_at']}`", "",
             f"Policy: `{report['policy']}`. Applied: `{report['candidates_applied']}`. Review not applied: `{report['review_not_applied']}`.", "",
             "| Component | Added | Remaining | Existing UK preserved | Placeholder errors | Markup errors |", "|---|---:|---:|---:|---:|---:|"]
    for name, item in report["components"].items():
        validation = item.get("validation", {})
        lines.append(f"| `{name}` | {item['added']} | {item['remaining_missing_or_empty']} | {item['existing_uk_preserved']} | "
                     f"{len(validation.get('placeholder_errors', []))} | {len(validation.get('markup_errors', []))} |")
    for name, item in report["components"].items():
        lines += ["", f"## {name}", "", "| Key | EN | UK |", "|---|---|---|"]
        for row in item["examples"]:
            esc = lambda value: str(value).replace("|", "\\|").replace("\n", "<br>")
            lines.append(f"| `{row['key']}` | {esc(row['en'])} | {esc(row['uk'])} |")
        if item["review"]:
            lines += ["", "Review not applied:", ""]
            lines += [f"- `{row['key']}` — `{row['reason_code']}`: {row['reason']}" for row in item["review"]]
    lines += ["", "Pinned upstream UK and production were not modified.", ""]
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    report = stage(Path(args.manifest), Path(args.cache_root), Path(args.source), Path(args.review), Path(args.output_root))
    audit_report = audit_overlay(Path(args.manifest), Path(args.cache_root), None, Path(args.output_root))
    validation_report = validate_overlay(Path(args.manifest), Path(args.cache_root), None, Path(args.output_root))
    for name, item in report["components"].items():
        item["audit_after"] = audit_report["components"][name]["counts"]
        item["validation"] = validation_report["components"][name]
    report["post_merge_validation_valid"] = validation_report["valid"]
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render(report), encoding="utf-8")
    audit_path = Path(args.audit_report)
    audit_path.write_text(json.dumps(audit_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation_path = Path(args.validation_report)
    validation_path.write_text(json.dumps(validation_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation_path.with_suffix(".md").write_text(render_validation(validation_report), encoding="utf-8")
    validation_path.with_name(f"{validation_path.stem}-findings.md").write_text(render_findings(validation_report), encoding="utf-8")
    print(f"staged {report['candidates_applied']} candidates; review excluded={report['review_not_applied']}")
    print(f"wrote {report['output_root']}, {output}, and {output.with_suffix('.md')}")
    return 0


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("stage-tsv", help="stage a validated manual TSV without overwriting existing UK")
    parser.add_argument("--source", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--manifest", default="manifest.yaml")
    parser.add_argument("--cache-root", default=".cache/upstream")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--report", default="reports/staged-merge-2924.json")
    parser.add_argument("--audit-report", default="reports/audit-merged-2924.json")
    parser.add_argument("--validation-report", default="reports/validation-merged-2924.json")
    parser.set_defaults(handler=run)
