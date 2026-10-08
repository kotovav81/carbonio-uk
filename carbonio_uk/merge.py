"""Non-destructive merge policy: KEEP EXISTING UK."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

import yaml

from .fetch import cache_path
from .formats.catalog import load_catalog
from .manifest import audit_components, load_manifest


_MISSING = object()


def usable(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def merge_keep_existing(english: Any, ukrainian: Any, additions: Any) -> Any:
    """Follow English order, preserving every existing non-empty UK leaf."""
    if isinstance(english, dict):
        uk_map = ukrainian if isinstance(ukrainian, dict) else {}
        add_map = additions if isinstance(additions, dict) else {}
        result = {
            key: merge_keep_existing(value, uk_map.get(key), add_map.get(key))
            for key, value in english.items()
        }
        for key, value in uk_map.items():
            if key not in result:
                result[key] = value
        return result
    if isinstance(english, list):
        uk_list = ukrainian if isinstance(ukrainian, list) else []
        add_list = additions if isinstance(additions, list) else []
        return [
            merge_keep_existing(value, uk_list[index] if index < len(uk_list) else None, add_list[index] if index < len(add_list) else None)
            for index, value in enumerate(english)
        ]
    if ukrainian is not _MISSING and usable(ukrainian):
        return ukrainian
    if usable(additions):
        return additions
    return ukrainian


def merge_flat_keep_existing(english: dict[str, Any], ukrainian: dict[str, Any], additions: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key in english:
        result[key] = ukrainian[key] if key in ukrainian and usable(ukrainian[key]) else additions.get(key, ukrainian.get(key))
    for key, value in ukrainian.items():
        if key not in result:
            result[key] = value
    return result


def merge_with_flat_additions(
    english: Any,
    ukrainian: Any,
    additions: dict[str, Any],
    approved: dict[str, Any],
    prefix: str = "",
) -> Any:
    if isinstance(english, dict):
        uk_map = ukrainian if isinstance(ukrainian, dict) else {}
        result = {}
        for key, value in english.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            child = merge_with_flat_additions(value, uk_map[key] if key in uk_map else _MISSING, additions, approved, path)
            if child is not _MISSING:
                result[key] = child
        for key, value in uk_map.items():
            if key not in result:
                result[key] = value
        return result
    if isinstance(english, list):
        uk_list = ukrainian if isinstance(ukrainian, list) else []
        return [
            merge_with_flat_additions(
                value,
                uk_list[index] if index < len(uk_list) else _MISSING,
                additions,
                approved,
                f"{prefix}[{index}]",
            )
            for index, value in enumerate(english)
        ]
    if prefix in approved:
        return approved[prefix]
    if ukrainian is not _MISSING and usable(ukrainian):
        return ukrainian
    if prefix in additions:
        return additions[prefix]
    return ukrainian


def _approved_changes(path: Path, component: str, commit: str, enabled: bool) -> dict[str, str]:
    if not enabled:
        return {}
    source = path / f"{component}.yaml"
    if not source.exists():
        return {}
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    if data.get("component") != component or data.get("commit") != commit:
        raise ValueError(f"approval does not match component/commit: {source}")
    return {item["key"]: item["approved_uk"] for item in data.get("changes", []) if item.get("status") == "review_approved"}


def merge_component(
    manifest_path: Path,
    cache_root: Path,
    generated_root: Path,
    merged_root: Path,
    approved_root: Path,
    component_name: str,
    review_approved: bool,
) -> dict[str, Any]:
    component = audit_components(load_manifest(manifest_path)).get(component_name)
    if component is None:
        raise ValueError(f"component is not baseline-auditable: {component_name}")
    translation = component["translation"]
    additions_path = generated_root / component_name / component["commit"] / "additions.json"
    additions = json.loads(additions_path.read_text(encoding="utf-8"))["translations"] if additions_path.exists() else {}
    approved = _approved_changes(approved_root, component_name, component["commit"], review_approved)
    en_path = cache_path(cache_root, component_name, component["commit"], "en", translation["english"])
    uk_path = cache_path(cache_root, component_name, component["commit"], "uk", translation["ukrainian"])
    target = merged_root / component_name / Path(translation["ukrainian"]).name
    target.parent.mkdir(parents=True, exist_ok=True)
    if translation["type"] == "json":
        english = json.loads(en_path.read_text(encoding="utf-8"))
        ukrainian = json.loads(uk_path.read_text(encoding="utf-8"))
        merged = merge_with_flat_additions(english, ukrainian, additions, approved)
        target.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        english, en_errors = load_catalog(en_path, "properties")
        ukrainian, uk_errors = load_catalog(uk_path, "properties")
        if en_errors or uk_errors:
            raise ValueError("cannot merge invalid properties")
        merged = merge_flat_keep_existing(english, ukrainian, additions)
        merged.update(approved)
        target.write_text("".join(f"{key}={value}\n" for key, value in merged.items()), encoding="utf-8")
    return {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "component": component_name,
        "commit": component["commit"],
        "policy": "KEEP EXISTING UK",
        "generated_additions": len(additions),
        "review_approved_enabled": review_approved,
        "approved_corrections": len(approved),
        "output": str(target),
        "source_uk_unchanged": True,
    }


def run(args: argparse.Namespace) -> int:
    report = merge_component(
        Path(args.manifest), Path(args.cache_root), Path(args.generated_root), Path(args.merged_root),
        Path(args.approved_root), args.component, args.review_approved,
    )
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"merged {report['component']}: additions={report['generated_additions']} approved={report['approved_corrections']}")
    print(f"source UK unchanged; wrote {report['output']} and {output}")
    return 0


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("merge", help="stage KEEP EXISTING UK merge output")
    parser.add_argument("--manifest", default="manifest.yaml")
    parser.add_argument("--cache-root", default=".cache/upstream")
    parser.add_argument("--generated-root", default="translations/generated")
    parser.add_argument("--merged-root", default="translations/merged")
    parser.add_argument("--approved-root", default="review/approved")
    parser.add_argument("--component", required=True)
    parser.add_argument("--review-approved", action="store_true")
    parser.add_argument("--report", default="reports/merge.json")
    parser.set_defaults(handler=run)
