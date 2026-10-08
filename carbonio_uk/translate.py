"""Translation planning. Dry-run never calls a provider or writes translations."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import hashlib
import math
from pathlib import Path
from typing import Any

from .fetch import cache_path
from .formats.catalog import load_catalog
from .manifest import audit_components, load_manifest
from .providers.base import TranslationRequest
from .providers.mock import MockTranslationProvider


PROMPT_VERSION = "mock-pipeline-v1"


def plan(manifest_path: Path, cache_root: Path, batch_size: int, selected: str | None = None) -> dict[str, Any]:
    if batch_size < 1:
        raise ValueError("batch size must be positive")
    manifest = load_manifest(manifest_path)
    components = audit_components(manifest)
    if selected:
        if selected not in components:
            raise ValueError(f"component is not baseline-auditable: {selected}")
        components = {selected: components[selected]}
    results = {}
    for name, component in components.items():
        translation = component["translation"]
        kind = translation["type"]
        en_path = cache_path(cache_root, name, component["commit"], "en", translation["english"])
        uk_path = cache_path(cache_root, name, component["commit"], "uk", translation["ukrainian"])
        en, en_errors = load_catalog(en_path, kind)
        uk, uk_errors = load_catalog(uk_path, kind)
        if en_errors or uk_errors:
            raise ValueError(f"cannot plan {name}: invalid catalog")
        keys = [key for key in en if key not in uk or uk[key] is None or (isinstance(uk[key], str) and not uk[key].strip())]
        characters = sum(len(str(en[key])) for key in keys)
        results[name] = {
            "repository": component["repository"],
            "commit": component["commit"],
            "missing_or_empty": len(keys),
            "batches": math.ceil(len(keys) / batch_size) if keys else 0,
            "estimated_source_characters": characters,
            "keys": keys,
            "would_write": f"translations/generated/{name}/{Path(translation['ukrainian']).name}",
        }
    return {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "dry_run": True,
        "provider_called": False,
        "source_language": "en",
        "reference_language": "ru (not sent as translation source)",
        "policy": "KEEP EXISTING UK",
        "batch_size": batch_size,
        "components": results,
        "totals": {
            "missing_or_empty": sum(item["missing_or_empty"] for item in results.values()),
            "batches": sum(item["batches"] for item in results.values()),
            "estimated_source_characters": sum(item["estimated_source_characters"] for item in results.values()),
        },
    }


def _glossary(path: Path) -> tuple[dict[str, str], str]:
    import yaml

    raw = path.read_bytes() if path.exists() else b"terms: {}\n"
    data = yaml.safe_load(raw.decode("utf-8")) or {}
    return data.get("terms", {}), hashlib.sha256(raw).hexdigest()


def _item_digest(component: str, key: str, source: str, glossary_version: str) -> str:
    material = "\0".join((component, key, source, glossary_version, PROMPT_VERSION))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def translate_mock(
    manifest_path: Path,
    cache_root: Path,
    generated_root: Path,
    translation_cache: Path,
    checkpoint_root: Path,
    glossary_path: Path,
    batch_size: int,
    selected: str,
    limit: int | None,
) -> dict[str, Any]:
    if batch_size < 1 or (limit is not None and limit < 1):
        raise ValueError("batch size and limit must be positive")
    manifest = load_manifest(manifest_path)
    components = audit_components(manifest)
    if selected not in components:
        raise ValueError(f"component is not baseline-auditable: {selected}")
    component = components[selected]
    translation = component["translation"]
    en, en_errors = load_catalog(
        cache_path(cache_root, selected, component["commit"], "en", translation["english"]), translation["type"]
    )
    uk, uk_errors = load_catalog(
        cache_path(cache_root, selected, component["commit"], "uk", translation["ukrainian"]), translation["type"]
    )
    if en_errors or uk_errors:
        raise ValueError(f"cannot translate {selected}: invalid catalog")
    keys = [key for key in en if key not in uk or uk[key] is None or (isinstance(uk[key], str) and not uk[key].strip())]
    if limit is not None:
        keys = keys[:limit]
    glossary, glossary_version = _glossary(glossary_path)
    provider = MockTranslationProvider()
    additions: dict[str, str] = {}
    batches = []
    cache_hits = 0
    provider_calls = 0
    for offset in range(0, len(keys), batch_size):
        batch_keys = keys[offset : offset + batch_size]
        item_hashes = [_item_digest(selected, key, str(en[key]), glossary_version) for key in batch_keys]
        batch_hash = hashlib.sha256("\n".join(item_hashes).encode("ascii")).hexdigest()
        checkpoint = checkpoint_root / selected / f"{batch_hash}.json"
        batch_values = {}
        for key, digest in zip(batch_keys, item_hashes):
            cache_file = translation_cache / f"{digest}.json"
            if cache_file.exists():
                value = json.loads(cache_file.read_text(encoding="utf-8"))["translation"]
                cache_hits += 1
            else:
                value = provider.translate(TranslationRequest(selected, key, str(en[key]), glossary))
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(
                    json.dumps({"sha256": digest, "provider": "mock", "translation": value}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                provider_calls += 1
            additions[key] = value
            batch_values[key] = value
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(
            json.dumps(
                {"status": "complete", "batch_sha256": batch_hash, "item_sha256": item_hashes, "keys": batch_keys},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        batches.append({"sha256": batch_hash, "keys": batch_keys, "checkpoint": str(checkpoint)})
    target = generated_root / selected / component["commit"] / "additions.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "schema": 1,
                "component": selected,
                "commit": component["commit"],
                "provider": "mock",
                "prompt_version": PROMPT_VERSION,
                "glossary_sha256": glossary_version,
                "policy": "EN source; RU not supplied; KEEP EXISTING UK at merge",
                "translations": additions,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "dry_run": False,
        "provider": "mock",
        "real_ai": False,
        "component": selected,
        "commit": component["commit"],
        "translated": len(additions),
        "provider_calls": provider_calls,
        "cache_hits": cache_hits,
        "batches": batches,
        "output": str(target),
    }


def run(args: argparse.Namespace) -> int:
    if args.dry_run:
        report = plan(Path(args.manifest), Path(args.cache_root), args.batch_size, args.component)
    else:
        if args.provider != "mock":
            raise SystemExit("real AI providers are disabled")
        if not args.component:
            raise SystemExit("controlled mock translation requires --component")
        report = translate_mock(
            Path(args.manifest), Path(args.cache_root), Path(args.generated_root), Path(args.translation_cache),
            Path(args.checkpoint_root), Path(args.glossary), args.batch_size, args.component, args.limit,
        )
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.dry_run:
        for name, item in report["components"].items():
            print(f"{name}: missing/empty={item['missing_or_empty']} batches={item['batches']} chars={item['estimated_source_characters']}")
        print(f"provider called: no; policy: {report['policy']}; wrote {output}")
    else:
        print(f"mock translated={report['translated']} provider_calls={report['provider_calls']} cache_hits={report['cache_hits']}")
        print(f"checkpoints={len(report['batches'])}; wrote {report['output']} and {output}")
    return 0


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("translate", help="plan translation without changing existing UK")
    parser.add_argument("--manifest", default="manifest.yaml")
    parser.add_argument("--cache-root", default=".cache/upstream")
    parser.add_argument("--report", default="reports/translate-dry-run.json")
    parser.add_argument("--component")
    parser.add_argument("--provider", choices=("mock",), default="mock")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--generated-root", default="translations/generated")
    parser.add_argument("--translation-cache", default=".cache/translation")
    parser.add_argument("--checkpoint-root", default=".cache/checkpoints")
    parser.add_argument("--glossary", default="glossary/uk.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(handler=run)
