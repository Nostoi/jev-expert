---
name: jev-engineering
description: >
  Engineering discipline for putting TypeSafe Jev (System One) decisions into real
  software safely: choosing the insertion point, off/shadow/active rollout, keeping
  API failures distinct from negative answers, versioning questions and thresholds,
  decision logging, retry and side-effect safety, outcome verification, and
  evaluation. Use this whenever you are adding Jev or the TypeSafe API to an existing
  codebase, replacing an LLM prompt-and-parse step or a brittle classifier with Jev,
  auditing or debugging a Jev-assisted decision, or preparing a Jev integration for
  rollout — even if the user only says "use Jev here" or "wire up TypeSafe". Pair it
  with the official typesafe-ai skill, which owns the API contract and question design.
---

# Jev engineering

Jev answers typed questions about supplied state. That is the easy part. The
integrations that fail do so around the call: a timeout that quietly becomes "no
problem found", a threshold copied from a demo, a retry that sends a message twice,
a shadow mode that performs the action anyway. This skill covers that surrounding
engineering. It is distilled from *Jev Engineering: Typed Decision Systems for
Reliable Agent Workflows* (Av1dlive, 19 Sep 2026).

## Division of labour with the official skill

The official **typesafe-ai** skill (plugin `typesafe@typesafe-ai`) and the live docs
at https://docs.typesafe.ai own everything about the API: request and response
fields, question types, criteria wording, confidence semantics, models, limits, SDKs.
Load that skill and read the live pages it points to before writing request code;
do not reconstruct the API from memory or from this file. If the official skill is
not installed, say so and read https://docs.typesafe.ai/llms.txt directly.

Community material (blog posts, third-party cookbooks) is often stale or wrong about
the contract. For example, one popular cookbook shows a `confidence` field on Noul
answers and recommends fixed universal thresholds; the official docs say Noul answers
carry no confidence and thresholds must be set per workload. When sources disagree,
the live docs win.

This skill owns what happens around the call.

## The decision loop

Design every integration as five separately testable parts:

1. **State builder** – turns an observation into compact, provenance-bearing state.
2. **Typed decision** – one Jev request (via the SDK or HTTP) plus response validation.
3. **Policy** – deterministic code mapping validated answers to known application
   outcomes, including "review", "not checked", and the existing fallback.
4. **Executor** – performs side effects, owns retries and idempotency.
5. **Verifier** – reads the resulting state and checks the user's actual goal.

Jev is not the loop controller. It supplies a judgment; code decides what that
judgment is allowed to do. Keeping the parts separate is what lets you test each
failure mode offline and tell, when something goes wrong, which layer failed.

## Choose the insertion point first

A good first insertion point has: clear inputs the application already holds, a
small known set of outcomes, an existing path to fall back on, and some way to tell
afterwards whether the decision was right. Inspect the repository for the real
decision site (the dispatcher, the classifier, the prompt-and-parse call) before
proposing anything. If several candidates exist, rank them by usefulness, available
evaluation data, and effort, and build one. A narrow change is measurable against
the path it replaces; a rewrite that changes model, retrieval, and UX at once is not.

Leave to code anything code can do exactly: arithmetic, counting, dates, lookups,
permission and ownership checks, budgets, exact dedup. Jev's documented weak spots
(see the jaggedness page for the model version in use) include several of these.

## Failure is not a negative answer

This is the most common and most damaging mistake. Give the result type an explicit
status that cannot be confused with a judgment, for example:

- `decided` – a validated answer the policy can use
- `not_checked` – with a reason: `api_error`, `timeout`, `rate_limited`, `auth`,
  `invalid_response`, `missing_evidence`, `disabled`
- `review` – a valid answer the policy routes to a human or the existing path

A failed fetch, an empty document, a 5xx, or a malformed body must land in
`not_checked`, and `not_checked` must route to the existing behaviour or a visible
"not checked" state. It must never produce "safe", "pass", "no match", or a default
category. Write a test for each of these paths; they are the ones that break silently.

Validate the response before the policy reads it: every requested answer present,
correct type, finite numbers, choice keys drawn from the criteria you sent, score
within range. Validation catches contract problems. It says nothing about whether
the judgment is right.

## Keep authority in code

Relevance is not permission. A confident "execute" interpretation does not replace
the product's authorization record, and a selected "done" option does not prove the
work completed. Filter candidates mechanically (availability, access, budget,
capability) before asking Jev to choose among them, and re-check current conditions
before acting, because they can change while the request is in flight. Bind each
decision to the observation it was made on; if the target changed, re-evaluate.

## Rollout modes

Put the integration behind a mode switch that uses the project's existing
configuration mechanism, defaulting to **off**:

- **off** – existing behaviour, no Jev call.
- **shadow** – call Jev and record what it *would* have done alongside what the
  existing path actually did. Shadow mode must not perform the business action a
  second time and must not change user-visible behaviour. Record shadow failures too,
  or the quality report silently drops the hard cases. Use the evidence available at
  decision time; evaluating later, richer state makes the comparison unfair.
- **active** – the validated decision drives the branch, for an explicitly enabled
  slice, with the existing path as fallback.

Test the switch in all three positions, including that turning active back to off
restores the old behaviour.

## Retries and side effects

There should be one retry owner. The official SDKs already retry 429 and 529
responses with backoff by default; wrapping the SDK in another retry loop multiplies
attempts and latency. Decide which layer retries, and give the whole decision a total
deadline.

Model-call retries and business-action retries are different things. If a transport
error happens after a mutation may have occurred, do not blindly repeat it: use the
system's idempotency key, or read fresh state first.

## Make it reviewable

Humans review Jev code mainly by reading the questions and thresholds, so put all
question definitions, criteria, thresholds, and a question-set version in one file.
Treat any change to question wording, model, language, or document type as a new
evaluation event: rewording what "supported" means changes the task and invalidates
old thresholds.

**Model version.** Aliases such as `jev-latest` move when a new release ships, so the
answers behind them can change without any change on your side. The models page
advises pinning the versioned ID once thresholds have been tuned against it. In
practice: an alias is fine while exploring or in shadow mode; pin before thresholds
are tuned on real data or the decision goes active, and say which you chose and why.
Copy the exact versioned ID from the live models page (`/models.md`); never guess or
shorten one. Whichever you send, log the `model` field every response returns, since
that is the only record of which model actually answered.

For each decision, log through the existing logging system: event ID, requested and
returned model, question-set version, policy version, latency, token usage, the
branch taken, and the fallback reason if any. Keep enough to reproduce the branch
without creating an uncontrolled second copy of sensitive content. Include the
evidence identity, question version, and model version in any cache key.

## Question quality

Wording is where most semantic errors start, and agents are not naturally good at
writing Jev questions. Run the static review in `references/question-design.md` on
every question you write, and on the existing questions of any integration you
modify, audit, or prepare for rollout, even when the task is about something else.
A missing "none of these" option or a Noul asking about degree is a defect in its own
right, not a style note. Report the findings and the fixes you made.

The reverse does not hold. When the user asks only to review the questions
themselves, report findings only about the question definitions, the state each one
reads, how they are grouped into requests, and how the code reads the answers. Say
what you did not review and offer to, without asserting defects there. If you
delegate to the reviewer agent, ask it for a question review. This does not apply
to a report of a wrong, missed, or suspicious decision: that is an audit — follow
the audit workflow in `references/workflows.md` — whatever cause the user suspects.

## Credentials

Keep API keys out of logs, test output, and your own transcript. To check whether a
key is configured, test for presence without revealing it (for example
`[ -n "$TYPESAFE_API_KEY" ] && echo set`, or list variable names with
`env | cut -d= -f1`). Never run `env`, `printenv`, or `echo` on a credential variable.
Tests should remove key variables from the environment so they cannot reach the
live API by accident.

## Evidence and honesty

Offline fixtures with recorded or synthetic responses test the plumbing: validation,
policy mapping, failure routing, modes. They do not measure whether Jev answers well.
Say so explicitly: report model accuracy as **unmeasured** until labelled,
representative inputs have been evaluated, and do not call paid APIs or change
production traffic without the user's authority.

When you justify a choice by citing a docs page, attribute to it only what it
actually says, quoting where you can. A plausible rule credited to the wrong source
misleads the reviewer who trusts the citation.

Thresholds in examples, cookbooks, and this skill are starting points to evaluate,
not settings to ship. When the answer is "pick the best option", use the highest
probability; reach for a confidence threshold only where the decision has a real
act/escalate split, and set it from the measured trade-off between automation
coverage and error on the user's own data.

## What to deliver

For an implementation task, finish with a short integration note covering: where Jev
now sits and what it replaced, the bounded decision and its fallback, the modes and
how to switch them, the model version choice, the question review findings, what the
tests cover, what is still unmeasured, and the evaluation needed before enabling
active mode.

## Reference files

Read these when the task calls for them:

- `references/workflows.md` – step-by-step checklists for the three task shapes:
  implementing an integration, auditing a failed decision, and preparing a rollout.
  Read the matching section at the start of any of those tasks.
- `references/question-design.md` – a static checklist for reviewing Jev questions
  (no API calls) and a live procedure for testing them against labelled examples.
  Read it whenever you write, change, audit, or ship questions.
- `references/evaluation.md` – how to evaluate a Jev decision: splits, baselines,
  coverage vs selective error, critical misses, failure taxonomy by layer.
  Read when designing an evaluation or writing the go/no-go report.
- `scripts/question_eval.py` – runs the live question test: labelled examples and
  one or more question-set variants in, per-question accuracy, confusion,
  near-threshold and high-confidence errors, and run-to-run stability out. Dry-run
  by default (prints the call count); `--live` needs `--model`, `--max-calls`, and
  the user's go-ahead. Run it with `--help` for input formats.
- `references/recipes.md` – proposed designs for twenty-one common insertion points
  (handler routing, model routing, UI action selection, memory filtering, citation
  checks, CI policy checks, research screening, rubric scoring of another system's
  output, support intake, and more), each with
  required evidence, questions, traps, and measures. Read the matching recipe when
  the task resembles one.
