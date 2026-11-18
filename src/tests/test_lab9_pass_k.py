"""M6 pass@k / pass^k self-check (public vectors + aggregate wiring)."""
import math

import pytest

pytestmark = pytest.mark.student

BAD = [(5, 6, 1), (5, 2, 0), (3, 1, 4), (5, -1, 1), (0, 0, 1)]


def test_pass_k_both_reject_bad_args():
    from lab9 import stats

    for fn in (stats.pass_at_k, stats.pass_hat_k):
        for n, c, k in BAD:
            with pytest.raises(ValueError):
                fn(n, c, k)


def test_pass_k_edge_values():
    from lab9 import stats

    assert math.isclose(stats.pass_at_k(5, 5, 3), 1.0, abs_tol=1e-9)
    assert math.isclose(stats.pass_at_k(5, 3, 3), 1.0, abs_tol=1e-9)
    assert math.isclose(stats.pass_at_k(5, 4, 1), 0.8, abs_tol=1e-9)
    assert math.isclose(stats.pass_hat_k(5, 0, 1), 0.0, abs_tol=1e-9)
    assert math.isclose(stats.pass_hat_k(5, 3, 5), 0.0, abs_tol=1e-9)
    assert math.isclose(stats.pass_hat_k(5, 5, 1), 1.0, abs_tol=1e-9)


def test_pass_k_hat_le_at1_le_at_k():
    from lab9 import stats

    n, k = 5, 3
    for c in range(n + 1):
        assert stats.pass_hat_k(n, c, k) <= c / n + 1e-12
        assert c / n <= stats.pass_at_k(n, c, k) + 1e-12
        assert abs(stats.pass_at_k(n, c, 1) - c / n) < 1e-12


def test_pass_k_aggregate_fills_metrics():
    from lab9.eval import aggregate

    rows = [{"item_id": "A", "seed": s, "pass_rate": True, "cost": 0.0} for s in range(5)]
    rows += [{"item_id": "B", "seed": s, "pass_rate": s > 0, "cost": 0.0} for s in range(5)]
    out = aggregate(rows, ["pass_rate"], k_values=[1, 5])
    assert math.isclose(out["pass_hat_5"], 0.5, abs_tol=1e-4)
    assert math.isclose(out["pass_at_5"], 1.0, abs_tol=1e-4)
    assert math.isclose(out["pass_hat_1"], 0.9, abs_tol=1e-4)
    assert math.isclose(out["pass_at_1"], 0.9, abs_tol=1e-4)
