"""Compose controlled-pipeline evidence from existing machine reports."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def compose(audit_path: Path, translation_path: Path, merge_path: Path, validation_path: Path, replay_path: Path | None = None) -> dict[str, Any]:
    audit = _load(audit_path)
    translation = _load(translation_path)
    merge = _load(merge_path)
    validation = _load(validation_path)
    component = translation["component"]
    additions = _load(Path(translation["output"]))["translations"]
    replay = _load(replay_path) if replay_path and replay_path.exists() else None
    return {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "pipeline": ["audit", "translate:mock", "merge:KEEP EXISTING UK", "validate", "report"],
        "real_ai": False,
        "component": component,
        "commit": translation["commit"],
        "audit_before": audit["components"][component]["counts"],
        "translation": {
            "translated": translation["translated"],
            "provider_calls": translation["provider_calls"],
            "cache_hits": translation["cache_hits"],
            "batches": len(translation["batches"]),
            "cache_replay": {
                "provider_calls": replay["provider_calls"], "cache_hits": replay["cache_hits"]
            } if replay else None,
            "sample": [{"key": key, "mock_uk": value} for key, value in additions.items()],
        },
        "merge": merge,
        "validation_after": validation["components"][component],
        "admin_console": "active/blocked; excluded because public translation repository is unavailable",
        "aggregator_admin_console_coverage": False,
    }


def render_markdown(report: dict[str, Any]) -> str:
    after = report["validation_after"]
    remaining_required = len(after["missing"]) + len(after["empty"]) + len(after["null"])
    sample_rows = "\n".join(f"| `{item['key']}` | {item['mock_uk']} |" for item in report["translation"]["sample"])
    replay = report["translation"]["cache_replay"] or {"provider_calls": "n/a", "cache_hits": "n/a"}
    return f"""# Controlled mock translation pipeline

Generated: `{report['generated_at']}`  
Component: `{report['component']}`  
Commit: `{report['commit']}`  
Real AI used: `no`

## Flow

`audit → translate mock → merge KEEP EXISTING UK → validate → report`

- Mock translations generated: `{report['translation']['translated']}`
- Provider calls: `{report['translation']['provider_calls']}`
- Cache hits: `{report['translation']['cache_hits']}`
- Completed batch checkpoints: `{report['translation']['batches']}`
- Cache replay provider calls: `{replay['provider_calls']}`
- Cache replay hits: `{replay['cache_hits']}`
- Approved review corrections applied: `{report['merge']['approved_corrections']}`
- Remaining missing/empty/null keys after staged merge: `{remaining_required}`
- Placeholder errors after staged merge: `{len(after['placeholder_errors'])}`
- Markup errors after staged merge: `{len(after['markup_errors'])}`

The source UK catalog remained unchanged. Admin Console remains `active/blocked`.
`carbonio-webui-i18n` packages legacy admin translations and does not cover the
new `carbonio-admin-console-ui` translation source.

## Generated mock sample

| Leaf key | Mock UK staging value |
|---|---|
{sample_rows}
"""


def run(args: argparse.Namespace) -> int:
    report = compose(
        Path(args.audit), Path(args.translation), Path(args.merge), Path(args.validation),
        Path(args.cache_replay) if args.cache_replay else None,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = output.with_suffix(".md")
    markdown.write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {output} and {markdown}")
    return 0


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("report", help="compose controlled mock-pipeline report")
    parser.add_argument("--audit", default="reports/audit.json")
    parser.add_argument("--translation", default="reports/mock-translation.json")
    parser.add_argument("--merge", default="reports/mock-merge.json")
    parser.add_argument("--validation", default="reports/mock-validation.json")
    parser.add_argument("--cache-replay", default="reports/mock-translation-cache-replay.json")
    parser.add_argument("--output", default="reports/mock-pipeline.json")
    parser.set_defaults(handler=run)
