"""Read-only comparison of a live Carbonio evidence snapshot with pinned catalogs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .fetch import LANGUAGES, cache_path
from .formats.catalog import load_catalog
from .manifest import audit_components, load_manifest


LIVE_DIRS = {
    "shell": "opt/zextras/web/iris/carbonio-shell-ui/i18n",
    "admin_login": "opt/zextras/admin/login-i18n",
    "login": "opt/zextras/web/login-i18n",
    "auth_ui": "opt/zextras/web/iris/carbonio-auth-ui/i18n",
    "mail": "opt/zextras/web/iris/carbonio-mails-ui/i18n",
    "calendar": "opt/zextras/web/iris/carbonio-calendars-ui/i18n",
    "contacts": "opt/zextras/web/iris/carbonio-contacts-ui/i18n",
    "files": "opt/zextras/web/iris/carbonio-files-ui/i18n",
    "search": "opt/zextras/web/iris/carbonio-search-ui/i18n",
    "tasks": "opt/zextras/web/iris/carbonio-tasks-ui/i18n",
    "collaboration": "opt/zextras/web/iris/carbonio-ws-collaboration-ui/i18n",
    "storages": "opt/zextras/web/iris/carbonio-storages-ui/i18n",
}


def compare_catalogs(pinned: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    common = pinned.keys() & live.keys()
    missing = sorted(pinned.keys() - live.keys())
    extra = sorted(live.keys() - pinned.keys())
    changed = sorted(key for key in common if pinned[key] != live[key])
    if not missing and not extra and not changed:
        classification = "exact"
    elif missing and not extra:
        classification = "likely_live_older"
    elif extra and not missing:
        classification = "likely_live_newer"
    elif missing and extra:
        classification = "diverged_keyset"
    else:
        classification = "content_drift"
    return {
        "pinned_leaf_count": len(pinned), "live_leaf_count": len(live),
        "missing_in_live": missing, "extra_in_live": extra,
        "changed_values": changed, "classification": classification,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report(manifest_path: Path, cache_root: Path, snapshot: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    result: dict[str, Any] = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": str(snapshot), "comparison_basis": "manifest-pinned upstream commits",
        "components": {},
    }
    for name, component in audit_components(manifest).items():
        entry: dict[str, Any] = {
            "repository": component["repository"], "branch": component["branch"],
            "commit": component["commit"], "live_path": LIVE_DIRS.get(name), "locales": {},
        }
        if name not in LIVE_DIRS:
            entry.update(status="not_in_snapshot", reason="no matching packaged resource")
            result["components"][name] = entry
            continue
        translation = component["translation"]
        for language, field in LANGUAGES.items():
            pinned_path = cache_path(cache_root, name, component["commit"], language, translation[field])
            live_path = snapshot / LIVE_DIRS[name] / f"{language}.json"
            if not pinned_path.is_file() or not live_path.is_file():
                entry["locales"][language] = {"status": "missing_file", "pinned": str(pinned_path), "live": str(live_path)}
                continue
            pinned, pinned_errors = load_catalog(pinned_path, translation["type"])
            live, live_errors = load_catalog(live_path, "json")
            comparison = compare_catalogs(pinned, live)
            comparison.update(status="compared", pinned_path=str(pinned_path), live_path=str(live_path),
                              pinned_sha256=_sha256(pinned_path), live_sha256=_sha256(live_path),
                              parse_errors={"pinned": pinned_errors, "live": live_errors})
            entry["locales"][language] = comparison
        entry["status"] = "compared"
        result["components"][name] = entry
    result["admin_console"] = {
        "status": "active/blocked", "baseline_audit": False,
        "reason": "translation repository unavailable; legacy opt/zextras/admin/iris is not the new Admin Console",
    }
    result["outside_baseline"] = [
        "opt/zextras/admin/iris (legacy Admin UI)", "opt/zextras/common/coolwsd",
        "opt/zextras/common/etc/mongooseim", "JavaScript plugin bundles", "English locale variants",
    ]
    return result


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Live snapshot vs pinned upstream", "", f"Checked: `{report['checked_at']}`", "",
             "The comparison is read-only. Version labels are inferences from locale keysets; they do not identify an installed Git commit.", "",
             "Cell format: `classification (missing/extra/changed)`.", "",
             "| Component | EN | RU | UK | Note |", "|---|---:|---:|---:|---|"]
    for name, entry in report["components"].items():
        cells = []
        for language in ("en", "ru", "uk"):
            item = entry.get("locales", {}).get(language)
            cells.append((f"{item['classification']} ({len(item['missing_in_live'])}/"
                          f"{len(item['extra_in_live'])}/{len(item['changed_values'])})")
                         if item and item.get("status") == "compared" else "not available")
        lines.append(f"| `{name}` | {cells[0]} | {cells[1]} | {cells[2]} | {entry.get('reason', '')} |")
    lines += ["", "## Admin Console", "", report["admin_console"]["reason"] + ". It remains `active/blocked` and outside the baseline audit.",
              "", "## Snapshot resources outside the baseline", ""]
    lines += [f"- {value}" for value in report["outside_baseline"]]
    lines += ["", "Full missing, extra, and changed leaf-key lists are in `reports/live-vs-upstream.json`.", ""]
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    report = build_report(Path(args.manifest), Path(args.cache_root), Path(args.snapshot))
    json_path, md_path = Path(args.json_report), Path(args.markdown_report)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {json_path} and {md_path}")
    return 0


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("live-compare", help="compare a read-only live snapshot with pinned upstream")
    parser.add_argument("--snapshot", default="translations/live-carbonio-20261008")
    parser.add_argument("--manifest", default="manifest.yaml")
    parser.add_argument("--cache-root", default=".cache/upstream")
    parser.add_argument("--json-report", default="reports/live-vs-upstream.json")
    parser.add_argument("--markdown-report", default="reports/live-vs-upstream.md")
    parser.set_defaults(handler=run)
