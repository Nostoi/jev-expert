# Changelog

All notable changes to this plugin are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). The version in
`.claude-plugin/plugin.json` is the single source of truth; CI refuses a change to
shipped files (`.claude-plugin/`, `skills/`, `agents/`) that does not raise it.

## [Unreleased]

## [0.1.2] - 2026-09-26

### Fixed
- An audit of a failed decision no longer ends at the layer that caused it. Before
  closing, it checks the whole integration for invalid responses reaching the
  policy, more than one retry owner, and shadow side effects, and fixes what it
  finds when asked to fix. The skill notes that the Python SDK does not reject unknown choice keys or
  out-of-range values, and the rollout checklist includes invalid responses.

## [0.1.1] - 2026-09-25

### Fixed
- A request to review only the Jev questions no longer turns into a full
  integration audit. The `jev-integration-reviewer` description tells callers to
  pass the user's scope unchanged, the agent runs only its question check for a
  question-only request, and the skill keeps its own question reviews to the
  questions, their state, their grouping, and how the code reads the answers.

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
