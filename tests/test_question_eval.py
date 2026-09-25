"""Tests for question_eval.py. Never make a real network call; always patch
urllib.request.urlopen (or pass a fake `call`) and question_eval._sleep.
"""

import json
import urllib.error

import pytest

import question_eval as qe

FIXTURES = None  # set below, after Path is imported


from pathlib import Path  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "question_eval"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def deny_urlopen(monkeypatch):
    """Patch urlopen to blow up loudly if called -- proves a dry run makes no calls."""

    def _boom(*args, **kwargs):
        raise AssertionError("urlopen must not be called")

    monkeypatch.setattr(qe.urllib.request, "urlopen", _boom)


QUESTIONS = {
    "urgent": {"type": "noul", "instructions": "Is this urgent?"},
    "queue": {
        "type": "choice",
        "instructions": "Which queue?",
        "criteria": {"billing": "b", "technical": "t", "account": "a"},
    },
    "severity": {
        "type": "score",
        "instructions": "How severe?",
        "criteria": ["fine", "minor", "major", "critical"],
    },
}


def make_variants():
    # Two independent copies, since load_questions-shaped dicts are mutated by nothing,
    # but tests should not share mutable state across variants.
    return {"v1": json.loads(json.dumps(QUESTIONS))}


def make_examples():
    return [
        {"id": "e1", "state": {"t": "a"}, "labels": {"urgent": False, "queue": "billing", "severity": 0}},
        {"id": "e2", "state": {"t": "b"}, "labels": {"urgent": True, "queue": "technical", "severity": 3}},
    ]


# --------------------------------------------------------------------------- #
# 1. Dry run makes zero calls and prints the planned count
# --------------------------------------------------------------------------- #


def test_dry_run_makes_zero_calls_and_prints_plan(tmp_path, monkeypatch, capsys):
    deny_urlopen(monkeypatch)
    argv = [
        "--examples", str(FIXTURES / "examples.jsonl"),
        "--variant", f"a={FIXTURES / 'variant_a.json'}",
        "--variant", f"b={FIXTURES / 'variant_b.json'}",
        "--out", str(tmp_path / "out"),
    ]
    code = qe.main(argv)
    assert code == 0
    out = capsys.readouterr().out
    # 3 examples * 2 variants * 1 repeat = 6 planned calls.
    assert "6" in out
    assert not (tmp_path / "out").exists(), "dry run must write no files"


# --------------------------------------------------------------------------- #
# 2. --live without the key env var exits 2 naming the variable
# --------------------------------------------------------------------------- #


def test_live_without_key_env_var_exits_2(tmp_path, monkeypatch, capsys):
    deny_urlopen(monkeypatch)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    argv = [
        "--examples", str(FIXTURES / "examples.jsonl"),
        "--variant", f"a={FIXTURES / 'variant_a.json'}",
        "--model", "jev-1.13-2026-08-01",
        "--live", "--max-calls", "100",
        "--out", str(tmp_path / "out"),
    ]
    code = qe.main(argv)
    assert code == 2
    err = capsys.readouterr().err
    assert "TYPESAFE_API_KEY" in err


# --------------------------------------------------------------------------- #
# 3. --live with --max-calls below planned exits 2 before any call
# --------------------------------------------------------------------------- #


def test_live_max_calls_below_planned_exits_2(tmp_path, monkeypatch, capsys):
    deny_urlopen(monkeypatch)
    monkeypatch.setenv("TYPESAFE_API_KEY", "sentinel-key-value")
    argv = [
        "--examples", str(FIXTURES / "examples.jsonl"),
        "--variant", f"a={FIXTURES / 'variant_a.json'}",  # 3 examples * 1 variant = 3 planned
        "--model", "jev-1.13-2026-08-01",
        "--live", "--max-calls", "2",
        "--out", str(tmp_path / "out"),
    ]
    code = qe.main(argv)
    assert code == 2
    err = capsys.readouterr().err
    assert "3" in err and "2" in err


# --------------------------------------------------------------------------- #
# 4. --live without --model exits 2
# --------------------------------------------------------------------------- #


def test_live_without_model_exits_2(tmp_path, monkeypatch, capsys):
    deny_urlopen(monkeypatch)
    monkeypatch.setenv("TYPESAFE_API_KEY", "sentinel-key-value")
    argv = [
        "--examples", str(FIXTURES / "examples.jsonl"),
        "--variant", f"a={FIXTURES / 'variant_a.json'}",
        "--live", "--max-calls", "100",
        "--out", str(tmp_path / "out"),
    ]
    code = qe.main(argv)
    assert code == 2
    err = capsys.readouterr().err
    assert "--model" in err


# --------------------------------------------------------------------------- #
# 5. Noul metrics
# --------------------------------------------------------------------------- #


def test_noul_metrics(tmp_path):
    variants = {"v1": {"urgent": QUESTIONS["urgent"]}}
    examples = [
        {"id": "a", "state": {}, "labels": {"urgent": True}},   # noul 0.9  -> correct, near nothing
        {"id": "b", "state": {}, "labels": {"urgent": False}},  # noul 0.6  -> false positive, near threshold
        {"id": "c", "state": {}, "labels": {"urgent": True}},   # noul 0.2  -> false negative
        {"id": "d", "state": {}, "labels": {"urgent": False}},  # noul 0.1  -> correct
    ]
    answers_by_id = {
        "a": {"type": "noul", "noul": 0.9},
        "b": {"type": "noul", "noul": 0.6},
        "c": {"type": "noul", "noul": 0.2},
        "d": {"type": "noul", "noul": 0.1},
    }

    def fake_call(state, questions, model):
        # examples carry no identifying field in state, so route by call order.
        eid = next(iter(fake_call.order))
        fake_call.order.remove(eid)
        return {"model": model, "usage": {"input_tokens": 1, "output_tokens": 1},
                "answers": {"urgent": answers_by_id[eid]}}

    fake_call.order = ["a", "b", "c", "d"]

    result = qe.run_eval(examples, variants, model="m", repeats=1, noul_threshold=0.5, call=fake_call)
    m = result["metrics"]["v1"]["urgent"]
    assert m["n_labelled"] == 4
    assert m["n_scored"] == 4
    assert m["accuracy"] == pytest.approx(0.5)  # a, d correct; b, c wrong
    assert m["false_positives"] == 1
    assert m["false_negatives"] == 1
    assert m["near_threshold"] == 1  # only b: |0.6-0.5| = 0.1, not < 0.1 -> check boundary below
    expected_brier = ((0.9 - 1) ** 2 + (0.6 - 0) ** 2 + (0.2 - 1) ** 2 + (0.1 - 0) ** 2) / 4
    assert m["brier"] == pytest.approx(expected_brier)

    # Threshold respected: raising the threshold to 0.65 flips b's prediction to "no" (correct)
    # and c stays wrong; accuracy should change.
    fake_call.order = ["a", "b", "c", "d"]
    result2 = qe.run_eval(examples, variants, model="m", repeats=1, noul_threshold=0.65, call=fake_call)
    m2 = result2["metrics"]["v1"]["urgent"]
    assert m2["accuracy"] == pytest.approx(0.75)
    assert m2["false_positives"] == 0
    assert m2["false_negatives"] == 1


def test_noul_near_threshold_boundary():
    # |0.6 - 0.5| == 0.09999999999999998 due to float error -- must still read as "near" (< 0.1).
    variants = {"v1": {"urgent": QUESTIONS["urgent"]}}
    examples = [{"id": "a", "state": {}, "labels": {"urgent": False}}]

    def fake_call(state, questions, model):
        return {"model": model, "usage": {}, "answers": {"urgent": {"type": "noul", "noul": 0.6}}}

    result = qe.run_eval(examples, variants, model="m", repeats=1, noul_threshold=0.5, call=fake_call)
    assert result["metrics"]["v1"]["urgent"]["near_threshold"] == 1


# --------------------------------------------------------------------------- #
# 6. Choice metrics
# --------------------------------------------------------------------------- #


def test_choice_metrics(tmp_path):
    variants = {"v1": {"queue": QUESTIONS["queue"]}}
    examples = [
        {"id": "a", "state": {}, "labels": {"queue": "billing"}},
        {"id": "b", "state": {}, "labels": {"queue": "technical"}},
        {"id": "c", "state": {}, "labels": {"queue": "account"}},
        {"id": "d", "state": {}, "labels": {"queue": "billing"}},
    ]
    responses = [
        {"choice": "billing", "confidence": 0.95, "probabilities": {"billing": 0.95}},   # correct, high conf
        {"choice": "billing", "confidence": 0.9, "probabilities": {"billing": 0.9}},      # wrong, high conf error
        {"choice": "account", "confidence": 0.2, "probabilities": {"account": 0.2}},      # correct but flat
        {"choice": "technical", "confidence": 0.6, "probabilities": {"technical": 0.6}},  # wrong, not high conf
    ]

    def fake_call(state, questions, model):
        r = responses.pop(0)
        return {"model": model, "usage": {}, "answers": {"queue": {"type": "choice", **r}}}

    result = qe.run_eval(examples, variants, model="m", repeats=1, noul_threshold=0.5, call=fake_call)
    m = result["metrics"]["v1"]["queue"]
    assert m["n_scored"] == 4
    assert m["accuracy"] == pytest.approx(0.5)
    assert m["confusion"] == {
        "billing": {"billing": 1, "technical": 1},
        "technical": {"billing": 1},
        "account": {"account": 1},
    }
    assert m["high_conf_errors"] == 1  # b: wrong, confidence 0.9 >= 0.8
    assert m["flat"] == 1  # c: confidence 0.2 < 0.3
    # mean confidence over all 4 scored = (0.95+0.9+0.2+0.6)/4 = 0.6625 -> not >= 0.8
    assert m["confident_but_disagreeing"] is False


def test_choice_confident_but_disagreeing_flag():
    variants = {"v1": {"queue": QUESTIONS["queue"]}}
    examples = [
        {"id": "a", "state": {}, "labels": {"queue": "billing"}},
        {"id": "b", "state": {}, "labels": {"queue": "technical"}},
    ]
    # Both confident, both wrong -> mean confidence high, accuracy 0 <= 0.8.
    responses = [
        {"choice": "account", "confidence": 0.9, "probabilities": {"account": 0.9}},
        {"choice": "account", "confidence": 0.85, "probabilities": {"account": 0.85}},
    ]

    def fake_call(state, questions, model):
        r = responses.pop(0)
        return {"model": model, "usage": {}, "answers": {"queue": {"type": "choice", **r}}}

    result = qe.run_eval(examples, variants, model="m", repeats=1, noul_threshold=0.5, call=fake_call)
    m = result["metrics"]["v1"]["queue"]
    assert m["accuracy"] == pytest.approx(0.0)
    assert m["confident_but_disagreeing"] is True


# --------------------------------------------------------------------------- #
# 7. Score metrics
# --------------------------------------------------------------------------- #


def test_score_metrics_rounding_mae_confusion():
    variants = {"v1": {"severity": QUESTIONS["severity"]}}
    examples = [
        {"id": "a", "state": {}, "labels": {"severity": 3}},  # score 2.5 -> round-half-up -> 3, correct
        {"id": "b", "state": {}, "labels": {"severity": 1}},  # score 1.0 -> 1, correct
        {"id": "c", "state": {}, "labels": {"severity": 0}},  # score 2.0 -> 2, wrong
    ]
    responses = [
        {"score": 2.5, "confidence": 0.7, "legend": {}, "probabilities": {}},
        {"score": 1.0, "confidence": 0.9, "legend": {}, "probabilities": {}},
        {"score": 2.0, "confidence": 0.85, "legend": {}, "probabilities": {}},
    ]

    def fake_call(state, questions, model):
        r = responses.pop(0)
        return {"model": model, "usage": {}, "answers": {"severity": {"type": "score", **r}}}

    result = qe.run_eval(examples, variants, model="m", repeats=1, noul_threshold=0.5, call=fake_call)
    m = result["metrics"]["v1"]["severity"]
    assert m["accuracy"] == pytest.approx(2 / 3)
    assert m["confusion"] == {3: {3: 1}, 1: {1: 1}, 0: {2: 1}}
    expected_mae = (abs(2.5 - 3) + abs(1.0 - 1) + abs(2.0 - 0)) / 3
    assert m["mae"] == pytest.approx(expected_mae)
    assert m["high_conf_errors"] == 1  # c: wrong, confidence 0.85 >= 0.8


# --------------------------------------------------------------------------- #
# 8. Failed calls
# --------------------------------------------------------------------------- #


def test_failed_calls_excluded_from_accuracy(tmp_path):
    variants = {"v1": {"urgent": QUESTIONS["urgent"]}}
    examples = [
        {"id": "a", "state": {}, "labels": {"urgent": True}},
        {"id": "b", "state": {}, "labels": {"urgent": False}},
    ]

    def fake_call(state, questions, model):
        raise qe.ApiError(500, "server exploded")

    result = qe.run_eval(examples, variants, model="m", repeats=1, noul_threshold=0.5, call=fake_call)
    m = result["metrics"]["v1"]["urgent"]
    assert m["n_labelled"] == 2
    assert m["n_failed"] == 2
    assert m["n_scored"] == 0
    assert m["accuracy"] is None  # not 0
    assert result["totals"]["calls_failed"] == 2
    assert result["totals"]["calls_made"] == 2


# --------------------------------------------------------------------------- #
# 9. Invalid answers
# --------------------------------------------------------------------------- #


def test_invalid_answers_excluded(tmp_path):
    variants = {
        "v1": {
            "queue": QUESTIONS["queue"],
            "urgent": QUESTIONS["urgent"],
            "severity": QUESTIONS["severity"],
        }
    }
    examples = [
        {"id": "a", "state": {}, "labels": {"queue": "billing"}},     # unknown choice key returned
        {"id": "b", "state": {}, "labels": {"urgent": True}},          # noul 1.3, out of range
        {"id": "c", "state": {}, "labels": {"severity": 1}},           # score out of range
        {"id": "d", "state": {}, "labels": {"queue": "billing"}},      # missing qid in the response
    ]
    canned = {
        "a": {"queue": {"type": "choice", "choice": "shipping", "confidence": 0.5, "probabilities": {}}},
        "b": {"urgent": {"type": "noul", "noul": 1.3}},
        "c": {"severity": {"type": "score", "score": 7.0, "confidence": 0.5}},
        "d": {},  # no "queue" key at all
    }
    order = ["a", "b", "c", "d"]

    def fake_call(state, questions, model):
        eid = order.pop(0)
        return {"model": model, "usage": {}, "answers": canned[eid]}

    result = qe.run_eval(examples, variants, model="m", repeats=1, noul_threshold=0.5, call=fake_call)
    metrics = result["metrics"]["v1"]
    assert metrics["queue"]["n_invalid"] == 2  # a (unknown key) + d (missing qid)
    assert metrics["queue"]["n_scored"] == 0
    assert metrics["queue"]["accuracy"] is None
    assert metrics["urgent"]["n_invalid"] == 1
    assert metrics["urgent"]["accuracy"] is None
    assert metrics["severity"]["n_invalid"] == 1
    assert metrics["severity"]["accuracy"] is None


# --------------------------------------------------------------------------- #
# 10. Repeats
# --------------------------------------------------------------------------- #


def test_repeats_add_distinct_eval_run_key():
    variants = {"v1": {"urgent": QUESTIONS["urgent"]}}
    examples = [{"id": "a", "state": {"x": 1}, "labels": {"urgent": True}}]
    seen_states = []

    def fake_call(state, questions, model):
        seen_states.append(dict(state))
        return {"model": model, "usage": {}, "answers": {"urgent": {"type": "noul", "noul": 0.9}}}

    qe.run_eval(examples, variants, model="m", repeats=3, noul_threshold=0.5, call=fake_call)
    assert len(seen_states) == 3
    run_ids = [s.get("_eval_run") for s in seen_states]
    assert all(run_ids)
    assert len(set(run_ids)) == 3  # distinct
    for s in seen_states:
        assert s["x"] == 1  # original state preserved alongside the cache-buster


def test_repeats_flip_rate_and_max_spread():
    variants = {"v1": {"urgent": QUESTIONS["urgent"]}}
    examples = [{"id": "a", "state": {"x": 1}, "labels": {"urgent": True}}]
    nouls = [0.9, 0.4, 0.6]  # decisions at threshold 0.5: yes, no, yes -> not all identical -> flip

    def fake_call(state, questions, model):
        return {"model": model, "usage": {}, "answers": {"urgent": {"type": "noul", "noul": nouls.pop(0)}}}

    result = qe.run_eval(examples, variants, model="m", repeats=3, noul_threshold=0.5, call=fake_call)
    stability = result["metrics"]["v1"]["urgent"]["stability"]
    assert stability["flip_rate"] == pytest.approx(1.0)
    assert stability["max_spread"] == pytest.approx(0.9 - 0.4)


def test_repeats_with_string_state_exits_2(tmp_path, monkeypatch, capsys):
    deny_urlopen(monkeypatch)
    examples_path = tmp_path / "examples.jsonl"
    write_jsonl(examples_path, [{"id": "a", "state": "just a string", "labels": {}}])
    argv = [
        "--examples", str(examples_path),
        "--variant", f"a={FIXTURES / 'variant_a.json'}",
        "--repeats", "2",
        "--out", str(tmp_path / "out"),
    ]
    code = qe.main(argv)
    assert code == 2
    err = capsys.readouterr().err
    assert "object state" in err or "repeats" in err.lower()


# --------------------------------------------------------------------------- #
# 11. HTTP function: retries and non-retried errors
# --------------------------------------------------------------------------- #


class _FakeHTTPResponse:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_http_call_retries_429_then_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(qe, "_sleep", lambda s: sleeps.append(s))

    calls = {"n": 0}
    success_body = json.dumps({"model": "m", "answers": {}, "usage": {}}).encode()

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(
                url="http://x", code=429, msg="rate limited",
                hdrs={"Retry-After": "1"}, fp=None,
            )
        return _FakeHTTPResponse(success_body)

    monkeypatch.setattr(qe.urllib.request, "urlopen", fake_urlopen)
    result = qe.http_call({}, {}, "m", base_url="https://api.typesafe.ai", api_key="k")
    assert result == {"model": "m", "answers": {}, "usage": {}}
    assert calls["n"] == 2
    assert len(sleeps) == 1


def test_http_call_422_not_retried(monkeypatch):
    monkeypatch.setattr(qe, "_sleep", lambda s: (_ for _ in ()).throw(AssertionError("must not sleep")))

    calls = {"n": 0}

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        raise urllib.error.HTTPError(
            url="http://x", code=422, msg="bad request",
            hdrs={}, fp=__import__("io").BytesIO(b'{"error": "bad question"}'),
        )

    monkeypatch.setattr(qe.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(qe.ApiError) as excinfo:
        qe.http_call({}, {}, "m", base_url="https://api.typesafe.ai", api_key="k")
    assert excinfo.value.status == 422
    assert calls["n"] == 1


# --------------------------------------------------------------------------- #
# 12. Input validation errors
# --------------------------------------------------------------------------- #


def test_bad_choice_label_exits_2(tmp_path, monkeypatch, capsys):
    deny_urlopen(monkeypatch)
    examples_path = tmp_path / "examples.jsonl"
    write_jsonl(examples_path, [{"id": "e1", "state": {}, "labels": {"queue": "shipping"}}])
    argv = [
        "--examples", str(examples_path),
        "--variant", f"a={FIXTURES / 'variant_a.json'}",
        "--out", str(tmp_path / "out"),
    ]
    code = qe.main(argv)
    assert code == 2
    err = capsys.readouterr().err
    assert "1" in err  # line number
    assert "queue" in err
    assert "shipping" in err


def test_score_level_out_of_range_exits_2(tmp_path, monkeypatch, capsys):
    deny_urlopen(monkeypatch)
    questions_path = tmp_path / "q.json"
    write_json(questions_path, {
        "severity": {"type": "score", "instructions": "x", "criteria": ["a", "b", "c"]},
    })
    examples_path = tmp_path / "examples.jsonl"
    write_jsonl(examples_path, [{"id": "e1", "state": {}, "labels": {"severity": 9}}])
    argv = [
        "--examples", str(examples_path),
        "--variant", f"a={questions_path}",
        "--out", str(tmp_path / "out"),
    ]
    code = qe.main(argv)
    assert code == 2
    err = capsys.readouterr().err
    assert "severity" in err
    assert "9" in err


def test_duplicate_example_id_exits_2(tmp_path, monkeypatch, capsys):
    deny_urlopen(monkeypatch)
    examples_path = tmp_path / "examples.jsonl"
    write_jsonl(examples_path, [
        {"id": "dup", "state": {}, "labels": {}},
        {"id": "dup", "state": {}, "labels": {}},
    ])
    argv = [
        "--examples", str(examples_path),
        "--variant", f"a={FIXTURES / 'variant_a.json'}",
        "--out", str(tmp_path / "out"),
    ]
    code = qe.main(argv)
    assert code == 2
    err = capsys.readouterr().err
    assert "dup" in err
    assert "2" in err  # line number of the duplicate


# --------------------------------------------------------------------------- #
# 13. The API key value never leaks
# --------------------------------------------------------------------------- #


def test_api_key_never_leaks(tmp_path, monkeypatch, capsys):
    sentinel = "sk-SENTINEL-DO-NOT-LEAK-123456"
    monkeypatch.setenv("TYPESAFE_API_KEY", sentinel)
    seen_auth_headers = []

    def fake_urlopen(request, timeout=None):
        seen_auth_headers.append(request.get_header("Authorization"))
        # One call fails with a 401 whose body echoes the key back, to force redaction.
        if len(seen_auth_headers) == 1:
            raise urllib.error.HTTPError(
                url="http://x", code=401, msg="unauthorized",
                hdrs={}, fp=__import__("io").BytesIO(
                    f'{{"error": "bad key {sentinel}"}}'.encode()
                ),
            )
        body = json.dumps({
            "model": "jev-1.13-2026-08-01",
            "answers": {"urgent": {"type": "noul", "noul": 0.5}},
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }).encode()
        return _FakeHTTPResponse(body)

    monkeypatch.setattr(qe.urllib.request, "urlopen", fake_urlopen)

    examples_path = tmp_path / "examples.jsonl"
    write_jsonl(examples_path, [
        {"id": "e1", "state": {}, "labels": {"urgent": True}},
        {"id": "e2", "state": {}, "labels": {"urgent": False}},
    ])
    questions_path = tmp_path / "q.json"
    write_json(questions_path, {"urgent": QUESTIONS["urgent"]})
    out_dir = tmp_path / "out"

    argv = [
        "--examples", str(examples_path),
        "--variant", f"a={questions_path}",
        "--model", "jev-1.13-2026-08-01",
        "--live", "--max-calls", "10",
        "--out", str(out_dir),
    ]
    code = qe.main(argv)
    assert code == 0

    # The key did reach the transport -- otherwise this test would prove nothing.
    assert seen_auth_headers[0] == f"Bearer {sentinel}"

    out, err = capsys.readouterr()
    assert sentinel not in out
    assert sentinel not in err
    for fname in ("answers.jsonl", "report.json", "report.md"):
        content = (out_dir / fname).read_text(encoding="utf-8")
        assert sentinel not in content


# --------------------------------------------------------------------------- #
# 14. Returned-model warning
# --------------------------------------------------------------------------- #


def test_returned_model_warning_on_mismatch():
    variants = {"v1": {"urgent": QUESTIONS["urgent"]}}
    examples = [{"id": "a", "state": {}, "labels": {"urgent": True}}]

    def fake_call(state, questions, model):
        return {
            "model": "jev-1.14-2026-09-01",  # different from the requested model below
            "usage": {},
            "answers": {"urgent": {"type": "noul", "noul": 0.9}},
        }

    result = qe.run_eval(
        examples, variants, model="jev-1.13-2026-08-01", repeats=1, noul_threshold=0.5, call=fake_call
    )
    warnings = result["totals"]["warnings"]
    assert any("jev-1.14-2026-09-01" in w for w in warnings)


def test_no_returned_model_warning_when_matching():
    variants = {"v1": {"urgent": QUESTIONS["urgent"]}}
    examples = [{"id": "a", "state": {}, "labels": {"urgent": True}}]

    def fake_call(state, questions, model):
        return {"model": model, "usage": {}, "answers": {"urgent": {"type": "noul", "noul": 0.9}}}

    result = qe.run_eval(
        examples, variants, model="jev-1.13-2026-08-01", repeats=1, noul_threshold=0.5, call=fake_call
    )
    assert result["totals"]["warnings"] == []


# --------------------------------------------------------------------------- #
# Extra: --help works (part of "Done means")
# --------------------------------------------------------------------------- #


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        qe.build_parser().parse_args(["--help"])
    assert excinfo.value.code == 0
