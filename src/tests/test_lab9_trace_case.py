"""Regression test for docs/trace_case.md: seeded_regression C-002@11 (FM-03, ticket_trust).

First wrong step: event 3 `model_override {"delay_days": 5}` overrides the DB fact delay_days=2.
Must be caught on the buggy variant and NOT flagged on the `fixed` control.
"""
import pytest

pytestmark = pytest.mark.student
CLAIM, SEED = "C-002", 11


@pytest.fixture(scope="module")
def case():
    # The overlaid Lab 8 CI collects these tests with only Lab 8 dependencies.
    from lab9.trace_case import investigate

    return {shape: investigate(shape, CLAIM, SEED) for shape in ("seeded_regression", "fixed")}


def grade(c):
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9.graders import DbFactKept, RefundAmountCorrect

    ctx = EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=c["label"], output=c["trial"],
                           duration=0.0, _span_tree=None, attributes={}, metrics={})
    return DbFactKept().evaluate(ctx).value, RefundAmountCorrect().evaluate(ctx).value


def test_trace_case_c002_seed11_first_wrong_step_is_caught(case):
    c = case["seeded_regression"]
    events = c["trial"]["events"]
    assert events[2]["kind"] == "model_override"
    assert events[2]["payload"] == {"delay_days": 5}
    assert c["trial"]["snapshot"]["refund_vnd"] == 20000
    assert grade(c) == (False, False)


def test_trace_case_c002_seed11_control_fixed_passes(case):
    c = case["fixed"]
    assert not [e for e in c["trial"]["events"] if e.get("kind") == "model_override"]
    assert c["trial"]["snapshot"]["refund_vnd"] == 0
    assert grade(c) == (True, True)
