"""Translation catalog parsers and recursive leaf flattening."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    """Return scalar leaves, preserving list indices in unambiguous paths."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            result.update(flatten(child, path))
        return result
    if isinstance(value, list):
        result = {}
        for index, child in enumerate(value):
            result.update(flatten(child, f"{prefix}[{index}]"))
        return result
    return {prefix: value}


def parse_json(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return {}, [str(error)]
    if not isinstance(value, (dict, list)):
        return {}, ["catalog root must be an object or array"]
    return flatten(value), []


_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})|\\(.)", re.DOTALL)


def _unescape(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.group(1):
            return chr(int(match.group(1), 16))
        escaped = match.group(2)
        return {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}.get(escaped, escaped)

    return _ESCAPE.sub(replace, value)


def parse_properties(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        physical = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as error:
        return {}, [str(error)]
    logical: list[str] = []
    pending = ""
    for line in physical:
        current = pending + line.lstrip() if pending else line
        trailing = len(current) - len(current.rstrip("\\"))
        if trailing % 2:
            pending = current[:-1]
        else:
            logical.append(current)
            pending = ""
    if pending:
        logical.append(pending)
    result: dict[str, Any] = {}
    errors: list[str] = []
    for number, line in enumerate(logical, 1):
        stripped = line.lstrip()
        if not stripped or stripped.startswith(("#", "!")):
            continue
        escaped = False
        split = None
        for index, character in enumerate(line):
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
            elif character in "=:" or character.isspace():
                split = index
                break
        if split is None:
            key, value = line, ""
        else:
            key = line[:split]
            cursor = split
            while cursor < len(line) and line[cursor].isspace():
                cursor += 1
            if cursor < len(line) and line[cursor] in "=:":
                cursor += 1
            while cursor < len(line) and line[cursor].isspace():
                cursor += 1
            value = line[cursor:]
        key = _unescape(key)
        if key in result:
            errors.append(f"line {number}: duplicate key {key!r}")
        result[key] = _unescape(value)
    return result, errors


def load_catalog(path: Path, kind: str) -> tuple[dict[str, Any], list[str]]:
    if kind == "json":
        return parse_json(path)
    if kind == "properties":
        return parse_properties(path)
    return {}, [f"unsupported translation type: {kind}"]
