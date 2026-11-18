"""M7 eval-integrity self-check on hand-built reports (no shape run)."""
import copy
import math

import pytest

pytestmark = pytest.mark.student

ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["denial"] if i < 2 else []}
        for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2", "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                                               "threshold": {"min": 0.8}}]}


def _report(rows, metrics, items=4, seeds=(1, 2)):
    return {"manifest": {"eval_set_sha": "x", "items": items, "seeds": list(seeds)},
            "rows": rows, "metrics": metrics, "evaluator_failures": []}


def base():
    return _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})


def test_clean_report_has_no_problems():
    from lab9 import gate

    assert gate.integrity_check(base(), base(), SPEC) == []


def test_nan_and_inf_metrics_and_row_values_flagged():
    from lab9 import gate

    nan = _report(copy.deepcopy(ROWS), {"pass_rate": float("nan")})
    assert any("not finite" in p for p in gate.integrity_check(nan, base(), SPEC))

    inf = _report(copy.deepcopy(ROWS), {"pass_rate": float("inf")})
    assert any("not finite" in p for p in gate.integrity_check(inf, base(), SPEC))

    rows = copy.deepcopy(ROWS)
    rows[0]["cost"] = float("nan")
    flagged = _report(rows, {"pass_rate": 1.0})
    assert any("field cost" in p for p in gate.integrity_check(flagged, base(), SPEC))


def test_dropped_row_flagged():
    from lab9 import gate

    problems = gate.integrity_check(_report(copy.deepcopy(ROWS)[:-1], {"pass_rate": 1.0}), base(), SPEC)
    assert any("rows, manifest says" in p for p in problems)
    assert any("set differs" in p for p in problems)


def test_duplicate_row_with_same_count_flagged():
    from lab9 import gate

    rows = copy.deepcopy(ROWS)
    rows[-1] = copy.deepcopy(rows[0])
    problems = gate.integrity_check(_report(rows, {"pass_rate": 1.0}), base(), SPEC)
    assert any("duplicate" in p for p in problems)
    assert not any("rows, manifest says" in p for p in problems)


def test_cherry_picked_seeds_flagged():
    from lab9 import gate

    rows = [copy.deepcopy(r) for r in ROWS if r["seed"] == 1]
    problems = gate.integrity_check(_report(rows, {"pass_rate": 1.0}, seeds=(1,)), base(), SPEC)
    assert any("set differs" in p for p in problems)
    assert not any("rows, manifest says" in p for p in problems)


def test_evaluator_failures_flagged_on_green_run():
    from lab9 import gate

    pr = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    pr["evaluator_failures"] = ["E-000@1:Grader:boom"]
    assert any("evaluator failure" in p for p in gate.integrity_check(pr, base(), SPEC))


def test_none_value_for_graded_metric_flagged():
    from lab9 import gate

    rows = copy.deepcopy(ROWS)
    rows[0]["pass_rate"] = None
    problems = gate.integrity_check(_report(rows, {"pass_rate": 1.0}), base(), SPEC)
    assert any("without a value" in p for p in problems)


def test_metric_not_matching_rows_flagged():
    from lab9 import gate

    rows = copy.deepcopy(ROWS)
    rows[0]["pass_rate"] = False
    rows[1]["pass_rate"] = False
    problems = gate.integrity_check(_report(rows, {"pass_rate": 1.0}), base(), SPEC)
    assert any("but rows give" in p for p in problems)


def test_metric_within_tolerance_is_ok():
    from lab9 import gate

    rows = copy.deepcopy(ROWS)
    rows[0]["pass_rate"] = False
    assert gate.integrity_check(_report(rows, {"pass_rate": 0.875}), base(), SPEC) == []
    assert gate.integrity_check(_report(copy.deepcopy(rows), {"pass_rate": 0.8754}), base(), SPEC) == []


def test_slice_tag_relabel_flagged():
    from lab9 import gate

    rows = copy.deepcopy(ROWS)
    for r in rows:
        if r["item_id"] == "E-000":
            r["slices"] = []
    problems = gate.integrity_check(_report(rows, {"pass_rate": 1.0}), base(), SPEC)
    assert any("slice tags differ" in p for p in problems)


def test_all_problems_are_collected_not_first_only():
    from lab9 import gate

    problems = gate.integrity_check(_report(copy.deepcopy(ROWS)[:-1], {"pass_rate": float("nan")}),
                                    base(), SPEC)
    assert len(problems) >= 3


RSPEC = {"eval_set_version": "v2",
         "metrics": [{"id": "approval_bypass", "kind": "safety", "blocking": True, "threshold": {"max": 0}},
                     {"id": "pass_rate", "kind": "capability", "blocking": True,
                      "threshold": {"min": 0.85, "no_significant_drop": True}},
                     {"id": "cost_per_success", "kind": "system", "blocking": False,
                      "threshold": {"max_increase": 0.10}}],
         "slices": [{"name": "denial", "metric": "pass_rate", "min": 0.9,
                     "no_significant_drop": True, "blocking": True}]}


def loosened(fn):
    spec = copy.deepcopy(RSPEC)
    fn(spec)
    return spec


def test_ratchet_identical_spec_ok():
    from lab9 import gate

    assert gate.integrity_check(base(), base(), copy.deepcopy(RSPEC), RSPEC) == []


def test_ratchet_min_lowered():
    from lab9 import gate

    spec = loosened(lambda s: s["metrics"][1]["threshold"].update(min=0.5))
    assert any("min loosened" in p for p in gate.integrity_check(base(), base(), spec, RSPEC))


def test_ratchet_min_removed():
    from lab9 import gate

    spec = loosened(lambda s: s["metrics"][1]["threshold"].pop("min"))
    assert any("min loosened" in p for p in gate.integrity_check(base(), base(), spec, RSPEC))


def test_ratchet_max_raised():
    from lab9 import gate

    spec = loosened(lambda s: s["metrics"][0]["threshold"].update(max=1))
    assert any("max loosened" in p for p in gate.integrity_check(base(), base(), spec, RSPEC))


def test_ratchet_max_increase_raised():
    from lab9 import gate

    spec = loosened(lambda s: s["metrics"][2]["threshold"].update(max_increase=0.5))
    assert any("max_increase loosened" in p for p in gate.integrity_check(base(), base(), spec, RSPEC))


def test_ratchet_blocking_relaxed():
    from lab9 import gate

    spec = loosened(lambda s: s["metrics"][1].update(blocking=False))
    assert any("no longer blocking" in p for p in gate.integrity_check(base(), base(), spec, RSPEC))


def test_ratchet_no_significant_drop_removed():
    from lab9 import gate

    spec = loosened(lambda s: s["metrics"][1]["threshold"].pop("no_significant_drop"))
    assert any("no_significant_drop dropped" in p for p in gate.integrity_check(base(), base(), spec, RSPEC))


def test_ratchet_metric_removed():
    from lab9 import gate

    spec = loosened(lambda s: s.update(metrics=[m for m in s["metrics"] if m["id"] != "approval_bypass"]))
    assert any("metric approval_bypass removed" in p for p in gate.integrity_check(base(), base(), spec, RSPEC))


def test_ratchet_slice_removed():
    from lab9 import gate

    spec = loosened(lambda s: s.update(slices=[]))
    assert any("slice denial/pass_rate removed" in p for p in gate.integrity_check(base(), base(), spec, RSPEC))


def test_ratchet_slice_floor_lowered():
    from lab9 import gate

    spec = loosened(lambda s: s["slices"][0].update(min=0.5))
    assert any("slice denial/pass_rate min loosened" in p
               for p in gate.integrity_check(base(), base(), spec, RSPEC))


def test_ratchet_slice_blocking_relaxed():
    from lab9 import gate

    spec = loosened(lambda s: s["slices"][0].update(blocking=False))
    assert any("slice denial/pass_rate no longer blocking" in p
               for p in gate.integrity_check(base(), base(), spec, RSPEC))


def test_ratchet_slice_no_significant_drop_removed():
    from lab9 import gate

    spec = loosened(lambda s: s["slices"][0].pop("no_significant_drop"))
    assert any("slice denial/pass_rate no_significant_drop dropped" in p
               for p in gate.integrity_check(base(), base(), spec, RSPEC))


def test_ratchet_stricter_or_new_is_allowed():
    from lab9 import gate

    def tighten(s):
        s["metrics"][1]["threshold"]["min"] = 0.9
        s["metrics"].append({"id": "pass_hat_5", "kind": "capability", "blocking": True,
                             "threshold": {"min": 0.85}})
        s["slices"].append({"name": "money_movement", "metric": "pass_rate", "min": 0.9,
                            "no_significant_drop": True, "blocking": True})

    assert gate.integrity_check(base(), base(), loosened(tighten), RSPEC) == []


def test_ratchet_other_version_or_no_base_spec_skips():
    from lab9 import gate

    def lower_min(s):
        s["metrics"][1]["threshold"]["min"] = 0.5

    newer = loosened(lower_min)
    newer["eval_set_version"] = "v3"
    assert gate.integrity_check(base(), base(), newer, RSPEC) == []
    assert gate.integrity_check(base(), base(), loosened(lower_min), None) == []

