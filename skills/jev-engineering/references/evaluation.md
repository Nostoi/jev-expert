# Evaluating a Jev decision

The question an evaluation answers is whether the whole workflow improves at the
required quality, not whether a single call is fast or cheap.

## Separate the judgment from its consequence

For each event keep three things: the evidence available at decision time, a
reference label from an identified source (a human, an adjudicated rubric), and the
eventual workflow outcome. A correct route can still end in failure and a wrong
route can succeed by accident; one combined "success" field hides which happened.

## Data splits

- A development split for iterating on wording, candidates, and policy.
- A held-out split used once, for the final assessment. Once its failures guide
  tuning, it is no longer held out.
- Group near-duplicates and related entities so they don't straddle splits. For a
  process that runs over time, testing on later events is usually more realistic
  than a random split.

## Baselines

Compare on identical eligible inputs and completion criteria against: the existing
application path; a simple deterministic rule where one is plausible; and an LLM
structured classifier if that is the real alternative. Record model IDs, settings,
retries, concurrency, question versions, prices, and cache state. Compare against the
best existing implementation, not an artificially serialized one.

## Units

Decide the unit before computing a percentage. Twenty questions over one document is
one document; ten actions in one task is one task. Errors within one source or
session are correlated and are not independent evidence.

## Measures

| Measure | Denominator | Why |
|---|---|---|
| Overall decision quality | all eligible labelled events | includes hard and failed cases |
| Automatic coverage | all eligible events | how much work the policy actually takes on |
| Selective error | automatically handled events | risk carried by the automated decisions |
| Critical-miss rate | actual critical cases | failures hidden by class imbalance |
| Tail latency | complete workflow attempts | slow paths and retries |
| Cost per accepted outcome | all costs / accepted completions | ties inference cost to value |

If nothing is automated, selective error is undefined, not zero. A policy that
escalates nearly everything can show low error and little value, so always report
review burden alongside it.

Setting a threshold means choosing a point on the coverage vs selective-error curve
for this workload. Plot or tabulate it from the development split; do not import a
number from a demo, another workload, or another model version.

For probabilities, compare predicted ranges with observed frequencies and report a
proper score such as the Brier score (mean squared probability error); small bins
are weak evidence. For Choice, inspect the confusion matrix and no-match behaviour.
For Score, look at errors near the threshold and at disagreements about the rubric
itself.

## Whole-workflow speed

If the decision is fraction f of end-to-end time and becomes r times faster, the
workflow speeds up by 1 / ((1 − f) + f / r). A 100× faster decision that was 40% of
the time gives about 1.66× overall. Measure end to end; better routing can also save
downstream work, and wrong routing can add retries.

## Failure taxonomy

Classify each failure by the layer that caused it and fix that layer: missing
source, wrong retrieval, omitted candidate, unclear question, task that code should
have done (arithmetic, counting, dates), semantic error, conflicting answers, stale
state, invalid response, provider failure, policy bug, execution failure, disputed
reference label. Adding another question does not fix an authorization bug or a
missing source.

Use the jaggedness page for the model version in use to build challenge cases (the documented weak
spots include arithmetic, counting, dates, literal interpretation, indirection,
distracting context, hostile input, and contradictory criteria). A documented
mitigation is a hypothesis until it works on this workload.
