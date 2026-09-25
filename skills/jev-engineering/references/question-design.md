# Reviewing Jev questions

Jev answers the question you wrote, not the one you meant, so the wording of each
question is where most semantic errors start. This file has two parts: a review you
can do by reading the questions (no API calls), and a live test that measures how
they actually behave (needs API calls and labelled examples).

Every rule below comes from the official docs, cited by page. Page paths are
relative to https://docs.typesafe.ai and serve Markdown with `.md` appended. The
jaggedness page is version-specific; re-read it for the model version in use.

## Contents

1. Static review checklist
2. Live question test
3. Reporting a review

---

## 1. Static review checklist

Run this on every question you write or inherit. Each item is a yes/no check; a
"no" is a finding.

### A. Should Jev answer this at all?

- **No arithmetic, counting, or numeric comparison.** Code computes exact values;
  Jev is "not a calculator" and "does not count reliably". To count items matching a
  condition, ask one question per item and add up in code. (`/model-jaggedness/jev-1.13`)
- **No date ordering, durations, or window checks.** Extract date parts (a Choice
  per part, with a "not stated" option) and compare in code. (`/model-jaggedness/jev-1.13`)
- **No free-text generation or open extraction.** Find candidates with a regex,
  parser, or generative model, then have Jev select among them. (`/model-jaggedness/jev-1.13`)
- **Prefer semantic over raw numeric representations** (a named bucket rather than a
  hex code or raw figure). (`/model-jaggedness/jev-1.13`)
- **A snap judgment.** Something a knowledgeable person decides in about a second given
  the context. "Analyze this and decide what to do" is a sign to split the task. (`/primitives`)

### B. Right question type

- **Choice** for one of a known set with no order; **Score** for a position on a
  spectrum whose levels you can describe; **Noul** for a clean yes/no where the
  probability is the useful signal. (`/primitives`)
- **Not a Noul for degree.** A Noul value of 0.5 means yes and no are equally likely,
  not "medium". "Is the candidate strong in Python?" wants a Score with defined
  levels, or a Noul with a precise condition. (`/primitives`, `/primitives/noul`)
- **Not a Score when there's no in-between.** Discrete categories belong in a Choice
  or several Nouls. (`/primitives/score`)
- When two types fit, prefer the one the code can act on directly. (`/primitives`)

### C. Instructions

- **Complete on its own.** Question IDs are not sent to the model; the full meaning
  must be in `instructions`. (`/primitives`)
- **One judgment.** No "and" joining two conditions ("angry and asking for a
  refund"); split and combine in code. (`/primitives/noul`)
- **Literal and exact.** Scoping words, negations, and implied conditions are read at
  face value. State the exact condition; if you find yourself explaining what you
  "really meant", that explanation belongs in the instruction or criteria.
  (`/model-jaggedness/jev-1.13`)
- **Direct.** No double negatives, no property-of-a-property, no multi-hop reasoning.
  (`/model-jaggedness/jev-1.13`)
- **High means yes** (Noul). "Does the message contain personal data?", not "Is the
  message free of personal data?". (`/primitives/noul`)
- **Points at the right part of state.** With structured state, name the field by a
  backticked path such as `ticket.messages[0].text`. (`/primitives`)

### D. Choice criteria

- **Full option list.** Give every team, category, or product, not a shortlist; up to
  255 options. (`/primitives/choice`)
- **A no-match option** (`other`, `none of the above`) whenever the list might not
  cover every input, so the model can say none of the others fit.
  (`/primitives`, `/primitives/choice`) Every answer is constrained to the options
  supplied (`/primitives`), so without one an unfit input still lands on some option.
- **Descriptions separate the options.** Option names and descriptions are both sent.
  For options that get confused, use an object per option with what it covers, what
  belongs to a neighbour instead (`not_for`), and a few examples. Field names are
  yours and visible to the model. (`/primitives/choice`)

### E. Score levels

- **Situations, not degrees.** "Broken feature, but a workaround exists", not
  "moderately severe". (`/primitives/score`)
- **Each level stands alone.** Levels are judged separately; the model does not see a
  level's number or neighbours, so "worse than the previous level" or numeric labels
  carry no meaning. (`/primitives/score`)
- **One dimension.** "Punctual and smart and experienced" is three questions.
  (`/primitives/score`)
- **2–10 levels, each distinct.** Don't add levels you can't describe distinctly.
  (`/primitives/score`)
- **A separate level for a rare extreme you act on differently** (for example
  "abusive or threatening" above "very angry"). (`/primitives/score`)
- **Code uses the score correctly.** Normalize by `len(criteria) - 1` before
  weighting across scales; threshold it, but don't interpolate exact magnitudes
  between levels. (`/primitives/score`, `/model-jaggedness/jev-1.13`)

### F. Noul criteria

- Optional; add `true` and `false` descriptions when the boundary is subtle.
  (`/primitives/noul`) Words like "urgent", "serious", or "at risk" leave the
  boundary to the model's reading; when a code path depends on the answer, state
  what counts as yes and what counts as no, then keep whichever version answers
  your labelled examples better (the docs advise trying with and without).
- **Aligned with the instruction.** A Noul whose `true` maps to "no" performs worse;
  instructions and criteria must ask the same thing. This applies to every type.
  (`/model-jaggedness/jev-1.13`)

### G. State for the question

- **Only what the question needs.** Unrelated material lowers accuracy; filter in code
  first. (`/model-jaggedness/jev-1.13`)
- **Named fields** in an object when the state has several parts; content in state,
  judgments in questions. (`/concepts/state`)
- **Verified facts kept separate from user assertions and quoted text**, so the
  question can refer to the right one. (A support ticket saying "Enterprise" is not
  the account's plan.)
- **Language.** English is the primary training language; others are handled with
  lower accuracy and need testing. (`/concepts/state`, `/models`)
- **Hostile content can move answers.** State is not treated as adversarial; be
  explicit in criteria and test injected or self-classifying text.
  (`/model-jaggedness/jev-1.13`)

### H. Composition

- **Independent questions over the same state go in one request**, including
  speculative ones the code may ignore. (`/primitives`)
- **A second request only when code can't build it without the first answer** (to
  fetch evidence, construct new state, or pick the next options). (`/primitives`)
- **No identities assumed between questions.** A Noul and its negation needn't sum to
  1; a Noul and a yes/no Choice answer differently. Don't move a threshold tuned on a
  Noul to a Choice. (`/model-jaggedness/jev-1.13`)

---

## 2. Live question test

A static review finds ambiguity; only data shows accuracy. This needs API calls, so
get the user's go-ahead and state the expected call count and cost first. Pin the
versioned model ID.

`scripts/question_eval.py` automates steps 2–4: give it the labelled examples as
JSONL and each wording variant as a questions file. Run it without `--live` first to
get the call count to show the user.

1. **Labelled examples.** Collect real inputs with the expected answer for each
   question, written down before running. Include clear cases, boundary cases, inputs
   that fit no option, and challenge cases built from the jaggedness failure modes
   (literal-reading traps, numbers, dates, indirection, distracting context, injected
   instructions). Keep some examples aside for a final check.
2. **Accuracy.** Compare answers with labels: a confusion matrix for Choice (watch the
   no-match option), errors near the threshold for Noul, errors between neighbouring
   levels for Score. Two patterns point at the wording rather than the model: a flat
   distribution across options (unclear criteria or state too thin to decide, per
   `/primitives/score` for Scores), and high confidence alongside middling agreement
   with your labels (criteria clear enough to commit to but not drawing the
   distinction you intend; rewrite the criteria).
   Record every component answer, not only a combined score, so a later change of
   weights or combination rule can be re-run without calling the model again.
3. **Variant comparisons.** Change one thing at a time and re-run the same labelled
   set: a reworded instruction, with and without Noul `criteria`, string vs object
   option descriptions, reordered Choice options. Keep the variant that is more
   accurate. Higher confidence alone does not show a wording is better; examples
   added to levels help only when they resemble real inputs, so test revisions on
   examples you did not tune them on. (`/primitives/score`, `/primitives/noul`)
4. **Run-to-run stability.** Repeat identical requests. TypeSafe's self-consistency
   cookbooks add a throwaway unique field to state each run so repeats aren't served
   from cache (per `/cookbooks/consistency_choice_cookbook`), and show answers close
   to a threshold can flip between runs. Values that sit near a decision threshold
   belong in an explicit uncertain / review band rather than being forced to one side.
5. **Decomposition test.** When a compound judgment underperforms, compare it with
   the same decision split into one question per signal, combined in code. With
   enough labelled data, fit the combination (for example a logistic regression) on
   one split and score it on another rather than hand-picking weights. One
   practitioner write-up reports a phishing benchmark moving from 62.6% on a single
   compound question to 95.0% with five atomic questions plus a fitted combiner
   (relayed from lmspedia.org/how-to-write-jev-questions, 2026-09-22; the
   underlying study was not reviewed here). Treat it as a reason to run the
   comparison, not as an expected gain.
6. **Record** model ID, question-set version, and results, so a later wording change
   can be compared against this baseline.

---

## 3. Reporting a review

For each question, list only the findings: the question ID, the checklist item, what
the problem is in this question, and the proposed rewrite. Then note which questions
passed without findings, and state plainly that the static review does not measure
accuracy: say whether a live test has been run and on how many labelled examples.
