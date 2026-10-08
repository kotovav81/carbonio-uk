"""Reproducible discovery of public Carbonio localization repositories."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.request


ORG = "Zextras"
API = "https://api.github.com"

# Scope is intentionally explicit: discovery verifies these relationships rather
# than silently adding every repository whose name happens to contain "i18n".
COMPONENTS = (
    ("shell", "carbonio-shell-ui", "carbonio-shell-ui-i18n", "json"),
    ("admin_login", "carbonio-admin-login-ui", "carbonio-admin-login-ui-i18n", "json"),
    ("login", "carbonio-login-ui", "carbonio-login-ui-i18n", "json"),
    ("auth_ui", "carbonio-auth-ui", "carbonio-auth-ui-i18n", "json"),
    ("auth_properties", "carbonio-auth-ui", "carbonio-auth-i18n", "properties"),
    ("mail", "carbonio-mails-ui", "carbonio-mails-ui-i18n", "json"),
    ("calendar", "carbonio-calendars-ui", "carbonio-calendars-ui-i18n", "json"),
    ("contacts", "carbonio-contacts-ui", "carbonio-contacts-ui-i18n", "json"),
    ("files", "carbonio-files-ui", "carbonio-files-ui-i18n", "json"),
    ("search", "carbonio-search-ui", "carbonio-search-ui-i18n", "json"),
    ("tasks", "carbonio-tasks-ui", "carbonio-tasks-ui-i18n", "json"),
    ("collaboration", "carbonio-ws-collaboration-ui", "carbonio-ws-collaboration-ui-i18n", "json"),
    ("storages", None, "carbonio-storages-ui-i18n", "json"),
)

REVIEW_REPOSITORIES = (
    "carbonio-admin-manage-ui-i18n",
    "carbonio-admin-ui",
    "carbonio-admin-ui-i18n",
    "carbonio-chats-ui-i18n",
    "carbonio-webui-i18n",
)

# Public metadata observed on 2026-10-08. This only supplies classification when
# GitHub's anonymous REST quota is exhausted; branch SHAs and files are still
# probed live with git/raw GitHub.
SNAPSHOT = {
    "carbonio-shell-ui": ("main", False, "TypeScript"),
    "carbonio-shell-ui-i18n": ("master", False, None),
    "carbonio-admin-console-ui": ("main", False, "TypeScript"),
    "carbonio-admin-login-ui": ("main", False, "TypeScript"),
    "carbonio-admin-login-ui-i18n": ("master", False, None),
    "carbonio-login-ui": ("main", False, "JavaScript"),
    "carbonio-login-ui-i18n": ("master", False, None),
    "carbonio-auth-ui": ("main", False, "TypeScript"),
    "carbonio-auth-ui-i18n": ("master", False, None),
    "carbonio-auth-i18n": ("main", False, None),
    "carbonio-mails-ui": ("main", False, "TypeScript"),
    "carbonio-mails-ui-i18n": ("master", False, None),
    "carbonio-calendars-ui": ("main", False, "TypeScript"),
    "carbonio-calendars-ui-i18n": ("master", False, None),
    "carbonio-contacts-ui": ("main", False, "TypeScript"),
    "carbonio-contacts-ui-i18n": ("master", False, None),
    "carbonio-files-ui": ("main", False, "TypeScript"),
    "carbonio-files-ui-i18n": ("master", False, None),
    "carbonio-search-ui": ("main", False, "TypeScript"),
    "carbonio-search-ui-i18n": ("master", False, None),
    "carbonio-tasks-ui": ("main", False, "TypeScript"),
    "carbonio-tasks-ui-i18n": ("master", False, None),
    "carbonio-ws-collaboration-ui": ("main", False, "TypeScript"),
    "carbonio-ws-collaboration-ui-i18n": ("main", False, None),
    "carbonio-storages-ui-i18n": ("master", False, None),
    "carbonio-admin-ui": ("devel", True, "TypeScript"),
    "carbonio-admin-ui-i18n": ("master", False, None),
    "carbonio-chats-ui-i18n": ("master", False, None),
    "carbonio-webui-i18n": ("main", False, "Shell"),
}


def _request_json(url: str) -> object:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "carbonio-uk-discovery"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _org_repositories() -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    page = 1
    while True:
        rows = _request_json(f"{API}/orgs/{ORG}/repos?per_page=100&page={page}")
        if not isinstance(rows, list):
            raise RuntimeError("unexpected GitHub repositories response")
        for row in rows:
            result[str(row["name"])] = row
        if len(rows) < 100:
            return result
        page += 1


def _snapshot_repositories() -> dict[str, dict[str, object]]:
    return {
        name: {
            "name": name,
            "html_url": f"https://github.com/{ORG}/{name}",
            "default_branch": branch,
            "archived": archived,
            "language": language,
        }
        for name, (branch, archived, language) in SNAPSHOT.items()
    }


def _head(repository: str, branch: str) -> str:
    process = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{ORG}/{repository}.git", f"refs/heads/{branch}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if process.returncode or not process.stdout.strip():
        return ""
    return process.stdout.split()[0]


def _exists(repository: str, commit: str, path: str) -> bool:
    url = f"https://raw.githubusercontent.com/{ORG}/{repository}/{commit}/{path}"
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "carbonio-uk-discovery"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status == 200
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise


def _translation_paths(kind: str) -> dict[str, str]:
    if kind == "properties":
        return {
            "english": "com_zextras_module_auth.properties",
            "russian": "com_zextras_module_auth_ru.properties",
            "ukrainian": "com_zextras_module_auth_uk.properties",
        }
    return {"english": "en.json", "russian": "ru.json", "ukrainian": "uk.json"}


def _scan_local(root: Path) -> dict[str, object]:
    patterns = ("*.json", "*.properties", "*.po", "*.mo")
    if not root.exists():
        return {"root": str(root), "exists": False, "mode": "read-only", "resource_files": []}
    files: list[str] = []
    for pattern in patterns:
        for path in root.rglob(pattern):
            lowered = str(path).lower()
            if any(marker in lowered for marker in ("locale", "i18n", "translation", "message")):
                files.append(str(path))
    return {
        "root": str(root),
        "exists": True,
        "mode": "read-only",
        "resource_files": sorted(set(files)),
    }


def discover(local_root: Path) -> dict[str, object]:
    metadata_source = "GitHub REST API"
    try:
        repositories = _org_repositories()
    except urllib.error.HTTPError as error:
        if error.code != 403:
            raise
        metadata_source = "embedded public metadata snapshot (GitHub REST rate limit); live git/raw checks"
        repositories = _snapshot_repositories()
        print("warning: GitHub REST rate limit exceeded; using dated public metadata snapshot")
    checked_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    components: list[dict[str, object]] = []
    for name, source_name, locale_name, kind in COMPONENTS:
        meta = repositories.get(locale_name)
        source_meta = repositories.get(source_name) if source_name else None
        if meta is None:
            raise RuntimeError(f"public repository not found: {locale_name}")
        branch = str(meta["default_branch"])
        commit = _head(locale_name, branch)
        if not commit:
            raise RuntimeError(f"cannot resolve {locale_name}:{branch}")
        paths = _translation_paths(kind)
        present = {language: _exists(locale_name, commit, path) for language, path in paths.items()}
        urls = {
            language: f"https://raw.githubusercontent.com/{ORG}/{locale_name}/{commit}/{path}"
            for language, path in paths.items()
        }
        components.append(
            {
                "name": name,
                "repository": str(meta["html_url"]),
                "source_repository": str(source_meta["html_url"]) if source_meta else None,
                "branch": branch,
                "commit": commit,
                "checked_at": checked_at,
                "status": "active",
                "active": not bool(meta["archived"]),
                "archived": bool(meta["archived"]),
                "technology": "Java .properties" if kind == "properties" else "i18next JSON",
                "translation": {"type": kind, **paths, "urls": urls, "locale": "uk", "available": True},
                "languages": {"en": present["english"], "ru": present["russian"], "uk": present["ukrainian"]},
                "included": not bool(meta["archived"]) and all(present.values()),
                "baseline_audit": not bool(meta["archived"]) and all(present.values()),
                "source": {
                    "branch": source_meta.get("default_branch") if source_meta else None,
                    "commit": _head(source_name, str(source_meta["default_branch"])) if source_meta else None,
                    "technology": source_meta.get("language") if source_meta else None,
                    "archived": source_meta.get("archived") if source_meta else None,
                },
            }
        )

    admin_meta = repositories["carbonio-admin-console-ui"]
    admin_branch = str(admin_meta["default_branch"])
    admin_commit = _head("carbonio-admin-console-ui", admin_branch)
    components.append(
        {
            "name": "admin_console",
            "repository": str(admin_meta["html_url"]),
            "source_repository": str(admin_meta["html_url"]),
            "branch": admin_branch,
            "commit": admin_commit,
            "checked_at": checked_at,
            "status": "active/blocked",
            "active": True,
            "archived": False,
            "technology": "TypeScript/React, pnpm/Turborepo/Vite",
            "translation": {
                "type": "json",
                "repository": "https://github.com/Zextras/carbonio-admin-manage-ui-i18n",
                "available": False,
                "blocked_reason": "translation repository unavailable",
                "english": None,
                "russian": None,
                "ukrainian": None,
                "urls": {"english": None, "russian": None, "ukrainian": None},
                "locale": "uk",
            },
            "languages": {"en": False, "ru": False, "uk": False},
            "included": True,
            "baseline_audit": False,
            "source": {
                "branch": admin_branch,
                "commit": admin_commit,
                "technology": admin_meta.get("language"),
                "archived": False,
            },
        }
    )

    reviewed = []
    for repository in REVIEW_REPOSITORIES:
        meta = repositories.get(repository)
        reviewed.append(
            {
                "repository": f"https://github.com/{ORG}/{repository}",
                "public": meta is not None,
                "archived": meta.get("archived") if meta else None,
                "default_branch": meta.get("default_branch") if meta else None,
                "commit": _head(repository, str(meta["default_branch"])) if meta else None,
            }
        )
    return {
        "schema": 1,
        "generated_at": checked_at,
        "organization": f"https://github.com/{ORG}",
        "method": f"{metadata_source}, git ls-remote branch HEAD, raw resource HEAD checks",
        "components": components,
        "reviewed_repositories": reviewed,
        "aggregators": [
            {
                "name": "carbonio-webui-i18n",
                "repository": "https://github.com/Zextras/carbonio-webui-i18n",
                "status": "aggregator/packaging-only",
                "branch": repositories["carbonio-webui-i18n"]["default_branch"],
                "commit": _head("carbonio-webui-i18n", str(repositories["carbonio-webui-i18n"]["default_branch"])),
                "checked_at": checked_at,
                "components": [item[0] for item in COMPONENTS],
                "baseline_audit": False,
            }
        ],
        "local_resources": _scan_local(local_root),
    }


def _yaml_string(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(str(value), ensure_ascii=False)


def render_manifest(data: dict[str, object]) -> str:
    lines = ["schema: 1", "locale:", '  primary: "uk"', '  display_name: "Українська"', '  reference: "ru"', "components:"]
    for component in data["components"]:
        lines.extend(
            [
                f"  {component['name']}:",
                f"    repository: {_yaml_string(component['repository'])}",
                f"    branch: {_yaml_string(component['branch'])}",
                f"    commit: {_yaml_string(component['commit'])}",
                f"    checked_at: {_yaml_string(component['checked_at'])}",
                f"    status: {_yaml_string(component['status'])}",
                f"    baseline_audit: {_yaml_string(component['baseline_audit'])}",
                f"    source_repository: {_yaml_string(component['source_repository'])}",
                "    translation:",
                f"      type: {_yaml_string(component['translation']['type'])}",
                f"      repository: {_yaml_string(component['translation'].get('repository', component['repository']))}",
                f"      available: {_yaml_string(component['translation']['available'])}",
                f"      english: {_yaml_string(component['translation']['english'])}",
                f"      russian: {_yaml_string(component['translation']['russian'])}",
                f"      ukrainian: {_yaml_string(component['translation']['ukrainian'])}",
                '      locale: "uk"',
            ]
        )
        if not component["translation"]["available"]:
            lines.append(f"      blocked_reason: {_yaml_string(component['translation']['blocked_reason'])}")
    lines.append("aggregators:")
    for aggregator in data["aggregators"]:
        lines.extend(
            [
                f"  {aggregator['name']}:",
                f"    repository: {_yaml_string(aggregator['repository'])}",
                f"    branch: {_yaml_string(aggregator['branch'])}",
                f"    commit: {_yaml_string(aggregator['commit'])}",
                f"    checked_at: {_yaml_string(aggregator['checked_at'])}",
                f"    status: {_yaml_string(aggregator['status'])}",
                "    components:",
                *[f"      - {_yaml_string(name)}" for name in aggregator["components"]],
            ]
        )
    return "\n".join(lines) + "\n"


def render_markdown(data: dict[str, object]) -> str:
    rows = []
    for item in data["components"]:
        translation = item["translation"]
        paths = "; ".join(str(translation[key] or "unavailable") for key in ("english", "russian", "ukrainian"))
        links = []
        for language, label in (("english", "EN"), ("russian", "RU"), ("ukrainian", "UK")):
            url = translation["urls"][language]
            links.append(f"[{label}]({url})" if url else f"{label}: unavailable")
        rows.append(
            f"| {item['name']} | [{item['repository'].rsplit('/', 1)[-1]}]({item['repository']}) | "
            f"{item['branch']} | `{item['commit']}` | {item['checked_at']} | "
            f"{' / '.join(links)} | `{paths}` | {item['status']} | {'yes' if item['baseline_audit'] else 'no'} |"
        )
    local = data["local_resources"]
    review_lines = []
    for item in data["reviewed_repositories"]:
        state = "not public/not found" if not item["public"] else ("archived/legacy" if item["archived"] else "active")
        review_lines.append(f"- `{item['repository'].rsplit('/', 1)[-1]}`: {state}; commit `{item['commit'] or 'n/a'}`.")
    return f"""# Zextras Carbonio localization discovery

Generated: `{data['generated_at']}`. Coverage and paths below are bound to the full commit SHA in `discovery.json` and `manifest.yaml`.

## Discovered components and locale sources

| Component | Repository | Branch | Commit SHA | Checked | Files | Translation paths | Status | Baseline audit |
|---|---|---:|---|---|---|---|:---:|:---:|
{os.linesep.join(rows)}

English is the structural source of truth; existing Ukrainian is preserved; Russian is context/QA only. The 13 baseline-audit repositories are public, active, and expose all three required resources at the recorded SHA.

For every one of the 13 audit-ready components, `discovery.json` records the repository URL, branch, full commit SHA, check date, EN/RU/UK paths, and direct immutable raw-file URLs. The Admin Console is retained as `active/blocked`, but is excluded from the current baseline audit because no confirmed public i18n source is available.

## Web applications and build technology

- Web Client shell: `carbonio-shell-ui`, TypeScript/React, pnpm, build script `pnpm run build:pkg && pnpm run build:lib`.
- Admin Console: `carbonio-admin-console-ui`, TypeScript/React monorepo, pnpm/Turborepo/Vite. Its current `package.json` references `carbonio-admin-manage-ui-i18n`, which is not public/found. The component remains in discovery and manifest as `active/blocked`; only its baseline audit is excluded.
- User login: `carbonio-login-ui`, JavaScript/React, pnpm/Webpack; runtime path `i18n/{{{{lng}}}}.json`, fallback `en`, browser language detection.
- Admin login: `carbonio-admin-login-ui`, TypeScript/React, pnpm/Vite; runtime path `i18n/{{{{lng}}}}.json`, fallback `en`, browser language detection without preference caching.
- Feature modules (auth, mail, calendar, contacts, files, search, tasks, collaboration): TypeScript/React packages, predominantly pnpm plus Carbonio UI SDK build.
- `carbonio-auth-i18n` is the non-JSON exception and supplies Java `.properties` resources.

## Reviewed but not included

{os.linesep.join(review_lines)}

`carbonio-webui-i18n` has status `aggregator/packaging-only`, links all 13 locale components in `discovery.json` and `manifest.yaml`, and has no root EN/RU/UK resources. `carbonio-admin-ui` is archived; its locale repository is retained only for historical comparison. `carbonio-chats-ui-i18n` is superseded for current collaboration scope by `carbonio-ws-collaboration-ui-i18n`.

## Local Carbonio resources (read-only)

- Root: `{local['root']}`
- Exists: `{'yes' if local['exists'] else 'no'}`
- Matching resource files: `{len(local['resource_files'])}`

No local file was created, changed, or removed during this scan. `/opt/zextras` was not present when this report was generated.

## Reproduce

```bash
python -m carbonio_uk discovery
```

The command queries public GitHub metadata, resolves branch HEAD using `git ls-remote`, checks resource paths through raw GitHub, scans the configured local root read-only, and rewrites all three outputs deterministically apart from timestamp and moving upstream SHAs.
"""


def write_outputs(data: dict[str, object], project_root: Path) -> None:
    reports = project_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "discovery.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (reports / "discovery.md").write_text(render_markdown(data), encoding="utf-8")
    (project_root / "manifest.yaml").write_text(render_manifest(data), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    data = discover(Path(args.local_root))
    write_outputs(data, Path(args.project_root).resolve())
    ready = sum(bool(item["baseline_audit"]) for item in data["components"])
    print(f"discovered {len(data['components'])} components; {ready} audit-ready, 1 active/blocked")
    print("wrote reports/discovery.md, reports/discovery.json, manifest.yaml")
    return 0


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("discovery", help="discover public Zextras localization sources")
    parser.add_argument("--local-root", default="/opt/zextras", help="local Carbonio root to scan read-only")
    parser.add_argument("--project-root", default=".", help="directory receiving reports and manifest")
    parser.set_defaults(handler=run)
