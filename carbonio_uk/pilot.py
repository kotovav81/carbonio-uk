"""Plan and explicitly execute a 20-row Login/Mail real-translation pilot."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from .fetch import cache_path
from .formats.catalog import load_catalog
from .manifest import audit_components, load_manifest
from .providers.base import TranslationRequest
from .validate import markup_signature, placeholder_signature


PILOT_COMPONENTS = ("login", "mail")
PILOT_SIZE = 20


def _glossary(path: Path) -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {"terms": {}}
    return data.get("terms", {})


def _context(source: str, glossary: dict[str, str]) -> dict[str, str]:
    return {
        term: target
        for term, target in glossary.items()
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", source, flags=re.IGNORECASE)
    }


def make_plan(manifest_path: Path, cache_root: Path, glossary_path: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    components = audit_components(manifest)
    glossary = _glossary(glossary_path)
    rows = []
    for component_name in PILOT_COMPONENTS:
        component = components[component_name]
        translation = component["translation"]
        catalogs = {}
        for language, field in (("en", "english"), ("ru", "russian"), ("uk", "ukrainian")):
            path = cache_path(cache_root, component_name, component["commit"], language, translation[field])
            catalogs[language], errors = load_catalog(path, translation["type"])
            if errors:
                raise ValueError(f"invalid {component_name}:{language} catalog")
        missing = [
            key for key in catalogs["en"]
            if key not in catalogs["uk"] or catalogs["uk"][key] is None
            or (isinstance(catalogs["uk"][key], str) and not catalogs["uk"][key].strip())
        ][: PILOT_SIZE // len(PILOT_COMPONENTS)]
        for key in missing:
            rows.append(
                {
                    "id": hashlib.sha256(f"{component_name}\0{component['commit']}\0{key}".encode()).hexdigest()[:16],
                    "component": component_name,
                    "repository": component["repository"],
                    "commit": component["commit"],
                    "key": key,
                    "en": catalogs["en"][key],
                    "ru_reference": catalogs["ru"].get(key),
                    "glossary_context": _context(str(catalogs["en"][key]), glossary),
                    "status": "planned_not_executed",
                }
            )
    if len(rows) != PILOT_SIZE:
        raise ValueError(f"pilot must contain exactly {PILOT_SIZE} rows, got {len(rows)}")
    return {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "size": PILOT_SIZE,
        "components": list(PILOT_COMPONENTS),
        "policy": {"source": "en", "ru": "display/reference only; never sent to provider", "automatic_merge": False},
        "rows": rows,
    }


def render_plan(plan: dict[str, Any]) -> str:
    sections = ["# Controlled real-translation pilot plan", "", "Status: `planned_not_executed`. Real AI calls: `0`.", ""]
    for index, row in enumerate(plan["rows"], 1):
        context = ", ".join(f"{source} → {target}" for source, target in row["glossary_context"].items()) or "none"
        ru_reference = row["ru_reference"] if row["ru_reference"] is not None else "missing"
        sections.extend(
            [
                f"## {index}. {row['component']}: `{row['key']}`",
                "",
                f"- EN: `{row['en']}`",
                f"- RU reference: `{ru_reference}`",
                f"- Glossary context: {context}",
                f"- Commit: `{row['commit']}`",
                "",
            ]
        )
    return "\n".join(sections)


def write_plan(plan: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False), encoding="utf-8")
    path.with_suffix(".md").write_text(render_plan(plan), encoding="utf-8")


def execute_plan(plan: dict[str, Any], pending_root: Path, provider_name: str, execute: bool, model: str | None) -> dict[str, Any]:
    if provider_name != "openai" or not execute:
        raise ValueError("real pilot execution requires both `--provider openai` and `--execute`")
    if not model:
        raise ValueError("real pilot execution requires explicit `--model`")
    from .providers.openai import OpenAITranslationProvider

    provider = OpenAITranslationProvider(model)
    results = []
    for row in plan["rows"]:
        target = pending_root / row["component"] / f"{row['id']}.yaml"
        if target.exists():
            existing = yaml.safe_load(target.read_text(encoding="utf-8"))
            if existing.get("commit") != row["commit"] or existing.get("key") != row["key"] or existing.get("model") != model:
                raise ValueError(f"pending checkpoint does not match plan/model: {target}")
            results.append(existing)
            continue
        request = TranslationRequest(row["component"], row["key"], str(row["en"]), row["glossary_context"])
        translated = provider.translate(request)
        placeholder_ok = placeholder_signature(row["en"]) == placeholder_signature(translated)
        markup_ok = markup_signature(row["en"]) == markup_signature(translated)
        result = {
            **row,
            "provider": "openai",
            "model": model,
            "uk_candidate": translated,
            "validation": {"non_empty": bool(translated.strip()), "placeholders": placeholder_ok, "markup": markup_ok},
            "status": "pending_review" if translated.strip() and placeholder_ok and markup_ok else "pending_validation_failed",
            "automatic_merge": False,
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), encoding="utf-8")
        results.append(result)
    return {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "executed": True,
        "provider": "openai",
        "model": model,
        "rows": results,
        "valid": sum(all(row["validation"].values()) for row in results),
        "needs_review": len(results),
        "automatic_merge": False,
    }


def render_review(report: dict[str, Any]) -> str:
    lines = ["# Real-translation pilot review", "", f"Model: `{report['model']}`. Automatic merge: `no`.", ""]
    for row in report["rows"]:
        lines.extend(
            [
                f"## {row['component']}: `{row['key']}`",
                "",
                f"- EN: `{row['en']}`",
                f"- RU reference: `{row['ru_reference']}`",
                f"- UK candidate: `{row['uk_candidate']}`",
                f"- Validation: `{row['validation']}`",
                f"- Status: `{row['status']}`",
                "",
            ]
        )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan)
    plan = make_plan(Path(args.manifest), Path(args.cache_root), Path(args.glossary))
    write_plan(plan, plan_path)
    print(f"planned {len(plan['rows'])} rows -> {plan_path} and {plan_path.with_suffix('.md')}")
    if not args.execute:
        print("real AI calls: 0; inspect the plan before using --provider openai --execute --model MODEL")
        return 0
    report = execute_plan(plan, Path(args.pending_root), args.provider, args.execute, args.model)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.with_suffix(".md").write_text(render_review(report), encoding="utf-8")
    print(f"saved {len(report['rows'])} pending rows; automatic merge: no")
    return 0 if report["valid"] == len(report["rows"]) else 1


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("pilot", help="plan or explicitly execute a 20-row Login/Mail pilot")
    parser.add_argument("--manifest", default="manifest.yaml")
    parser.add_argument("--cache-root", default=".cache/upstream")
    parser.add_argument("--glossary", default="glossary/uk.yaml")
    parser.add_argument("--plan", default="reports/real-pilot-plan.yaml")
    parser.add_argument("--pending-root", default="review/pending")
    parser.add_argument("--report", default="reports/real-pilot-review.json")
    parser.add_argument("--provider", choices=("none", "openai"), default="none")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--model", help="required explicitly for OpenAI execution")
    parser.set_defaults(handler=run)
