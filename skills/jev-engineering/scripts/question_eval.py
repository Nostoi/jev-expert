#!/usr/bin/env python3
"""question_eval.py -- live-test a set of TypeSafe Jev questions against labelled examples.

Measures how well one or more wording variants of a Jev question set answer a set
of labelled examples, and (with --repeats > 1) how stable the answers are across
identical repeated calls. See skills/jev-engineering/references/question-design.md
part 2 for the methodology this implements.

Usage:
    question_eval.py --examples FILE.jsonl --variant NAME=QUESTIONS.json
                      [--variant NAME=FILE ...]
                      [--model MODEL] [--repeats N] [--noul-threshold 0.5]
                      [--out DIR] [--live --max-calls N]

Without --live: validates inputs, prints the plan, and makes no network calls (and
writes no files). With --live: calls TypeSafe's systemone endpoint (base URL from
TYPESAFE_BASE_URL, default https://api.typesafe.ai; key from TYPESAFE_API_KEY) and
writes answers.jsonl, report.json and report.md under --out.

Questions file: a JSON object {qid: question} in the API's question shape.
Examples file: JSONL, one object per line: {"id": str, "state": <any JSON>,
"labels": {qid: expected}}.
"""

import argparse
import functools
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ALIASES = {"jev-latest", "jev-preview"}
_MISSING = object()

# Patched by tests; also lets a future backoff tweak live in one place.
_sleep = time.sleep


class ApiError(Exception):
    """Raised by an HTTP call function; status is None for transport-level errors."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class InputError(Exception):
    """Raised for a validation problem; str(e) is the ready-to-print message."""


# --------------------------------------------------------------------------- #
# Input loading and validation
# --------------------------------------------------------------------------- #


def load_questions(path):
    """Load and validate a {qid: question} JSON file. Raises InputError."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"{path}: cannot read questions file: {exc}") from exc
    if not isinstance(data, dict):
        raise InputError(f"{path}: questions file must be a JSON object of {{qid: question}}")
    for qid, question in data.items():
        if not isinstance(question, dict) or "type" not in question:
            raise InputError(f"{path}: qid={qid}: question must be an object with a type")
        qtype = question["type"]
        if qtype not in ("noul", "choice", "score"):
            raise InputError(f"{path}: qid={qid}: unknown type {qtype!r}")
        if qtype == "choice":
            criteria = question.get("criteria")
            if not isinstance(criteria, dict) or not criteria:
                raise InputError(f"{path}: qid={qid}: choice criteria must be a non-empty object")
        elif qtype == "score":
            criteria = question.get("criteria")
            if not isinstance(criteria, list) or not (2 <= len(criteria) <= 10):
                raise InputError(f"{path}: qid={qid}: score criteria must be a list of 2-10 entries")
        # noul criteria is optional and unconstrained beyond that.
    return data


def load_variants(variant_args):
    """Parse --variant NAME=FILE arguments into {name: {qid: question}}."""
    variants = {}
    for item in variant_args:
        if "=" not in item:
            raise InputError(f"--variant must be NAME=FILE, got {item!r}")
        name, _, file_path = item.partition("=")
        if not name:
            raise InputError(f"--variant must be NAME=FILE, got {item!r}")
        variants[name] = load_questions(file_path)
    return variants


def _validate_label(path, lineno, variant_name, qid, question, label):
    qtype = question["type"]
    if qtype == "noul":
        if not isinstance(label, bool):
            raise InputError(
                f"{path}:{lineno}: variant {variant_name} qid {qid}: "
                f"noul label must be true/false, got {label!r}"
            )
    elif qtype == "choice":
        if not isinstance(label, str) or label not in question["criteria"]:
            raise InputError(
                f"{path}:{lineno}: variant {variant_name} qid {qid}: "
                f"unknown option key {label!r}"
            )
    elif qtype == "score":
        k = len(question["criteria"])
        if isinstance(label, bool) or not isinstance(label, int) or not (0 <= label <= k - 1):
            raise InputError(
                f"{path}:{lineno}: variant {variant_name} qid {qid}: "
                f"score level {label!r} out of range 0..{k - 1}"
            )


def load_examples(path, variants):
    """Load and validate the JSONL examples file against every variant's questions."""
    examples = []
    seen_ids = set()
    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise InputError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(obj, dict) or "id" not in obj or "state" not in obj:
                raise InputError(f"{path}:{lineno}: example must be an object with id and state")
            ex_id = obj["id"]
            if not isinstance(ex_id, str):
                raise InputError(f"{path}:{lineno}: id must be a string")
            if ex_id in seen_ids:
                raise InputError(f"{path}:{lineno}: duplicate example id {ex_id!r}")
            seen_ids.add(ex_id)
            labels = obj.get("labels", {})
            if not isinstance(labels, dict):
                raise InputError(f"{path}:{lineno}: labels must be an object")
            for qid, label in labels.items():
                for variant_name, questions in variants.items():
                    if qid not in questions:
                        continue  # a label for a qid a variant lacks is ignored for it
                    _validate_label(path, lineno, variant_name, qid, questions[qid], label)
            examples.append({"id": ex_id, "state": obj["state"], "labels": labels})
    return examples


def check_repeats_state(examples, repeats):
    """--repeats > 1 needs a JSON object state to carry the _eval_run cache-buster."""
    if repeats <= 1:
        return
    for example in examples:
        if not isinstance(example["state"], dict):
            raise InputError(
                f"--repeats > 1 requires object state; example {example['id']!r} "
                f"has {type(example['state']).__name__} state"
            )


def plan_calls(examples, variants, repeats):
    return len(examples) * len(variants) * repeats


# --------------------------------------------------------------------------- #
# HTTP transport
# --------------------------------------------------------------------------- #


def _retry_delay(exc, attempt):
    retry_after = None
    headers = getattr(exc, "headers", None)
    if headers is not None:
        retry_after = headers.get("Retry-After")
    if retry_after is not None:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return 2**attempt


def _redact(text, secret):
    if secret:
        text = text.replace(secret, "***")
    return text


def http_call(state, questions, model, *, base_url, api_key, timeout=30):
    """POST to {base_url}/v1/systemone, retrying 429/529 up to 3 times.

    Returns the parsed JSON response, or raises ApiError(status, message) --
    status is None for transport-level failures (network error, bad JSON).
    """
    url = base_url.rstrip("/") + "/v1/systemone"
    body = json.dumps({"model": model, "state": state, "questions": questions}).encode("utf-8")
    max_retries = 3
    retries = 0
    while True:
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw_body = exc.read()
            text = _redact(raw_body.decode("utf-8", "replace"), api_key)[:500]
            if exc.code in (429, 529) and retries < max_retries:
                _sleep(_retry_delay(exc, retries))
                retries += 1
                continue
            raise ApiError(exc.code, text)
        except urllib.error.URLError as exc:
            raise ApiError(None, _redact(str(exc.reason), api_key))
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ApiError(None, f"invalid JSON response: {exc}")


# --------------------------------------------------------------------------- #
# Answer validation
# --------------------------------------------------------------------------- #


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_answer(question, answer):
    """Return ("ok", value) or ("invalid", None). value is a small normalized dict."""
    if not isinstance(answer, dict):
        return "invalid", None
    qtype = question["type"]
    if answer.get("type") != qtype:
        return "invalid", None

    if qtype == "noul":
        noul = answer.get("noul")
        if not _finite_number(noul) or not (0 <= noul <= 1):
            return "invalid", None
        return "ok", {"noul": float(noul)}

    if qtype == "choice":
        choice = answer.get("choice")
        confidence = answer.get("confidence")
        if not isinstance(choice, str) or choice not in question["criteria"]:
            return "invalid", None
        if not _finite_number(confidence) or not (0 <= confidence <= 1):
            return "invalid", None
        probabilities = answer.get("probabilities")
        if not isinstance(probabilities, dict):
            probabilities = {}
        return "ok", {"choice": choice, "confidence": float(confidence), "probabilities": probabilities}

    if qtype == "score":
        score = answer.get("score")
        confidence = answer.get("confidence")
        k = len(question["criteria"])
        if not _finite_number(score) or not (0 <= score <= k - 1):
            return "invalid", None
        if not _finite_number(confidence) or not (0 <= confidence <= 1):
            return "invalid", None
        return "ok", {"score": float(score), "confidence": float(confidence)}

    return "invalid", None


def _round_half_up(x):
    return math.floor(x + 0.5)


def _decision(qtype, value, threshold):
    if qtype == "noul":
        return value["noul"] >= threshold
    if qtype == "choice":
        return value["choice"]
    return _round_half_up(value["score"])


# --------------------------------------------------------------------------- #
# Evaluation core
# --------------------------------------------------------------------------- #


def run_eval(examples, variants, *, model, repeats, noul_threshold, call):
    """Make the planned calls and compute metrics. `call` raises ApiError on failure."""
    calls = []
    records = {}  # (variant, example_id) -> {repeat_index: record}

    for variant_name, questions in variants.items():
        for example in examples:
            for repeat in range(repeats):
                state = example["state"]
                if repeats > 1:
                    state = dict(state)
                    state["_eval_run"] = uuid.uuid4().hex
                try:
                    resp = call(state, questions, model)
                    record = {
                        "variant": variant_name,
                        "example_id": example["id"],
                        "repeat": repeat,
                        "model": resp.get("model"),
                        "usage": resp.get("usage"),
                        "answers": resp.get("answers") if isinstance(resp.get("answers"), dict) else {},
                    }
                except ApiError as exc:
                    record = {
                        "variant": variant_name,
                        "example_id": example["id"],
                        "repeat": repeat,
                        "model": None,
                        "usage": None,
                        "error": {"status": exc.status, "message": (exc.message or "")[:500]},
                    }
                calls.append(record)
                records.setdefault((variant_name, example["id"]), {})[repeat] = record

    calls_failed = 0
    input_tokens = 0
    output_tokens = 0
    returned_models = set()
    for rec in calls:
        if "error" in rec:
            calls_failed += 1
            continue
        if rec["model"]:
            returned_models.add(rec["model"])
        usage = rec.get("usage") or {}
        input_tokens += usage.get("input_tokens", 0) or 0
        output_tokens += usage.get("output_tokens", 0) or 0

    metrics = {}
    for variant_name, questions in variants.items():
        metrics[variant_name] = {}
        for qid, question in questions.items():
            metrics[variant_name][qid] = _question_metrics(
                variant_name, qid, question, examples, records, noul_threshold, repeats
            )

    warnings = []
    if len(returned_models) > 1:
        warnings.append(f"multiple models returned: {sorted(returned_models)}")
    elif returned_models and model not in ALIASES:
        (only_model,) = tuple(returned_models)
        if only_model != model:
            warnings.append(f"requested model {model!r} but got {only_model!r}")

    totals = {
        "calls_made": len(calls),
        "calls_failed": calls_failed,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "returned_models": sorted(returned_models),
        "warnings": warnings,
    }
    return {"calls": calls, "metrics": metrics, "totals": totals}


def _question_metrics(variant_name, qid, question, examples, records, threshold, repeats):
    qtype = question["type"]
    n_labelled = 0
    n_failed = 0
    n_invalid = 0
    scored = []  # list of (label, normalized value)

    for example in examples:
        label = example["labels"].get(qid, _MISSING)
        if label is _MISSING:
            continue
        n_labelled += 1
        rec0 = records.get((variant_name, example["id"]), {}).get(0)
        if rec0 is None or "error" in rec0:
            n_failed += 1
            continue
        answer = rec0["answers"].get(qid)
        if answer is None:
            n_invalid += 1
            continue
        status, value = validate_answer(question, answer)
        if status != "ok":
            n_invalid += 1
            continue
        scored.append((label, value))

    n_scored = len(scored)
    correct = sum(1 for label, value in scored if _decision(qtype, value, threshold) == label)
    accuracy = (correct / n_scored) if n_scored else None

    metrics = {
        "n_labelled": n_labelled,
        "n_scored": n_scored,
        "n_failed": n_failed,
        "n_invalid": n_invalid,
        "accuracy": accuracy,
    }

    if qtype == "noul":
        metrics.update(_noul_metrics(scored, threshold))
    elif qtype == "choice":
        metrics.update(_choice_metrics(scored))
    elif qtype == "score":
        metrics.update(_score_metrics(scored))

    if qtype in ("choice", "score"):
        confidences = [value["confidence"] for _, value in scored]
        mean_confidence = (sum(confidences) / len(confidences)) if confidences else None
        metrics["confident_but_disagreeing"] = bool(
            mean_confidence is not None and mean_confidence >= 0.8 and accuracy is not None and accuracy <= 0.8
        )

    if repeats > 1:
        metrics["stability"] = _stability_metrics(
            variant_name, qid, question, examples, records, threshold, repeats
        )

    return metrics


def _noul_metrics(scored, threshold):
    if not scored:
        return {"brier": None, "false_positives": 0, "false_negatives": 0, "near_threshold": 0}
    brier_sum = 0.0
    false_positives = false_negatives = near_threshold = 0
    for label, value in scored:
        p = value["noul"]
        brier_sum += (p - (1.0 if label else 0.0)) ** 2
        predicted = p >= threshold
        if predicted and not label:
            false_positives += 1
        if not predicted and label:
            false_negatives += 1
        if abs(p - threshold) < 0.1:
            near_threshold += 1
    return {
        "brier": brier_sum / len(scored),
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "near_threshold": near_threshold,
    }


def _choice_metrics(scored):
    confusion = {}
    conf_correct = []
    conf_wrong = []
    high_conf_errors = 0
    flat = 0
    for label, value in scored:
        predicted = value["choice"]
        confusion.setdefault(label, {}).setdefault(predicted, 0)
        confusion[label][predicted] += 1
        confidence = value["confidence"]
        if predicted != label:
            conf_wrong.append(confidence)
            if confidence >= 0.8:
                high_conf_errors += 1
        else:
            conf_correct.append(confidence)
        if confidence < 0.3:
            flat += 1
    return {
        "confusion": confusion,
        "mean_conf_correct": (sum(conf_correct) / len(conf_correct)) if conf_correct else None,
        "mean_conf_wrong": (sum(conf_wrong) / len(conf_wrong)) if conf_wrong else None,
        "high_conf_errors": high_conf_errors,
        "flat": flat,
    }


def _score_metrics(scored):
    confusion = {}
    errors = []
    high_conf_errors = 0
    flat = 0
    for label, value in scored:
        predicted = _round_half_up(value["score"])
        confusion.setdefault(label, {}).setdefault(predicted, 0)
        confusion[label][predicted] += 1
        errors.append(abs(value["score"] - label))
        confidence = value["confidence"]
        if predicted != label and confidence >= 0.8:
            high_conf_errors += 1
        if confidence < 0.3:
            flat += 1
    return {
        "confusion": confusion,
        "mae": (sum(errors) / len(errors)) if errors else None,
        "high_conf_errors": high_conf_errors,
        "flat": flat,
    }


def _stability_metrics(variant_name, qid, question, examples, records, threshold, repeats):
    qtype = question["type"]
    flips = 0
    denominator = 0
    spreads = []

    for example in examples:
        example_records = records.get((variant_name, example["id"]), {})
        valid = []
        for repeat in range(repeats):
            rec = example_records.get(repeat)
            if rec is None or "error" in rec:
                continue
            answer = rec["answers"].get(qid)
            if answer is None:
                continue
            status, value = validate_answer(question, answer)
            if status != "ok":
                continue
            valid.append(value)
        if len(valid) < 2:
            continue
        denominator += 1
        decisions = [_decision(qtype, value, threshold) for value in valid]
        if len(set(decisions)) > 1:
            flips += 1

        if qtype == "choice":
            repeat0_choice = valid[0]["choice"]
            raws = [
                value["probabilities"][repeat0_choice]
                for value in valid
                if repeat0_choice in value.get("probabilities", {})
            ]
        elif qtype == "noul":
            raws = [value["noul"] for value in valid]
        else:
            raws = [value["score"] for value in valid]
        if len(raws) >= 2:
            spreads.append(max(raws) - min(raws))

    return {
        "flip_rate": (flips / denominator) if denominator else None,
        "max_spread": max(spreads) if spreads else None,
    }


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def format_plan(variants, examples, planned):
    lines = ["Plan:", f"  examples: {len(examples)}"]
    for name, questions in variants.items():
        lines.append(f"  variant {name}: {', '.join(questions.keys())}")
    lines.append(f"  planned calls: {planned}")
    return "\n".join(lines)


def _fmt(x):
    return "n/a" if x is None else f"{x:.3f}"


def _format_details(m):
    parts = []
    if "brier" in m:
        parts.append(f"brier={_fmt(m['brier'])}")
        parts.append(f"fp={m['false_positives']}")
        parts.append(f"fn={m['false_negatives']}")
        parts.append(f"near_threshold={m['near_threshold']}")
    if "mae" in m:
        parts.append(f"mae={_fmt(m['mae'])}")
    if "mean_conf_correct" in m:
        parts.append(f"mean_conf_correct={_fmt(m['mean_conf_correct'])}")
        parts.append(f"mean_conf_wrong={_fmt(m['mean_conf_wrong'])}")
    if "high_conf_errors" in m:
        parts.append(f"high_conf_errors={m['high_conf_errors']}")
    if "flat" in m:
        parts.append(f"flat={m['flat']}")
    if "confusion" in m:
        parts.append(f"confusion={json.dumps(m['confusion'], sort_keys=True)}")
    return "; ".join(parts)


def _format_flags(m):
    flags = []
    if m.get("confident_but_disagreeing"):
        flags.append("confident_but_disagreeing")
    stability = m.get("stability")
    if stability:
        flags.append(f"flip_rate={_fmt(stability['flip_rate'])} max_spread={_fmt(stability['max_spread'])}")
    return "; ".join(flags) if flags else "-"


def render_report_md(report):
    lines = [
        "# Question eval report",
        "",
        "Accuracy below is measured only against the supplied labels; it says nothing "
        "about examples outside them.",
        "",
    ]
    variants = report["plan"]["variants"]
    metrics = report["metrics"]

    qids = []
    for name in variants:
        for qid in variants[name]:
            if qid not in qids:
                qids.append(qid)

    for qid in qids:
        lines.append(f"## {qid}")
        lines.append("")
        lines.append("| variant | n | scored | failed | invalid | accuracy | details | flags |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for vname in variants:
            m = metrics.get(vname, {}).get(qid)
            if m is None:
                continue
            acc = _fmt(m["accuracy"])
            lines.append(
                f"| {vname} | {m['n_labelled']} | {m['n_scored']} | {m['n_failed']} | "
                f"{m['n_invalid']} | {acc} | {_format_details(m)} | {_format_flags(m)} |"
            )
        lines.append("")

    totals = report["totals"]
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- calls made: {totals['calls_made']}")
    lines.append(f"- calls failed: {totals['calls_failed']}")
    lines.append(f"- input tokens: {totals['input_tokens']}")
    lines.append(f"- returned models: {', '.join(totals['returned_models']) or 'none'}")
    if totals["warnings"]:
        lines.append("")
        lines.append("### Warnings")
        for warning in totals["warnings"]:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def write_outputs(out_dir, variants, examples, planned, args, result):
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "answers.jsonl", "w", encoding="utf-8") as f:
        for record in result["calls"]:
            f.write(json.dumps(record) + "\n")

    report = {
        "plan": {
            "variants": {name: list(questions.keys()) for name, questions in variants.items()},
            "example_count": len(examples),
            "planned_calls": planned,
            "model": args.model,
            "repeats": args.repeats,
            "noul_threshold": args.noul_threshold,
        },
        "totals": result["totals"],
        "metrics": result["metrics"],
    }
    with open(out_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    md = render_report_md(report)
    with open(out_dir / "report.md", "w", encoding="utf-8") as f:
        f.write(md)
    print(md)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="question_eval.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--examples", required=True, help="JSONL file of labelled examples")
    parser.add_argument(
        "--variant", action="append", required=True, metavar="NAME=FILE",
        help="a named question-set variant; repeat for more than one",
    )
    parser.add_argument("--model", help="versioned model id; required with --live")
    parser.add_argument("--repeats", type=int, default=1, help="repeats per (example, variant) call")
    parser.add_argument("--noul-threshold", type=float, default=0.5, dest="noul_threshold")
    parser.add_argument("--out", help="output directory (default ./question-eval-<UTC timestamp>)")
    parser.add_argument("--live", action="store_true", help="make real API calls")
    parser.add_argument("--max-calls", type=int, default=None, dest="max_calls")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        variants = load_variants(args.variant)
        examples = load_examples(args.examples, variants)
        check_repeats_state(examples, args.repeats)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    planned = plan_calls(examples, variants, args.repeats)
    print(format_plan(variants, examples, planned))

    if not args.live:
        return 0

    if not args.model:
        print("error: --model is required with --live", file=sys.stderr)
        return 2
    if args.model in ALIASES:
        print(
            f"warning: --model {args.model!r} is an alias; pin a versioned model id "
            "for a reproducible live test",
            file=sys.stderr,
        )

    api_key = os.environ.get("TYPESAFE_API_KEY", "")
    if not api_key:
        print("error: TYPESAFE_API_KEY is not set", file=sys.stderr)
        return 2

    if args.max_calls is None or args.max_calls < planned:
        print(
            f"error: --max-calls ({args.max_calls}) is below the planned call count ({planned})",
            file=sys.stderr,
        )
        return 2

    base_url = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
    call = functools.partial(http_call, base_url=base_url, api_key=api_key)

    result = run_eval(
        examples, variants,
        model=args.model, repeats=args.repeats, noul_threshold=args.noul_threshold,
        call=call,
    )

    out_dir = Path(args.out) if args.out else Path(f"./question-eval-{_utc_stamp()}")
    write_outputs(out_dir, variants, examples, planned, args, result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
