"""Tests for scripts/check_version.py, the release-versioning gate."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_version.py"

CHANGELOG = """# Changelog

## [Unreleased]

## [{v}] - 2026-09-25

### Added
- Something for {v}.

## [0.0.1] - 2026-09-01

### Added
- Older entry.
"""


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def write(repo, version, changelog_version=None):
    (repo / ".claude-plugin").mkdir(exist_ok=True)
    (repo / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "p", "version": version}))
    (repo / "CHANGELOG.md").write_text(CHANGELOG.format(v=changelog_version or version))


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    write(tmp_path, "0.1.0")
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "SKILL.md").write_text("v1")
    (tmp_path / "README.md").write_text("readme")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "tag", "base")
    return tmp_path


def run(repo, *args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=repo, capture_output=True, text=True)


def commit(repo, msg="change"):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)


def test_consistent_repo_passes(repo):
    r = run(repo)
    assert r.returncode == 0, r.stderr


def test_invalid_semver_fails(repo):
    write(repo, "1.2")
    r = run(repo)
    assert r.returncode == 1
    assert "semver" in r.stderr.lower()


def test_missing_changelog_section_fails(repo):
    write(repo, "0.2.0", changelog_version="0.1.0")
    r = run(repo)
    assert r.returncode == 1
    assert "0.2.0" in r.stderr and "CHANGELOG" in r.stderr


def test_missing_unreleased_section_fails(repo):
    (repo / "CHANGELOG.md").write_text(CHANGELOG.format(v="0.1.0").replace("## [Unreleased]\n\n", ""))
    r = run(repo)
    assert r.returncode == 1
    assert "Unreleased" in r.stderr


def test_shipped_change_without_bump_fails(repo):
    (repo / "skills" / "SKILL.md").write_text("v2")
    commit(repo)
    r = run(repo, "--base", "base")
    assert r.returncode == 1
    assert "skills/SKILL.md" in r.stderr and "0.1.0" in r.stderr


def test_shipped_change_with_bump_passes(repo):
    (repo / "skills" / "SKILL.md").write_text("v2")
    write(repo, "0.1.1")
    commit(repo)
    r = run(repo, "--base", "base")
    assert r.returncode == 0, r.stderr


def test_version_decrease_fails(repo):
    (repo / "skills" / "SKILL.md").write_text("v2")
    write(repo, "0.0.9")
    commit(repo)
    r = run(repo, "--base", "base")
    assert r.returncode == 1


def test_semver_compared_numerically(repo):
    write(repo, "0.9.0")
    commit(repo, "to 0.9.0")
    git(repo, "tag", "-f", "base")
    (repo / "skills" / "SKILL.md").write_text("v2")
    write(repo, "0.10.0")
    commit(repo)
    r = run(repo, "--base", "base")
    assert r.returncode == 0, r.stderr


def test_shipped_rename_out_without_bump_fails(repo):
    (repo / "docs").mkdir()
    git(repo, "mv", "skills/SKILL.md", "docs/retired-skill.md")
    commit(repo, "retire skill")
    r = run(repo, "--base", "base")
    assert r.returncode == 1
    assert "skills/SKILL.md" in r.stderr and "0.1.0" in r.stderr


def test_non_shipped_change_needs_no_bump(repo):
    (repo / "README.md").write_text("new readme")
    commit(repo)
    r = run(repo, "--base", "base")
    assert r.returncode == 0, r.stderr


def test_tag_must_match_version(repo):
    assert run(repo, "--tag", "v0.1.0").returncode == 0
    r = run(repo, "--tag", "v0.2.0")
    assert r.returncode == 1
    assert "v0.1.0" in r.stderr


def test_release_notes_prints_only_that_section(repo):
    r = run(repo, "--release-notes")
    assert r.returncode == 0
    assert "Something for 0.1.0" in r.stdout
    assert "Older entry" not in r.stdout


def test_print_version(repo):
    r = run(repo, "--print-version")
    assert r.stdout.strip() == "0.1.0"
