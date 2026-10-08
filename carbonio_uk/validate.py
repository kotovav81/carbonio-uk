"""Structural and content validation for pinned translation catalogs."""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
from pathlib import Path
import re
from typing import Any

from .fetch import LANGUAGES, cache_path
from .formats.catalog import load_catalog
from .manifest import audit_components, load_manifest


INTERPOLATION = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
BRACE = re.compile(r"(?<!\{)\{\s*([^{}]+?)\s*\}(?!\})")
PRINTF = re.compile(r"%\(([^)]+)\)[a-zA-Z]|%([0-9]+\$)?([a-zA-Z])")
# Only treat known UI markup elements as markup.  Carbonio also uses literal
# angle-bracket placeholders such as ``<No Name>``; interpreting those as an
# HTML tag would reject a valid translated placeholder.
MARKUP = re.compile(r"<(/?)(strong|br|a|span|em|b|i|p|code|ul|ol|li)\b[^>]*>", re.IGNORECASE)


def placeholder_signature(value: Any) -> Counter[str]:
    if not isinstance(value, str):
        return Counter()
    found = [f"i18n:{item.strip()}" for item in INTERPOLATION.findall(value)]
    found.extend(f"brace:{item.strip()}" for item in BRACE.findall(value))
    for match in PRINTF.finditer(value):
        found.append(f"printf:{match.group(0)}")
    return Counter(found)


def interpolation_signature(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return re.findall(r"\{\{[^{}]+\}\}", value)


def markup_signature(value: Any) -> Counter[tuple[str, str]]:
    if not isinstance(value, str):
        return Counter()
    return Counter((closing, name.lower()) for closing, name in MARKUP.findall(value))


def _json_with_duplicates(path: Path) -> tuple[list[str], list[str]]:
    duplicates: list[str] = []

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                duplicates.append(key)
            result[key] = value
        return result

    try:
        with path.open(encoding="utf-8") as stream:
            json.load(stream, object_pairs_hook=hook)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return [], [str(error)]
    return sorted(set(duplicates)), []


def validate_component(name: str, component: dict[str, Any], cache_root: Path, uk_root: Path | None = None) -> dict[str, Any]:
    catalogs: dict[str, dict[str, Any]] = {}
    syntax_errors: dict[str, list[str]] = {}
    duplicate_keys: dict[str, list[str]] = {}
    paths: dict[str, str] = {}
    for language, field in LANGUAGES.items():
        staged = uk_root / name / Path(component["translation"][field]).name if uk_root and language == "uk" else None
        path = staged if staged and staged.exists() else cache_path(cache_root, name, component["commit"], language, component["translation"][field])
        paths[language] = str(path)
        catalogs[language], errors = load_catalog(path, component["translation"]["type"])
        if errors:
            syntax_errors[language] = errors
        if component["translation"]["type"] == "json":
            duplicates, json_errors = _json_with_duplicates(path)
            if duplicates:
                duplicate_keys[language] = duplicates
            if json_errors:
                syntax_errors.setdefault(language, []).extend(json_errors)
        else:
            duplicates = [error for error in errors if "duplicate key" in error]
            if duplicates:
                duplicate_keys[language] = duplicates

    en, ru, uk = catalogs["en"], catalogs["ru"], catalogs["uk"]
    common = sorted(set(en) & set(uk))
    missing = sorted(set(en) - set(uk))
    extra = sorted(set(uk) - set(en))
    empty = sorted(key for key in common if isinstance(uk[key], str) and not uk[key].strip())
    null = sorted(key for key in common if uk[key] is None)
    invalid = sorted(key for key in common if uk[key] is not None and not isinstance(uk[key], (str, int, float, bool)))
    comparable = [key for key in common if key not in empty and key not in null and key not in invalid]
    placeholder_errors = sorted(key for key in comparable if placeholder_signature(en[key]) != placeholder_signature(uk[key]))
    interpolation_format = sorted(
        key
        for key in comparable
        if placeholder_signature(en[key]) == placeholder_signature(uk[key])
        and interpolation_signature(en[key]) != interpolation_signature(uk[key])
    )
    markup_errors = sorted(key for key in comparable if markup_signature(en[key]) != markup_signature(uk[key]))
    control_characters = sorted(
        key for key in common if isinstance(uk[key], str) and any(ord(char) < 32 and char not in "\n\r\t" for char in uk[key])
    )
    critical_count = sum(
        len(value)
        for value in (missing, empty, null, invalid, placeholder_errors, markup_errors, control_characters)
    ) + sum(len(value) for value in syntax_errors.values()) + sum(len(value) for value in duplicate_keys.values())
    findings = []
    for kind, keys in (
        ("placeholder_error", placeholder_errors),
        ("interpolation_format_warning", interpolation_format),
        ("markup_error", markup_errors),
    ):
        for key in keys:
            if kind == "placeholder_error":
                reason = f"placeholder identifiers differ: EN={dict(placeholder_signature(en[key]))}, UK={dict(placeholder_signature(uk[key]))}"
            elif kind == "interpolation_format_warning":
                reason = "raw {{ ... }} spacing differs, but normalized placeholder identifiers are equal"
            else:
                reason = f"markup tags differ: EN={dict(markup_signature(en[key]))}, UK={dict(markup_signature(uk[key]))}"
            ru_value = ru.get(key)
            if placeholder_signature(en.get(key)) != placeholder_signature(ru_value):
                reason += "; RU reference placeholder identifiers differ from EN"
            if isinstance(ru_value, str) and ru_value.count("{") != ru_value.count("}"):
                reason += "; RU reference has unbalanced brace delimiters"
            findings.append({"kind": kind, "key": key, "en": en.get(key), "ru": ru_value, "uk": uk.get(key), "reason": reason})
    return {
        "repository": component["repository"],
        "branch": component["branch"],
        "commit": component["commit"],
        "paths": paths,
        "counts": {"en": len(en), "ru": len(ru), "uk": len(uk), "critical": critical_count},
        "syntax_errors": syntax_errors,
        "duplicate_keys": duplicate_keys,
        "missing": missing,
        "extra": extra,
        "empty": empty,
        "null": null,
        "invalid_types": invalid,
        "placeholder_errors": placeholder_errors,
        "interpolation_format_warnings": interpolation_format,
        "markup_errors": markup_errors,
        "control_characters": control_characters,
        "findings": findings,
        "reference": {"ru_missing": sorted(set(en) - set(ru)), "ru_extra": sorted(set(ru) - set(en))},
    }


def validate(manifest_path: Path, cache_root: Path, selected: str | None = None, uk_root: Path | None = None) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    components = audit_components(manifest)
    if selected:
        if selected not in components:
            raise ValueError(f"component is not baseline-auditable: {selected}")
        components = {selected: components[selected]}
    results = {name: validate_component(name, component, cache_root, uk_root) for name, component in components.items()}
    return {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "policy": {"structure": "en", "existing_translation": "uk", "reference_only": "ru"},
        "valid": all(result["counts"]["critical"] == 0 for result in results.values()),
        "components": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for name, item in report["components"].items():
        rows.append(
            f"| {name} | {item['counts']['en']} | {item['counts']['uk']} | {len(item['missing'])} | "
            f"{len(item['empty'])} | {len(item['placeholder_errors'])} | {len(item['interpolation_format_warnings'])} | "
            f"{len(item['markup_errors'])} | {item['counts']['critical']} |"
        )
    return f"""# Validation report

Generated: `{report['generated_at']}`. Valid: `{'yes' if report['valid'] else 'no'}`.

| Component | EN | UK | Missing | Empty | Placeholder | Interpolation warning | Markup | Critical |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

EN defines required keys, existing non-empty UK is preserved, and RU is reference-only.
"""


def render_findings(report: dict[str, Any]) -> str:
    sections = []
    for component, item in report["components"].items():
        for finding in item["findings"]:
            sections.append(
                f"## {component}: `{finding['key']}`\n\n"
                f"- Kind: `{finding['kind']}`\n"
                f"- EN: `{finding['en']}`\n"
                f"- RU: `{finding['ru']}`\n"
                f"- UK: `{finding['uk']}`\n"
                f"- Reason: {finding['reason']}\n"
            )
    return "# Placeholder, interpolation, and markup findings\n\n" + "\n".join(sections)


def run(args: argparse.Namespace) -> int:
    report = validate(Path(args.manifest), Path(args.cache_root), args.component, Path(args.uk_root) if args.uk_root else None)
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = output.with_suffix(".md")
    markdown.write_text(render_markdown(report), encoding="utf-8")
    findings_name = "validation-findings.md" if output.stem == "validation" else f"{output.stem}-findings.md"
    findings_path = output.with_name(findings_name)
    findings_path.write_text(render_findings(report), encoding="utf-8")
    for name, result in report["components"].items():
        print(f"{name}: critical={result['counts']['critical']} missing={len(result['missing'])} placeholder={len(result['placeholder_errors'])} interpolation={len(result['interpolation_format_warnings'])} markup={len(result['markup_errors'])}")
    print(f"wrote {output}, {markdown}, and {findings_path}")
    return 0 if report["valid"] else 1


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("validate", help="validate cached translation catalogs")
    parser.add_argument("--manifest", default="manifest.yaml")
    parser.add_argument("--cache-root", default=".cache/upstream")
    parser.add_argument("--report", default="reports/validation.json")
    parser.add_argument("--component")
    parser.add_argument("--uk-root", help="staged UK overlay root, e.g. translations/merged")
    parser.set_defaults(handler=run)
