# jev-expert

A [Claude Code](https://claude.com/claude-code) plugin that helps coding agents put
[TypeSafe Jev](https://docs.typesafe.ai) decisions into real software **safely**.

The official TypeSafe plugin teaches an agent the API: endpoints, question types, and
the SDK. This plugin covers the engineering around those calls. It deals with where a
Jev decision belongs, what happens when the call fails, how to roll out without
side effects, whether the questions are any good, and how to tell that the
integration works.

> Not affiliated with or endorsed by TypeSafe. See [Attribution](#attribution).

## What's inside

| Component | What it does |
|---|---|
| **`jev-engineering` skill** | Loads when an agent adds, audits, or rolls out a Jev integration. Its doctrine: a failed call means `not_checked`, never a negative answer; `off` → `shadow` → `active` rollout, with shadow producing no side effects; one owner for retries; authority stays in code; log the returned model; mandatory question review; never print credentials. |
| `references/workflows.md` | Checklists for implementing, auditing, and rolling out. |
| `references/question-design.md` | A static question-review checklist, with each rule tied to an official docs page, plus a method for testing questions live. |
| `references/evaluation.md` | Splits, baselines, coverage, selective error, critical misses, and a failure taxonomy. |
| `references/recipes.md` | 21 insertion-point recipes (agent routing, stall detection, citation checks, support intake, scoring another system's output, …). |
| **`scripts/question_eval.py`** | Live question-test harness. Uses only the standard library, and does a dry run by default. |
| **`jev-integration-reviewer` agent** | Independent reviewer for a Jev integration. It returns a verdict, findings with `file:line` and a failure scenario, a question review, and a list of what was not verified. |

## Install

Install the official TypeSafe plugin first, since this one builds on it:

```bash
claude plugin marketplace add typesafe-ai/skills
claude plugin install typesafe@typesafe-ai

claude plugin marketplace add Nostoi/jev-expert
claude plugin install jev-expert@jev-expert
```

Pick up new releases with `claude plugin marketplace update jev-expert` followed by `claude plugin update jev-expert@jev-expert`.

To work on the plugin from a clone: `claude --plugin-dir /path/to/jev-expert`.

## Use

The skill loads by itself on requests such as *"add a Jev check before we auto-reply
to tickets"*, *"audit our Jev integration"* or *"is this ready to go active?"*.

To review an integration, ask for it: *"use the jev-integration-reviewer agent to
review src/triage/"*. By default the reviewer reads code and runs local tests only.
It calls the TypeSafe API only when you explicitly authorize a live question test.

### Live question test

`question_eval.py` answers two questions about a set of Jev questions: do they agree
with your labels, and are the answers stable? It can compare wording variants side by
side.

```bash
S=skills/jev-engineering/scripts/question_eval.py

# Dry run: validates inputs and prints the call plan. No network, no files.
python3 $S --examples examples.jsonl --variant a=questions_a.json --variant b=questions_b.json

# Live: needs TYPESAFE_API_KEY, an explicit model, and a call budget.
python3 $S --examples examples.jsonl --variant a=questions_a.json --variant b=questions_b.json \
  --live --model jev-1.13.0 --repeats 3 --max-calls 60 --out results/
```

A live run writes `answers.jsonl`, `report.json` and `report.md`. The key is never
written. Examples are JSONL rows `{"id", "state", "labels": {qid: expected}}`, and
each variant is a `{qid: question}` object in the API's question shape. See
`tests/fixtures/question_eval/` for working examples.

## How well does it work?

Three realistic tasks (implement, audit, rollout readiness) were each run three
times with 0.1.3 and three times without it. Both arms **had the official
TypeSafe skill installed**, so the comparison measures what this plugin adds to
that setup. Whether the official skill actually loaded varied: in the baseline it
loaded in every task-1 run, two of three task-2 runs and no task-3 run; with the
plugin it loaded only in task 1.
Both arms ran on Sonnet in a session with no user settings, with docs access and
without sub-agents (so the plugin's reviewer agent never ran). One model per task
graded all six runs under shuffled labels, running probes against the code where
an assertion called for one. The pass rule was fixed before any run: the plugin
must be at least even on every task and ahead by 3 or more on at least two.

Scores count only assertions that a competent engineer with the official skill
alone would be expected to meet from the prompt:

| Three runs each | With 0.1.3 | Official skill only | Cost with / without |
|---|---|---|---|
| 1. Implement a Jev classifier | 33/33 | 18/33 | $5.02 / $2.36 |
| 2. Audit an outage | 30/30 | 22/30 | $3.24 / $2.79 |
| 3. Review rollout readiness | 25/27 | 11/27 | $1.25 / $1.27 |

- Without the plugin, all three implementations replaced the keyword router
  outright. In probes, an API error or a missing answer crashed ticket handling
  before the page was sent, and an unknown queue or an urgency of 1.7 went
  straight into routing. With the plugin, all three kept the keyword route as the
  fallback and passed those probes. Eval 1 took about twice as long and cost about
  twice as much with the plugin.
- In the audit, only the plugin's runs flagged the queue question's missing
  no-match option and stopped invalid answers from driving pages.
- In the rollout review, only the plugin's runs said routing accuracy was
  unmeasured, flagged the unpinned model alias, and named unvalidated answers as a
  blocker. The plugin recommended a staged rollout in only 1 of 3 runs.
- Five more eval 1 assertions reward this plugin's own conventions (mode switch,
  question module, model logging). They are scored separately: 14/15 with the
  plugin and 0/15 without.

Limits:

- Three runs per task, on one model.
- The plugin's author built the fixtures and wrote the assertions.
- A model did the grading.
- Six of the nine plugin runs mention "skill" or the skill's name in their output,
  so the graders could often tell the arms apart. The pass rule still holds
  without task 3.

An earlier smoke test (one run per task, unisolated) scored 100% against 64%. In a
separate headless run, the reviewer agent found the defects planted in
`evals/fixtures/ticket-router-jev`. The prompts, assertions and fixtures are in
`evals/` so you can rerun or extend them.

A fourth eval asks only for a review of the Jev questions in eleven files, with ten
defects drawn from the docs, one from this skill, and five clean controls. Each arm
ran three times and a model graded all nine runs against the same key:

| Eval 4, three runs each | Docs defects | Skill defect | Clean controls | Out-of-scope findings |
|---|---|---|---|---|
| Official skill only | 29/30 | 3/3 | 15/15 | 0 |
| With 0.1.0 | 28/30 | 3/3 | 15/15 | 29 |
| With 0.1.1 | 30/30 | 3/3 | 15/15 | 0 |

On question review alone the plugin adds nothing measurable over the official
skill. Version 0.1.0 padded the review with failure-handling findings the user had
not asked for; 0.1.1 keeps a question-only request on the questions.

Eval 2 (the outage audit) was rerun three times per version in a session with no
user settings and no plugins beyond this one, the official one, and Claude Code's
built-ins. Models graded the runs
without knowing the version, using separate probes for an unknown choice key, a
probability above 1, one below 0, and NaN, plus a valid answer as a control:

| Eval 2, three runs each | Responses validated | One retry owner | All 11 assertions |
|---|---|---|---|
| With 0.1.1 | 0/3 | 3/3 | 30/33 |
| With 0.1.2 | 2/3 | 3/3 | 32/33 |

Audits in 0.1.1 fixed the reported failure but left invalid Jev answers driving
pages and queues. 0.1.2 has the audit check the whole integration before it closes.
These runs had no docs access, so they aren't directly comparable with the 0.1.3
comparison above.

## Versioning

The plugin follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: an incompatible change to how agents use the plugin, such as a renamed
  skill or agent, or a removed script flag.
- **MINOR**: new guidance, recipes, references, or features.
- **PATCH**: corrections and wording fixes that keep the same behaviour.

`.claude-plugin/plugin.json` is the **only** place the version lives. Enforcement:

- **CI** (`.github/workflows/ci.yml`) runs `scripts/check_version.py` on every pull
  request and push to `main`. It fails when:
  - the version is not `MAJOR.MINOR.PATCH`;
  - `CHANGELOG.md` has no `## [Unreleased]` section or no section for the current
    version;
  - shipped files (`.claude-plugin/`, `skills/`, `agents/`) changed without raising the
    version.

  CI also runs the tests and `claude plugin validate`.
- **Release** (the `release` job in the same workflow) runs after CI passes on a push
  to `main`. When no tag `vX.Y.Z` exists for the current version, it creates one and publishes a GitHub
  Release whose notes are that version's `CHANGELOG.md` section.
- **`main` is protected**: changes arrive by pull request and CI must pass.

Changes to docs, tests, evals and CI need no version bump.

## Contributing

1. Branch from `main`.
2. Make your change and add a line under `## [Unreleased]` in `CHANGELOG.md`.
3. If you changed shipped files, set the new version in `.claude-plugin/plugin.json`.
   Then rename `Unreleased` to `## [X.Y.Z] - YYYY-MM-DD` and add a fresh empty
   `## [Unreleased]` above it.
4. Run the checks locally:
   ```bash
   python3 -m pytest tests
   python3 scripts/check_version.py --base origin/main
   claude plugin validate . && claude plugin validate .claude-plugin/plugin.json
   ```
5. Open a pull request.

Guidance in the skill should trace to the official docs at
[docs.typesafe.ai](https://docs.typesafe.ai). Where a source disagrees with the
docs, the docs win. Claims that come from elsewhere are marked as relayed.

## Attribution

- The doctrine and recipes build on *Jev Engineering: Typed Decision Systems for
  Reliable Agent Workflows* by Av1dlive (2026), from
  [codejunkie99/jev-engineering](https://github.com/codejunkie99/jev-engineering).
  That paper is published without a license. It is credited here, and this
  repository will follow its author's wishes.
- API facts come from the official TypeSafe documentation at
  [docs.typesafe.ai](https://docs.typesafe.ai).
- One decomposition result in `question-design.md` is relayed, marked as such, from
  [LMSpedia](https://lmspedia.org/how-to-write-jev-questions/).

## License

[MIT](LICENSE) © 2026 Mark Jedrzejczyk. The MIT license covers this repository's own
work and grants no rights to third-party material cited above.
