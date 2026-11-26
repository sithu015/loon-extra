#!/usr/bin/env python3
"""Compute and sync Loon `#!source` SHA-256 hashes for all plugins/*.lpx.

Loon checks `#!source` by hashing the exact UTF-8 URL string without a trailing
newline (`printf '%s' '<url>' | shasum -a 256`). Each plugin includes both the
GitHub Raw URL and the jsDelivr CDN mirror hash separated by a comma so either
installation source passes verification.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_SLUG = "sithu015/loon-extra"
BRANCH = "main"


def expected_urls(rel_path: str) -> tuple[str, str]:
    raw_url = f"https://raw.githubusercontent.com/{REPO_SLUG}/{BRANCH}/{rel_path}"
    cdn_url = f"https://cdn.jsdelivr.net/gh/{REPO_SLUG}@{BRANCH}/{rel_path}"
    return raw_url, cdn_url


def sha256_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def expected_source_value(rel_path: str) -> str:
    raw_url, cdn_url = expected_urls(rel_path)
    return f"{sha256_url(raw_url)}, {sha256_url(cdn_url)}"


def process_plugin(path: Path, check_only: bool, date_str: str | None) -> tuple[bool, str]:
    rel = path.relative_to(ROOT).as_posix()
    expected = expected_source_value(rel)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    changed = False
    found_source = False
    new_lines: list[str] = []

    for line in lines:
        if line.startswith("#!source"):
            found_source = True
            target = f"#!source = {expected}"
            if line != target:
                changed = True
                new_lines.append(target)
            else:
                new_lines.append(line)
        elif date_str and line.startswith("#!date"):
            target = f"#!date = {date_str}"
            if line != target:
                changed = True
                new_lines.append(target)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if not found_source:
        raise ValueError(f"{rel}: missing `#!source` header line")

    if changed and not check_only:
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return changed, expected


def main() -> int:
    parser = argparse.ArgumentParser(description="Update or verify Loon plugin #!source SHA-256 hashes.")
    parser.add_argument("--check", action="store_true", help="Verify hashes without modifying files.")
    parser.add_argument("--date", default=None, help="Optional YYYY-MM-DD value to sync `#!date`.")
    args = parser.parse_args()

    if args.date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        print(f"ERROR: invalid --date format: {args.date} (expected YYYY-MM-DD)", file=sys.stderr)
        return 2

    plugins = sorted((ROOT / "plugins").glob("*.lpx"))
    if not plugins:
        print("ERROR: no plugins/*.lpx files found", file=sys.stderr)
        return 1

    stale = []
    for plugin in plugins:
        rel = plugin.relative_to(ROOT).as_posix()
        changed, expected = process_plugin(plugin, check_only=args.check, date_str=args.date)
        raw_url, cdn_url = expected_urls(rel)
        if args.check:
            if changed:
                stale.append(rel)
                print(f"STALE: {rel}\n  expected #!source = {expected}")
            else:
                print(f"OK:    {rel}")
        else:
            status = "UPDATED" if changed else "UNCHANGED"
            print(f"{status}: {rel}")
            print(f"  Raw URL: {raw_url} ({sha256_url(raw_url)})")
            print(f"  CDN URL: {cdn_url} ({sha256_url(cdn_url)})")

    if args.check and stale:
        print(f"\nERROR: {len(stale)} plugin(s) have stale #!source hashes. Run `python3 scripts/update_sources.py`.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
