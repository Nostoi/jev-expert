# jev-expert

A Claude Code plugin with one skill, `jev-engineering`, for putting TypeSafe Jev
decisions into real software safely: rollout modes, failure handling, versioning,
question review, evaluation, and audits.

It complements the official TypeSafe plugin, which owns the API contract and
question design. Install both:

```bash
claude plugin marketplace add typesafe-ai/skills
claude plugin install typesafe@typesafe-ai
claude --plugin-dir ~/dev/tools/jev-expert   # or install from a marketplace
```

Skill content is distilled from *Jev Engineering: Typed Decision Systems for
Reliable Agent Workflows* (Av1dlive, 2026,
https://github.com/codejunkie99/jev-engineering) and the official docs at
https://docs.typesafe.ai.

## Evals

`evals/evals.json` holds three test prompts (implement, audit, rollout) with
assertions; `evals/fixtures/` holds the example repos they run against. Runs and
grading go in `jev-engineering-workspace/` (git-ignored).
