"""Fetch manifest-pinned upstream catalogs into the local cache."""

from __future__ import annotations

import argparse
from pathlib import Path
import urllib.request

from .manifest import audit_components, load_manifest


LANGUAGES = {"en": "english", "ru": "russian", "uk": "ukrainian"}


def raw_url(repository: str, commit: str, path: str) -> str:
    marker = "github.com/"
    if marker not in repository:
        raise ValueError(f"unsupported repository URL: {repository}")
    slug = repository.split(marker, 1)[1].removesuffix(".git")
    return f"https://raw.githubusercontent.com/{slug}/{commit}/{path}"


def cache_path(cache_root: Path, component: str, commit: str, language: str, source_path: str) -> Path:
    return cache_root / component / commit / language / Path(source_path).name


def fetch_all(manifest_path: Path, cache_root: Path, selected: str | None = None) -> list[Path]:
    manifest = load_manifest(manifest_path)
    components = audit_components(manifest)
    if selected:
        if selected not in components:
            raise ValueError(f"component is not baseline-auditable: {selected}")
        components = {selected: components[selected]}
    written: list[Path] = []
    for name, component in components.items():
        translation = component["translation"]
        for language, field in LANGUAGES.items():
            source_path = translation[field]
            target = cache_path(cache_root, name, component["commit"], language, source_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(
                raw_url(component["repository"], component["commit"], source_path),
                headers={"User-Agent": "carbonio-uk-fetch"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
            payload.decode("utf-8")
            target.write_bytes(payload)
            written.append(target)
            print(f"fetched {name}:{language} -> {target}")
    return written


def run(args: argparse.Namespace) -> int:
    paths = fetch_all(Path(args.manifest), Path(args.cache_root), args.component)
    print(f"fetched {len(paths)} pinned resources")
    return 0


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("fetch", help="fetch manifest-pinned locale resources")
    parser.add_argument("--manifest", default="manifest.yaml")
    parser.add_argument("--cache-root", default=".cache/upstream")
    parser.add_argument("--component")
    parser.set_defaults(handler=run)
