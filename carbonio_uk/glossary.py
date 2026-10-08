"""Extract candidate EN→UK terminology from existing Ukrainian catalogs."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import json
from pathlib import Path
import re
from typing import Any

import yaml

from .fetch import cache_path
from .formats.catalog import load_catalog
from .manifest import audit_components, load_manifest
from .validate import markup_signature, placeholder_signature


UKRAINIAN = re.compile(r"[іїєґІЇЄҐ]")
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")


def extract(manifest_path: Path, cache_root: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    candidates: dict[str, Counter[str]] = defaultdict(Counter)
    provenance: dict[tuple[str, str], set[str]] = defaultdict(set)
    for name, component in audit_components(manifest).items():
        kind = component["translation"]["type"]
        en_path = cache_path(cache_root, name, component["commit"], "en", component["translation"]["english"])
        uk_path = cache_path(cache_root, name, component["commit"], "uk", component["translation"]["ukrainian"])
        en, _ = load_catalog(en_path, kind)
        uk, _ = load_catalog(uk_path, kind)
        for key in set(en) & set(uk):
            source, target = en[key], uk[key]
            if not isinstance(source, str) or not isinstance(target, str):
                continue
            source, target = source.strip(), target.strip()
            if not source or not target or source == target or len(source) > 60 or len(target) > 80:
                continue
            if not (1 <= len(WORD.findall(source)) <= 4) or not UKRAINIAN.search(target):
                continue
            if placeholder_signature(source) or placeholder_signature(target) or markup_signature(source) or markup_signature(target):
                continue
            candidates[source][target] += 1
            provenance[(source, target)].add(f"{name}:{key}")
    terms = {}
    conflicts = {}
    details = {}
    for source in sorted(candidates, key=str.casefold):
        ranked = candidates[source].most_common()
        selected, count = ranked[0]
        terms[source] = selected
        details[source] = {"uk": selected, "occurrences": count, "sources": sorted(provenance[(source, selected)])}
        if len(ranked) > 1:
            conflicts[source] = [
                {"uk": target, "occurrences": occurrences, "sources": sorted(provenance[(source, target)])}
                for target, occurrences in ranked
            ]
    return {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "method": "short EN/UK pairs from existing non-empty UK; placeholders and markup excluded",
        "terms": terms,
        "details": details,
        "conflicts": conflicts,
    }


def run(args: argparse.Namespace) -> int:
    report = extract(Path(args.manifest), Path(args.cache_root))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump({"terms": report["terms"]}, allow_unicode=True, sort_keys=True), encoding="utf-8")
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"extracted {len(report['terms'])} terms; conflicts={len(report['conflicts'])}")
    print(f"wrote {output} and {report_path}")
    return 0


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("glossary", help="extract glossary candidates from existing UK")
    parser.add_argument("--manifest", default="manifest.yaml")
    parser.add_argument("--cache-root", default=".cache/upstream")
    parser.add_argument("--output", default="reports/glossary-extracted.yaml")
    parser.add_argument("--report", default="reports/glossary.json")
    parser.set_defaults(handler=run)
