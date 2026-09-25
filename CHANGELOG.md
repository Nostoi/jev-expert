# Changelog

All notable changes to this plugin are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). The version in
`.claude-plugin/plugin.json` is the single source of truth; CI refuses a change to
shipped files (`.claude-plugin/`, `skills/`, `agents/`) that does not raise it.

## [Unreleased]

## [0.1.0] - 2026-09-25

### Added
- `jev-engineering` skill: decision-loop design, failure-as-`not_checked`,
  off/shadow/active rollout, retry ownership, model-version handling, decision
  logging, credentials, and evaluation guidance for code that calls TypeSafe Jev.
- References: implementation / audit / rollout workflows, evaluation measures,
  question-design checklist and live question test, and 21 insertion-point recipes.
- `scripts/question_eval.py`: live question-test harness (dry-run by default).
- `jev-integration-reviewer` agent: independent review of a Jev integration, with an
  opt-in live question test.
- Evals: three test prompts with assertions, two fixture repositories, and a
  trigger-eval set.
