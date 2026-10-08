"""Manifest loading shared by fetch, audit, and later workflow stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict) or not isinstance(data.get("components"), dict):
        raise ValueError(f"invalid manifest: {path}")
    return data


def audit_components(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        name: component
        for name, component in data["components"].items()
        if component.get("baseline_audit") is True and component.get("translation", {}).get("available") is True
    }
