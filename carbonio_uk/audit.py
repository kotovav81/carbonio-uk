"""Recursive leaf-key audit with English as the structural source of truth."""

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


PLACEHOLDER = re.compile(r"(?:\{\{[^{}]+\}\}|\{[^{}]+\}|%\([^)]+\)[a-zA-Z]|%[0-9$]*[a-zA-Z])")
TAG = re.compile(r"</?(?:strong|br|a|span|em|b|i|p|code|ul|ol|li)\b[^>]*>", re.IGNORECASE)
CYRILLIC_RUSSIAN = re.compile(r"[ыэъёЫЭЪЁ]")
IDENTICAL_ALLOWLIST = {"API", "DNS", "HTTP", "HTTPS", "IMAP", "IP", "POP3", "SMTP", "URL", "WebDAV"}


def _empty(value: Any) -> bool:
    return isinstance(value, str) and not value.strip()


def _tokens(pattern: re.Pattern[str], value: Any) -> Counter[str]:
    return Counter(pattern.findall(value)) if isinstance(value, str) else Counter()


def compare(en: dict[str, Any], ru: dict[str, Any], uk: dict[str, Any]) -> dict[str, Any]:
    en_keys, ru_keys, uk_keys = set(en), set(ru), set(uk)
    missing = sorted(en_keys - uk_keys)
    extra = sorted(uk_keys - en_keys)
    empty = sorted(key for key in en_keys & uk_keys if _empty(uk[key]))
    null = sorted(key for key in en_keys & uk_keys if uk[key] is None)
    invalid = sorted(key for key in en_keys & uk_keys if not isinstance(uk[key], (str, int, float, bool)) and uk[key] is not None)
    translated = sorted(key for key in en_keys & uk_keys if not _empty(uk[key]) and uk[key] is not None)
    identical_allowed = sorted(key for key in translated if uk[key] == en[key] and str(en[key]).strip() in IDENTICAL_ALLOWLIST)
    identical = sorted(key for key in translated if uk[key] == en[key] and key not in identical_allowed)
    placeholder_errors = sorted(
        key for key in translated if _tokens(PLACEHOLDER, en[key]) != _tokens(PLACEHOLDER, uk[key])
    )
    markup_errors = sorted(key for key in translated if _tokens(TAG, en[key]) != _tokens(TAG, uk[key]))
    suspicious_ru = sorted(key for key in translated if isinstance(uk[key], str) and CYRILLIC_RUSSIAN.search(uk[key]))
    return {
        "counts": {
            "en": len(en),
            "ru": len(ru),
            "uk": len(uk),
            "translated": len(translated),
            "missing": len(missing),
            "extra": len(extra),
            "empty": len(empty),
            "null": len(null),
            "invalid": len(invalid),
            "identical_en_uk": len(identical),
            "identical_allowed": len(identical_allowed),
            "placeholder_errors": len(placeholder_errors),
            "markup_errors": len(markup_errors),
            "suspicious_russian_leftovers": len(suspicious_ru),
        },
        "missing": missing,
        "extra": extra,
        "empty": empty,
        "null": null,
        "invalid": invalid,
        "identical_en_uk": identical,
        "identical_allowed": identical_allowed,
        "placeholder_errors": placeholder_errors,
        "markup_errors": markup_errors,
        "suspicious_russian_leftovers": suspicious_ru,
        "reference": {"ru_missing_against_en": sorted(en_keys - ru_keys), "ru_extra_against_en": sorted(ru_keys - en_keys)},
    }


def audit(manifest_path: Path, cache_root: Path, selected: str | None = None, uk_root: Path | None = None) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    components = audit_components(manifest)
    if selected:
        if selected not in components:
            raise ValueError(f"component is not baseline-auditable: {selected}")
        components = {selected: components[selected]}
    output: dict[str, Any] = {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "policy": {"structure": "en", "existing_translation": "uk", "reference_only": "ru"},
        "components": {},
    }
    for name, component in components.items():
        catalogs = {}
        parse_errors = {}
        for language, field in LANGUAGES.items():
            source_path = component["translation"][field]
            staged = uk_root / name / Path(source_path).name if uk_root and language == "uk" else None
            path = staged if staged and staged.exists() else cache_path(cache_root, name, component["commit"], language, source_path)
            if not path.exists():
                raise FileNotFoundError(f"missing cache resource {path}; run `python -m carbonio_uk fetch`")
            catalogs[language], errors = load_catalog(path, component["translation"]["type"])
            if errors:
                parse_errors[language] = errors
        result = compare(catalogs["en"], catalogs["ru"], catalogs["uk"])
        result.update(
            {
                "repository": component["repository"],
                "branch": component["branch"],
                "commit": component["commit"],
                "parse_errors": parse_errors,
            }
        )
        output["components"][name] = result
    return output


def run(args: argparse.Namespace) -> int:
    result = audit(Path(args.manifest), Path(args.cache_root), args.component, Path(args.uk_root) if args.uk_root else None)
    reports = Path(args.report)
    reports.parent.mkdir(parents=True, exist_ok=True)
    reports.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for name, component in result["components"].items():
            count = component["counts"]
            print(f"{name}: EN={count['en']} RU={count['ru']} UK={count['uk']} missing={count['missing']} empty={count['empty']} extra={count['extra']}")
        print(f"wrote {reports}")
    critical = any(
        component["parse_errors"] or component["counts"]["placeholder_errors"] or component["counts"]["markup_errors"]
        for component in result["components"].values()
    )
    return 1 if args.strict and critical else 0


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("audit", help="recursively audit cached locale leaf keys")
    parser.add_argument("--manifest", default="manifest.yaml")
    parser.add_argument("--cache-root", default=".cache/upstream")
    parser.add_argument("--report", default="reports/audit.json")
    parser.add_argument("--component")
    parser.add_argument("--compare-locale", choices=("ru",), default="ru")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--uk-root", help="staged UK overlay root")
    parser.set_defaults(handler=run)
