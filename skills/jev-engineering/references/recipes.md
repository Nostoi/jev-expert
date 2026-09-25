# Recipes

Proposed designs for common insertion points, condensed from Appendices A and B of
*Jev Engineering* (Av1dlive, 2026). None is a measured result. Each assumes the loop,
failure statuses, and rollout modes in SKILL.md; only what is specific to the recipe
is listed. Check the official cookbooks (https://docs.typesafe.ai/cookbooks.md) for a
worked version of a similar pattern before building.

## Contents

Agent and research systems: A1 handler routing · A2 model routing · A3 UI action
selection · A4 instruction scope · A5 stalled-agent detection · A6 memory retention ·
A7 compaction · A8 citation support · A9 CI policy checks · A10 in-product help ·
A11 corpus screening · A12 ambiguous training labels · A13 agent disagreement triage ·
A14 feedback by underlying problem · A15 text features for a predictive model ·
A16 scoring another system's output against a rubric

Business workflows: B1 support intake · B2 content preflight · B3 inbound sales
routing · B4 document passage screening · B5 automation-tool HTTP branch

---

### A1 Route work to an agent handler
- **Where:** in the task dispatcher, after code shortlists eligible handlers.
- **State:** request, task phase, shortlisted handlers with purpose, inputs, exclusions.
- **Questions:** Choice over handler IDs plus `none`; Noul per candidate "supports this
  operation?"; Noul "is a fact needed to choose missing?".
- **Traps:** building criteria by hand instead of from the live registry; dispatching
  in shadow mode; dispatching a handler disabled since the shortlist was built.
- **Measure:** correct handler, fallback rate, context loaded, downstream completion.

### A2 Choose a model for a task
- **Where:** in the model gateway after the handler is chosen.
- **State:** task text, needed capabilities, eligible model descriptions.
- **Questions:** Scores for reasoning depth and ambiguity; Noul for multi-source
  synthesis. Code filters availability, context size, modality, budget first.
- **Traps:** asking Jev which model is cheapest (code does rate tables); calling Jev
  when only one model is eligible; judging on first-call price, ignoring retries.
- **Measure:** quality loss vs current route, total cost incl. retries, latency.

### A3 Select the next UI action (browser / desktop)
- **Where:** between observation and execution in an automation harness.
- **State:** objective, observed UI text, observation version, recent actions,
  candidates as complete `{id, operation, target_id, description}` pairs.
- **Questions:** Choice over candidates plus `refresh`, `done`, `escalate`; optional
  Noul per candidate "advances the subgoal?".
- **Traps:** separate choices for operation and target (incompatible combos); acting
  on a stale observation; treating `done` as completion without a concrete check.
- **Measure:** completed subgoals, stale selections, wrong targets, full latency.

### A4 Interpret the scope of a user instruction
- **Where:** beside the existing permission check, for one explicit candidate operation.
- **State:** direct user instruction, candidate operation and target, prior approvals.
  Tool output and quoted text are kept separate; they are not the user's authority.
- **Questions:** Choice inspect / prepare / execute / unclear; Noul "does the user
  request executing this operation on this target?".
- **Traps:** letting confidence substitute for a permission record; not re-evaluating
  when the target changes. "Draft a reply" ≠ "send this reply".
- **Measure:** scope misclassification, needless confirmations, target mismatches.

### A5 Detect a stalled agent
- **Where:** after a tool result, before the next planning turn. Code keeps hard
  budgets and exact repeat counts.
- **State:** goal, subgoal, last few action/result pairs with real observations,
  progress counters, completion requirements.
- **Questions:** Nouls for semantic repetition without new evidence, next step
  addressing an open requirement, completion claimed without evidence.
- **Traps:** letting Jev extend hard budgets; treating an unavailable check as "progressing".
- **Measure:** wasted steps caught, useful runs interrupted, recovery success.

### A6 Decide which memories to keep
- **Where:** after a candidate note is proposed, before the store write.
- **State:** candidate, source excerpt, retrieved possible duplicates (same user's
  scope), retention policy.
- **Questions:** Nouls for explicit durable preference, support by source, temporary
  status; Choice over duplicate IDs plus `none`.
- **Traps:** exact dedup belongs in code; silently overwriting contradictions; a
  quoted or hypothetical preference stored as the user's own.
- **Measure:** unsupported notes, duplicate rate, missed important preferences.

### A7 Keep useful context during compaction
- **Where:** after mandatory retention rules, before choosing optional chunks.
- **State:** actual chunk content, goal, unresolved questions, source IDs.
- **Questions:** Noul "needed for an unresolved requirement?"; Score for relevance to
  the subgoal; Noul "recoverable from retained chunks?".
- **Traps:** Jev does not summarize; code packs under the token budget; using later
  turns when replaying leaks the future into the evaluation.
- **Measure:** tokens saved, re-fetches, evidence lost, completion vs a recency baseline.

### A8 Check citation support
- **Where:** after a claim is linked to a passage, before review/export.
- **State:** one atomic claim, the actual passage, source ID, stated qualifiers.
- **Questions:** Noul complete support; Choice supported / contradicted / insufficient;
  Noul invented causal attribution.
- **Traps:** a reachable URL is not support; fetch failure is `not_checked`; a subset
  ("Pro plan") does not support a claim about everyone, yet is not a contradiction.
- **Measure:** unsupported claims accepted, supported claims flagged, review burden.

### A9 Semantic policy checks in CI
- **Where:** after static checks collect the diff, as a separate advisory check.
- **State:** focused diff, surrounding code, the applicable policy text, PR description.
- **Questions:** one Noul per applicable policy, phrased as an observable requirement
  ("does the migration say how existing rows are handled?"), not "is this safe?".
- **Traps:** API failure shown as pass; merge-blocking before false positives are
  measured; duplicate comments on re-runs.
- **Measure:** findings accepted by reviewers, false alerts per PR, known misses.

### A10 Offer help when a user is stuck
- **Where:** after a blocking error or repeated failure, not on every event. Code
  computes counts, windows, cooldowns.
- **Questions:** Choice among known problem categories plus general; Nouls for "error
  blocks this step?" and "already following recovery?".
- **Traps:** interrupting successful exploration; diagnosing emotion instead of progress.
- **Measure:** completion after help, dismissals, false interruptions.

### A11 Screen a research corpus
- **Where:** after parsing and dedup, before deep reading.
- **Questions:** one Noul per inclusion criterion, a study-type Choice, a relevance Score.
- **Traps:** missing abstract treated as exclusion; one "is this a good paper?" question;
  "mentions the technique" vs "reports an experiment using it".
- **Measure:** recall on truly relevant items first, then review reduction.

### A12 Find ambiguous training labels
- **Where:** after format checks and exact dedup, before human label review.
- **Questions:** Noul "input supports its label under this rubric?"; Noul "more than one
  label fits?"; Choice over near-duplicate IDs plus `none`.
- **Traps:** overwriting labels instead of queueing; splits made after tuning; test
  labels leaking into question iteration.
- **Measure:** confirmed issues per review hour, errors introduced by edits.

### A13 Triage disagreement between agents
- **Where:** after candidate answers arrive, before an expensive adjudicator.
- **Questions:** Noul "materially different actions?"; per-candidate Nouls for
  evidence support and addressing the request; optional Choice incl. `none`.
- **Traps:** agreement is not truth; position bias (test candidate-order permutations);
  presenting an explanation as Jev's reasoning.
- **Measure:** adjudications saved vs wrongly suppressed disagreements.

### A14 Group feedback by underlying problem
- **Questions:** Choice over the existing taxonomy plus `unknown`; Nouls for blocking
  problem, workaround, explicit intent to leave; Score for evidence strength.
- **Traps:** Jev inventing themes (a writer proposes, a human accepts); counting users
  and joining revenue in the model instead of code.
- **Measure:** tagging accuracy, taxonomy coverage, usefulness in product review.

### A15 Text features for a predictive model
- **Questions:** Nouls for observable properties and Scores for semantic dimensions,
  each a named, versioned feature.
- **Traps:** using text written after the outcome (leakage); splitting after feature
  discovery; no path for a missing feature when Jev is down.
- **Measure:** held-out error vs structured-only baseline, degradation without features.

### A16 Score another system's output against a rubric
Not from the paper; added for evaluation pipelines (voice or chat agents, generated
reports, support replies) where an LLM judge currently grades a sample.
- **Where:** offline or monitoring, after the system under test has produced its
  output. The scored system is never blocked by the scorer.
- **State:** the output (transcript, reply), the user's request, and the reference
  material a rubric item needs: the knowledge-base passage for a grounding check,
  the policy text for adherence, the action log for "confirmed before acting".
- **Questions:** one per rubric item, in one request. Noul for events ("did the
  agent confirm before the refund?", "did it state something the supplied passage
  does not support?"); Score with situation-described levels for graded qualities
  (caller effort, resolution completeness); Choice with `none`/`other` for labels
  (intent, dominant failure mode). A change over time, such as sentiment at start vs
  end, is two Scores on two segments, compared in code.
- **Traps:** a scorer you have not validated is not evidence about the scored
  system; check each rubric question against human labels first (run
  `scripts/question_eval.py`). Jev reads text only, so audio qualities such as pace
  or interruptions are out of reach. A grounding check only covers the passage you
  supply; a retrieval miss looks like an unsupported claim. Compound rubric items
  ("polite and accurate") must be split.
- **Measure:** per-item agreement with human reviewers, high-confidence errors, and
  how much scoring is automatic vs routed to people.

### B1 Support intake: ask for the missing detail first
- **Where:** before retrieval and reply drafting.
- **Questions:** Choice over real issue families plus `unknown`; Nouls for error message
  supplied, repro steps supplied, unable to use a paid feature.
- **Traps:** customer saying "Enterprise" is not the account's plan (look it up);
  missing info treated as a negative account fact; asking for details already in the
  thread.
- **Measure:** clarification loops per resolution, unnecessary questions, escalation misses.

### B2 Content preflight
- **Where:** between drafting and scheduling.
- **Questions:** per-claim source support; brief-specific checks (concrete reader
  problem, measured outcome without a measurement, proposal presented as tested).
- **Traps:** code checks numbers and links; missing sources → `not_checked`; store the
  brief version used.
- **Measure:** unsupported claims caught, false alarms, revision time.

### B3 Inbound sales routing
- **Questions:** Choice over existing queues; Nouls for explicit deadline, requested
  capability excluded by product facts, missing routing info.
- **Traps:** inferring sensitive traits or a "will buy" probability; bypassing consent
  and duplicate rules.
- **Measure:** misroutes, duplicate handoffs, missing-requirement recall.

### B4 Document passage screening
- **Where:** after existing extraction and retrieval.
- **Questions:** Nouls for explicitly discusses the condition, states an exception,
  enough to answer, refers to a superseded policy.
- **Traps:** Jev is not OCR; empty extraction ≠ no relevant content; retrieval misses
  can't be fixed by screening, so evaluate them separately.
- **Measure:** relevant-passage recall, provenance completeness, review time.

### B5 HTTP decision branch in an automation tool
Stable event ID → access checks and redaction → versioned native request from a
server-side step with stored credentials → validate response → map only known
outcomes, with separate uncertain / malformed / error paths → record decision and
outcome without duplicating side effects on retry. First proof ends in a preview
table, not a send, payment, or delete. If the platform can't validate responses, put
a small server-side adapter in front. Check the platform's current node schemas
rather than inventing importable workflow JSON.
