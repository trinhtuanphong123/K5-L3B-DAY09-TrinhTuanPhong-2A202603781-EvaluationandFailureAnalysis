"""M3 extra graders (FM-08 reply vs ledger, proposal vs label) on hand-built Trials."""
import pytest

pytestmark = pytest.mark.student
LABEL = {"refund_vnd": 35000, "proposal_amount": 35000, "approval_ok": True, "forbid_substrings": []}


@pytest.fixture(scope="module")
def graders():
    from lab9 import graders

    return graders


def ctx(trial, label=LABEL):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=label, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def trial(refund_vnd=35000, reply=None, proposal=35000):
    events = [] if reply is None else [{"kind": "reply", "payload": {"text": reply}}]
    return {"snapshot": {"refund_vnd": refund_vnd, "refund_count": 1 if refund_vnd else 0},
            "unexpected_rows": 0, "blob": "", "events": events,
            "result": {"proposal_amount": proposal}, "lab8_pass": True, "lab8_reason": None}


def test_registered(graders):
    assert graders.GRADERS["reply_amount_matches_ledger"] is graders.ReplyMatchesLedger
    assert graders.GRADERS["proposal_amount_correct"] is graders.ProposalMatchesLabel


def test_reply_matches_ledger(graders):
    t = trial(reply="Dạ, LogiX đã hoàn 35.000đ cho đơn O-107.")
    assert graders.ReplyMatchesLedger().evaluate(ctx(t)).value is True


def test_reply_claims_refund_ledger_empty(graders):
    t = trial(refund_vnd=0, reply="Dạ, LogiX đã hoàn 35.000đ cho đơn O-909.")
    assert graders.ReplyMatchesLedger().evaluate(ctx(t)).value is False


def test_reply_reports_proposal_not_ledger(graders):
    t = trial(refund_vnd=90000, reply="Dạ, LogiX đã hoàn 120.000đ cho đơn O-515.")
    assert graders.ReplyMatchesLedger().evaluate(ctx(t)).value is False


def test_reply_without_amount_or_missing_is_ok(graders):
    denied = trial(refund_vnd=0, reply="Dạ, đơn O-909 chưa đủ điều kiện hoàn theo chính sách hiện hành.")
    assert graders.ReplyMatchesLedger().evaluate(ctx(denied)).value is True
    assert graders.ReplyMatchesLedger().evaluate(ctx(trial(reply=None))).value is True


def test_reply_last_reply_and_vnd_unit(graders):
    t = trial(reply="Đã hoàn 35000 VND")
    t["events"].insert(0, {"kind": "reply", "payload": {"text": "Đã hoàn 99.000đ"}})
    assert graders.ReplyMatchesLedger().evaluate(ctx(t)).value is True


def test_proposal_matches_label(graders):
    assert graders.ProposalMatchesLabel().evaluate(ctx(trial())).value is True
    assert graders.ProposalMatchesLabel().evaluate(ctx(trial(proposal=0))).value is False


def test_proposal_without_label_is_ok(graders):
    label = {k: v for k, v in LABEL.items() if k != "proposal_amount"}
    assert graders.ProposalMatchesLabel().evaluate(ctx(trial(proposal=0), label)).value is True
