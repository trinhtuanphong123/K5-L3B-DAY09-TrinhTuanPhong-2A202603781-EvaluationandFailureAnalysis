"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")
    tp = fp = fn = tn = 0
    for h, j in zip(human, judge):
        if h == POS and j == POS:
            tp += 1
        elif h != POS and j == POS:
            fp += 1
        elif h == POS and j != POS:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    # TODO M2: precision = tp/(tp+fp), recall = tp/(tp+fn); return 0.0 when the denominator is 0
    cm = confusion(human, judge)
    predicted_pos = cm["tp"] + cm["fp"]
    actual_pos = cm["tp"] + cm["fn"]
    precision = float(cm["tp"]) / predicted_pos if predicted_pos else 0.0
    recall = float(cm["tp"]) / actual_pos if actual_pos else 0.0
    return (precision, recall)


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    # TODO M2
    cm = confusion(human, judge)
    n = cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"]
    if n == 0:
        raise ValueError("kappa undefined: no items")
    p_o = (cm["tp"] + cm["tn"]) / n
    p_h_pos = (cm["tp"] + cm["fn"]) / n
    p_j_pos = (cm["tp"] + cm["fp"]) / n
    p_e = p_h_pos * p_j_pos + (1 - p_h_pos) * (1 - p_j_pos)
    if abs(1 - p_e) < 1e-12:
        raise ValueError("kappa undefined: p_e == 1 (constant labels)")
    return (p_o - p_e) / (1 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    # TODO M2: (p_obs + spec - 1) / (sens + spec - 1)
    denom = sensitivity + specificity - 1
    if denom <= 0:
        return float("nan")
    value = (observed_rate + specificity - 1) / denom
    return min(1.0, max(0.0, value))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    # TODO M4
    import numpy as np
    from scipy.stats import bootstrap

    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    if x.shape != y.shape:
        raise ValueError("a and b must be paired: same length")
    if x.size == 0:
        raise ValueError("no items")
    if np.array_equal(x, y):
        return (0.0, 0.0, 0.0)
    d = float(x.mean() - y.mean())
    res = bootstrap(
        (x, y),
        lambda u, v, axis: np.mean(u, axis=axis) - np.mean(v, axis=axis),
        paired=True,
        vectorized=True,
        n_resamples=n_resamples,
        confidence_level=confidence,
        method="percentile",
        rng=np.random.default_rng(rng),
    )
    return (d, float(res.confidence_interval.low), float(res.confidence_interval.high))


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    from math import comb

    if k < 1 or k > n or c < 0 or c > n:
        raise ValueError(f"pass_at_k needs 1 <= k <= n and 0 <= c <= n (got n={n}, c={c}, k={k})")
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    from math import comb

    if k < 1 or k > n or c < 0 or c > n:
        raise ValueError(f"pass_hat_k needs 1 <= k <= n and 0 <= c <= n (got n={n}, c={c}, k={k})")
    return comb(c, k) / comb(n, k)
