"""Build a deterministic, non-installing /opt/zextras localization overlay."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import tarfile
from typing import Any

from .formats.catalog import load_catalog
from .live_compare import LIVE_DIRS
from .manifest import audit_components, load_manifest


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_overlay(manifest_path: Path, merged_root: Path, snapshot: Path, output_dir: Path) -> dict[str, Any]:
    components = audit_components(load_manifest(manifest_path))
    rootfs = output_dir / "rootfs"
    mappings = []
    payload: list[tuple[Path, str]] = []
    excluded = []
    for name, component in components.items():
        translation = component["translation"]
        source = merged_root / name / Path(translation["ukrainian"]).name
        if name not in LIVE_DIRS:
            values, errors = load_catalog(source, translation["type"])
            excluded.append({
                "component": name, "source": str(source), "reason": "no confirmed live /opt/zextras destination; not in JSON-only aggregator payload",
                "validation": {"valid": not errors, "leaf_count": len(values), "errors": errors},
            })
            continue
        relative = f"{LIVE_DIRS[name]}/uk.json"
        live = snapshot / relative
        if not live.is_file():
            raise ValueError(f"live destination structure not confirmed: {live}")
        values, errors = load_catalog(source, "json")
        if errors:
            raise ValueError(f"invalid staged JSON {source}: {errors}")
        target = rootfs / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        target.chmod(0o644)
        payload.append((target, relative))
        mappings.append({
            "component": name, "source": str(source), "destination": f"/{relative}",
            "live_snapshot_path": str(live), "live_path_exists": True,
            "format": "json", "leaf_count": len(values), "sha256": _sha(target),
            "repository": component["repository"], "commit": component["commit"],
        })
    expected = {relative for _, relative in payload}
    actual = {str(path.relative_to(rootfs)) for path in rootfs.rglob("*") if path.is_file()}
    if actual != expected:
        raise ValueError(f"overlay contains unexpected paths: {sorted(actual ^ expected)}")

    package_manifest = {
        "schema": 1, "name": "carbonio-uk-overlay", "version": "2924",
        "install_root": "/", "policy": "staging-only; no automatic installation",
        "files": [{"path": f"/{relative}", "sha256": _sha(path), "size": path.stat().st_size} for path, relative in sorted(payload, key=lambda item: item[1])],
        "excluded": excluded,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = output_dir / "MANIFEST.json"
    manifest_file.write_text(json.dumps(package_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sums_file = output_dir / "SHA256SUMS"
    sums_file.write_text("".join(f"{item['sha256']}  rootfs/{item['path'].lstrip('/')}\n" for item in package_manifest["files"]), encoding="utf-8")
    archive = output_dir / "carbonio-uk-overlay-2924.tar"
    with tarfile.open(archive, "w", format=tarfile.PAX_FORMAT) as tar:
        for path, relative in sorted(payload, key=lambda item: item[1]):
            data = path.read_bytes()
            info = tarfile.TarInfo(relative)
            info.size = len(data); info.mode = 0o644; info.uid = 0; info.gid = 0
            info.uname = "root"; info.gname = "root"; info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    return {
        "schema": 1, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "artifact_type": "reproducible filesystem overlay (tar)", "installed": False,
        "artifact": str(archive), "artifact_sha256": _sha(archive), "artifact_size": archive.stat().st_size,
        "rootfs": str(rootfs), "manifest": str(manifest_file), "sha256sums": str(sums_file),
        "payload_files": len(payload), "path_structure_matches_live_snapshot": True,
        "mappings": mappings, "excluded": excluded,
        "backup_plan": [
            "Resolve owning deb/rpm package for every destination and record installed versions.",
            "Before installation, archive exactly the destination UK files with ownership, modes, SHA-256, and package metadata.",
            "Store the backup outside /opt/zextras and verify its checksum and listing before proceeding.",
            "Install only through an approved package/staging mechanism; do not copy files manually.",
            "For rollback, stop only the documented affected services, restore the recorded package/version or verified backup, then restart and smoke-test.",
        ],
        "gates_before_install": [
            "Complete focused linguistic QA for high-use Mail and Calendar strings.",
            "Resolve or explicitly accept the 20 review rows and existing auth_ui markup mismatch.",
            "Test package ownership/conflicts and UI loading in a disposable Carbonio environment.",
            "Verify language switching, fallback, Login, Mail, Calendar, and Contacts.",
        ],
    }


def render(report: dict[str, Any]) -> str:
    lines = ["# Package staging overlay 2924", "", f"Generated: `{report['generated_at']}`", "",
             f"Artifact: `{report['artifact']}`", f"SHA-256: `{report['artifact_sha256']}`", "",
             f"Payload files: `{report['payload_files']}`. Installed: `no`. Live path structure match: `yes`.", "",
             "| Component | Destination | Leaves | SHA-256 |", "|---|---|---:|---|"]
    for row in report["mappings"]:
        lines.append(f"| `{row['component']}` | `{row['destination']}` | {row['leaf_count']} | `{row['sha256']}` |")
    lines += ["", "## Excluded", ""]
    for row in report["excluded"]:
        lines.append(f"- `{row['component']}`: {row['reason']}; validation valid=`{str(row['validation']['valid']).lower()}`.")
    lines += ["", "## Backup and rollback plan", ""] + [f"{i}. {value}" for i, value in enumerate(report["backup_plan"], 1)]
    lines += ["", "## Gates before installation", ""] + [f"- {value}" for value in report["gates_before_install"]]
    lines += ["", "No package manager, service, production file, or `/opt/zextras` path was modified.", ""]
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    report = build_overlay(Path(args.manifest), Path(args.merged_root), Path(args.snapshot), Path(args.output_dir))
    output = Path(args.report); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render(report), encoding="utf-8")
    print(f"built {report['artifact']} ({report['payload_files']} files), sha256={report['artifact_sha256']}")
    print(f"installed: no; wrote {output} and {output.with_suffix('.md')}")
    return 0


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("package-overlay", help="build a deterministic non-installing /opt/zextras overlay")
    parser.add_argument("--merged-root", default="translations/uk")
    parser.add_argument("--snapshot", default="translations/live-carbonio-20261008")
    parser.add_argument("--manifest", default="manifest.yaml")
    parser.add_argument("--output-dir", default="artifacts/package-staging-2924")
    parser.add_argument("--report", default="reports/package-staging-2924.json")
    parser.set_defaults(handler=run)
