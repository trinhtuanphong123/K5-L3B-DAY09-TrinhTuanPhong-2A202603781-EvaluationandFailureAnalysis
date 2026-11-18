"""M5 slice gate self-check on hand-built reports (no shape run)."""
import copy

import pytest

pytestmark = pytest.mark.student

SEEDS = (1, 2)
SLICE = "money_movement"
SLICE_SPEC = {"name": SLICE, "metric": "pass_rate", "min": 0.9, "blocking": True}


def _report(rows, metrics, items=6, seeds=SEEDS):
    return {"manifest": {"eval_set_sha": "x", "items": items, "seeds": list(seeds)},
            "rows": rows, "metrics": metrics, "evaluator_failures": []}


def _rows(fail=None):
    """6 items x 2 seeds; items 0-2 carry the money_movement slice, items 3-5 carry none."""
    rows = []
    for i in range(6):
        tags = [SLICE] if i < 3 else []
        for s in SEEDS:
            ok = True if fail is None else not fail(i, s)
            rows.append({"item_id": f"E-{i:03d}", "seed": s, "pass_rate": ok, "slices": list(tags)})
    return rows


def _base():
    return _report(copy.deepcopy(_rows()), {"pass_rate": 1.0})


def test_slice_below_min_blocks():
    from lab9 import gate

    pr = _report(_rows(lambda i, s: i < 3 and s == 1), {"pass_rate": 0.75})
    blocked, lines = gate.slice_check(pr, _base(), {"slices": [dict(SLICE_SPEC)]})
    assert blocked == [f"slice:{SLICE}/pass_rate"]
    assert any(line.rstrip().endswith("BLOCK") for line in lines)


def test_slice_significant_drop_blocks_even_without_min():
    from lab9 import gate

    pr = _report(_rows(lambda i, s: i < 3), {"pass_rate": 0.5})
    spec = {"slices": [{"name": SLICE, "metric": "pass_rate",
                        "no_significant_drop": True, "blocking": True}]}
    blocked, lines = gate.slice_check(pr, _base(), spec)
    assert f"slice:{SLICE}/pass_rate" in blocked
    assert any("BLOCK" in line for line in lines)


def test_slice_equal_to_baseline_passes():
    from lab9 import gate

    pr = _report(_rows(), {"pass_rate": 1.0})
    spec = {"slices": [dict(SLICE_SPEC, no_significant_drop=True)]}
    blocked, lines = gate.slice_check(pr, _base(), spec)
    assert blocked == []
    assert any(line.rstrip().endswith("ok") for line in lines)


def test_slice_ci_touching_zero_is_not_blocked_by_drop_rule():
    from lab9 import gate

    pr = _report(_rows(lambda i, s: i == 0 and s == 1), {"pass_rate": 0.9167})
    spec = {"slices": [{"name": SLICE, "metric": "pass_rate",
                        "no_significant_drop": True, "blocking": True}]}
    blocked, _ = gate.slice_check(pr, _base(), spec)
    assert blocked == []


def test_empty_slice_in_pr_is_missing_and_blocks():
    from lab9 import gate

    rows = _rows()
    for r in rows:
        r["slices"] = []
    pr = _report(rows, {"pass_rate": 1.0})
    blocked, lines = gate.slice_check(pr, _base(), {"slices": [dict(SLICE_SPEC)]})
    assert f"slice:{SLICE}/pass_rate" in blocked
    assert any("MISSING" in line for line in lines)


def test_non_blocking_slice_only_warns():
    from lab9 import gate

    pr = _report(_rows(lambda i, s: i < 3 and s == 1), {"pass_rate": 0.75})
    spec = {"slices": [dict(SLICE_SPEC, blocking=False)]}
    blocked, lines = gate.slice_check(pr, _base(), spec)
    assert blocked == []
    assert any(line.rstrip().endswith("warn") for line in lines)


def test_no_slices_in_spec_returns_empty():
    from lab9 import gate

    pr = _report(_rows(), {"pass_rate": 1.0})
    assert gate.slice_check(pr, _base(), {"metrics": []}) == ([], [])
