"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def _graded_ids(spec: dict, base: dict) -> list[str]:
    """Metric ids graded per row: an id in spec["metrics"] AND a key of at least one baseline row."""
    ids = {m["id"] for m in spec.get("metrics", [])}
    keys: set[str] = set()
    for r in base.get("rows") or []:
        keys.update(r.keys())
    return sorted(ids & keys)


def _ratchet_problems(spec: dict, base_spec: dict) -> list[str]:
    """Reasons a spec loosened a threshold of base_spec on the same eval-set version (D6)."""
    if spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        return []
    problems: list[str] = []
    new = {m["id"]: m for m in spec.get("metrics", []) or []}
    for old in base_spec.get("metrics", []) or []:
        mid = old["id"]
        if mid not in new:
            problems.append(f"ratchet: metric {mid} removed")
            continue
        n = new[mid]
        ot, nt = old.get("threshold", {}) or {}, n.get("threshold", {}) or {}
        if old.get("blocking") and not n.get("blocking"):
            problems.append(f"ratchet: metric {mid} no longer blocking")
        for key in ("min",):
            if key in ot and (key not in nt or nt[key] < ot[key] - 1e-12):
                problems.append(f"ratchet: metric {mid} {key} loosened ({ot[key]} -> {nt.get(key)})")
        for key in ("max", "max_increase"):
            if key in ot and (key not in nt or nt[key] > ot[key] + 1e-12):
                problems.append(f"ratchet: metric {mid} {key} loosened ({ot[key]} -> {nt.get(key)})")
        if ot.get("no_significant_drop") and not nt.get("no_significant_drop"):
            problems.append(f"ratchet: metric {mid} no_significant_drop dropped")

    snew = {(s["name"], s["metric"]): s for s in spec.get("slices", []) or []}
    for old in base_spec.get("slices", []) or []:
        sid = f"{old['name']}/{old['metric']}"
        if (old["name"], old["metric"]) not in snew:
            problems.append(f"ratchet: slice {sid} removed")
            continue
        n = snew[(old["name"], old["metric"])]
        if "min" in old and ("min" not in n or n["min"] < old["min"] - 1e-12):
            problems.append(f"ratchet: slice {sid} min loosened ({old['min']} -> {n.get('min')})")
        if old.get("blocking") and not n.get("blocking"):
            problems.append(f"ratchet: slice {sid} no longer blocking")
        if old.get("no_significant_drop") and not n.get("no_significant_drop"):
            problems.append(f"ratchet: slice {sid} no_significant_drop dropped")
    return problems


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    rows = pr.get("rows") or []
    brows = base.get("rows") or []
    man = pr.get("manifest") or {}

    # D1: a non-finite total or row value is a report we cannot trust.
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {k} is {v} (not finite)")
    bad_values: list[str] = []
    for i, r in enumerate(rows):
        for k, v in r.items():
            if isinstance(v, float) and not math.isfinite(v):
                bad_values.append(f"row {i} ({r.get('item_id')}@{r.get('seed')}) field {k} is {v}")
    if len(bad_values) > 5:
        problems.extend(bad_values[:5])
        problems.append(f"... and {len(bad_values) - 5} more non-finite row values")
    else:
        problems.extend(bad_values)

    # D2: the row count the manifest promises, and no (item, seed) appearing twice.
    n_seeds = len(man.get("seeds", []) or [])
    want_rows = int(man.get("items", 0)) * n_seeds
    if len(rows) != want_rows:
        problems.append(f"{len(rows)} rows, manifest says {man.get('items')} items x {n_seeds} seeds = {want_rows}")
    keys = [(r.get("item_id"), r.get("seed")) for r in rows]
    if len(set(keys)) != len(keys):
        problems.append(f"{len(keys) - len(set(keys))} duplicate (item_id, seed) row(s)")

    # D3: the PR must cover exactly the baseline's items and seeds (no cherry-picking, no drops).
    bkeys = {(r.get("item_id"), r.get("seed")) for r in brows}
    pkeys = set(keys)
    if pkeys != bkeys:
        problems.append(f"(item, seed) set differs from baseline: {len(bkeys - pkeys)} missing, "
                        f"{len(pkeys - bkeys)} extra")

    # D4: a crashed grader must never score as "missing" and quietly leave the mean.
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s): "
                        f"{pr['evaluator_failures'][0]}")
    graded = _graded_ids(spec, base)
    for mid in graded:
        n = sum(1 for r in rows if r.get(mid) is None)
        if n:
            problems.append(f"metric {mid}: {n} row(s) without a value (grader crashed or dropped)")

    # D5: the totals must be recomputable from the rows (hand-edited numbers show up here).
    totals = pr.get("metrics") or {}
    for mid in graded:
        if mid not in totals:
            continue
        v = totals[mid]
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            continue
        vals = [r[mid] for r in rows if r.get(mid) is not None]
        if not vals:
            continue
        want = sum(vals) if mid in ("approval_bypass", "secret_leak") else round(sum(vals) / len(vals), 4)
        if abs(v - want) > 0.001:
            problems.append(f"metric {mid} = {v} but rows give {want}")

    # D7: relabelling an item out of a slice hides its regression from the slice gate.
    def _tags(rs: list) -> dict[str, set]:
        out: dict[str, set] = {}
        for r in rs:
            out.setdefault(r.get("item_id"), set()).update(r.get("slices") or [])
        return out

    ptags, btags = _tags(rows), _tags(brows)
    differ = [f"{iid} {sorted(btags[iid])} -> {sorted(ptags[iid])}"
              for iid in sorted(set(ptags) & set(btags)) if ptags[iid] != btags[iid]]
    if differ:
        problems.append(f"slice tags differ from baseline for {len(differ)} item(s): "
                        + ", ".join(differ[:3]) + (" ..." if len(differ) > 3 else ""))

    if base_spec is not None:
        problems += _ratchet_problems(spec, base_spec)
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices", []):
        name, metric = s["name"], s["metric"]
        sid = f"slice:{name}/{metric}"
        th = {k: s[k] for k in ("min", "no_significant_drop") if k in s}
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        note = ""
        if not a:
            verdict, val = "missing", None
        else:
            val = sum(a.values()) / len(a)
            verdict = "ok"
            if "min" in s and val < s["min"]:
                verdict = "fail"
            if s.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                       n_resamples=bs.get("n_resamples", 1000),
                                                       rng=bs.get("rng", 2027))
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        label = "ok" if verdict == "ok" else ("MISSING" if verdict == "missing"
                                              else ("BLOCK" if s.get("blocking") else "warn"))
        val_s = None if val is None else round(val, 4)
        lines.append(f"  {sid:<22} {val_s!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
