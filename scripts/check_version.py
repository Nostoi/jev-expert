#!/usr/bin/env python3
"""Release-versioning gate for this plugin.

The version in .claude-plugin/plugin.json is the single source of truth and must be
SemVer (MAJOR.MINOR.PATCH). CHANGELOG.md must keep an "## [Unreleased]" section and
a "## [X.Y.Z] - date" section for the current version.

Usage:
  check_version.py                  check plugin.json and CHANGELOG agree
  check_version.py --base REF       also require a version bump if shipped files
                                    (.claude-plugin/, skills/, agents/) changed since REF
  check_version.py --tag vX.Y.Z     also require the tag to match the version
  check_version.py --print-version  print the version
  check_version.py --release-notes  print the CHANGELOG section for the version
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

MANIFEST = ".claude-plugin/plugin.json"
SHIPPED = (".claude-plugin/", "skills/", "agents/")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def parse(version: str) -> tuple[int, int, int]:
    m = SEMVER.match(version)
    if not m:
        raise ValueError(f"version {version!r} in {MANIFEST} is not semver MAJOR.MINOR.PATCH")
    return tuple(int(p) for p in m.groups())


def changelog_section(text: str, version: str) -> str | None:
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base")
    ap.add_argument("--tag")
    ap.add_argument("--print-version", action="store_true")
    ap.add_argument("--release-notes", action="store_true")
    args = ap.parse_args()

    version = json.loads(Path(MANIFEST).read_text())["version"]
    errors = []
    try:
        current = parse(version)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    changelog = Path("CHANGELOG.md").read_text()
    if "## [Unreleased]" not in changelog:
        errors.append("CHANGELOG.md has no '## [Unreleased]' section")
    notes = changelog_section(changelog, version)
    if notes is None:
        errors.append(f"CHANGELOG.md has no '## [{version}]' section for the version in {MANIFEST}")

    if args.print_version:
        print(version)
    if args.release_notes and notes is not None:
        print(notes)

    if args.tag and args.tag != f"v{version}":
        errors.append(f"tag {args.tag} does not match plugin version v{version}")

    if args.base:
        changed = [
            f
            for f in git("diff", "--name-only", "--no-renames", f"{args.base}...HEAD").split()
            if f.startswith(SHIPPED)
        ]
        if changed:
            try:
                base_version = json.loads(git("show", f"{args.base}:{MANIFEST}"))["version"]
            except subprocess.CalledProcessError:
                base_version = None  # manifest did not exist at base: first release
            if base_version is not None and current <= parse(base_version):
                errors.append(
                    f"shipped files changed since {args.base} ({', '.join(changed[:5])}"
                    f"{', ...' if len(changed) > 5 else ''}) but version {version} is not greater "
                    f"than {base_version}; bump {MANIFEST} and add a CHANGELOG section"
                )

    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
