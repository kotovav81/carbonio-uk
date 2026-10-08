"""Explicit approval workflow for proposed human-review corrections."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import yaml


def approve(proposed_root: Path, approved_root: Path, component: str, key: str) -> Path:
    source = proposed_root / f"{component}.yaml"
    if not source.exists():
        raise FileNotFoundError(f"proposal sidecar not found: {source}")
    proposal = yaml.safe_load(source.read_text(encoding="utf-8"))
    matches = [change for change in proposal.get("changes", []) if change.get("key") == key]
    if len(matches) != 1:
        raise ValueError(f"expected one proposed change for {component}:{key}")
    change = matches[0]
    approval = {
        "schema": 1,
        "component": component,
        "repository": proposal.get("repository"),
        "commit": proposal.get("commit"),
        "approved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "proposal_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "changes": [
            {
                "key": key,
                "existing_uk": change["existing_uk"],
                "approved_uk": change["proposed_uk"],
                "status": "review_approved",
            }
        ],
    }
    target = approved_root / f"{component}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(approval, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return target


def run_apply(args: argparse.Namespace) -> int:
    target = approve(Path(args.proposed_root), Path(args.approved_root), args.component, args.key)
    print(f"approved exactly one proposal -> {target}")
    print("existing UK was not modified; use `merge --review-approved` to stage it")
    return 0


def decide(pending_root: Path, decisions_root: Path, component: str, key: str, decision: str, note: str | None) -> Path:
    candidates = []
    for path in (pending_root / component).glob("*.yaml"):
        row = yaml.safe_load(path.read_text(encoding="utf-8"))
        if row.get("key") == key:
            candidates.append((path, row))
    if len(candidates) != 1:
        raise ValueError(f"expected one pending row for {component}:{key}, found {len(candidates)}")
    pending_path, row = candidates[0]
    record = {
        "schema": 1,
        "component": component,
        "key": key,
        "commit": row["commit"],
        "pending_sha256": hashlib.sha256(pending_path.read_bytes()).hexdigest(),
        "decision": decision,
        "decided_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "note": note,
        "uk_candidate": row["uk_candidate"],
        "automatic_merge": False,
    }
    target = decisions_root / component / f"{row['id']}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return target


def run_decide(args: argparse.Namespace) -> int:
    target = decide(
        Path(args.pending_root), Path(args.decisions_root), args.component, args.key, args.decision, args.note
    )
    print(f"recorded {args.decision} decision -> {target}")
    print("pending result and upstream UK were not modified; automatic merge: no")
    return 0


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("review", help="manage explicit translation review approvals")
    commands = parser.add_subparsers(dest="review_command", required=True)
    apply_parser = commands.add_parser("apply", help="approve one proposed correction into a sidecar")
    apply_parser.add_argument("--component", required=True)
    apply_parser.add_argument("--key", required=True)
    apply_parser.add_argument("--proposed-root", default="review/proposed")
    apply_parser.add_argument("--approved-root", default="review/approved")
    apply_parser.set_defaults(handler=run_apply)
    decide_parser = commands.add_parser("decide", help="approve or reject one pending pilot row")
    decide_parser.add_argument("--component", required=True)
    decide_parser.add_argument("--key", required=True)
    decide_parser.add_argument("--decision", choices=("approve", "reject"), required=True)
    decide_parser.add_argument("--note")
    decide_parser.add_argument("--pending-root", default="review/pending")
    decide_parser.add_argument("--decisions-root", default="review/decisions")
    decide_parser.set_defaults(handler=run_decide)
