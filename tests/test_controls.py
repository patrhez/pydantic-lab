from concurrent.futures import ThreadPoolExecutor

import pytest

from pydantic_lab.application.controls import Controls
from pydantic_lab.models import Approval, Receipt
from pydantic_lab.storage.control import Conflict


def start(store, local):
    controls = Controls(store)
    rid = controls.send(local.id, "First", "queue", "first")["run_id"]
    store.mutate(local.id, lambda s, e: setattr(s.run(rid), "status", "running"))
    return controls, rid


def test_queue_retry_is_idempotent_and_stop_preserves_fifo(store, local):
    controls, rid = start(store, local)
    with ThreadPoolExecutor(4) as pool:
        results = list(
            pool.map(lambda _: controls.send(local.id, "Later", "queue", "later"), range(4))
        )
    assert len({r["run_id"] for r in results}) == 1
    controls.stop(local.id, "stop")
    session = store.get(local.id)
    assert session.paused and session.run(rid).stop_requested
    assert [r.prompt for r in session.runs] == ["First", "Later"]
    controls.send(local.id, "Paused input", "queue", "paused")
    assert store.get(local.id).paused


def test_steer_expires_approval_and_rejects_late_response(store, local):
    controls, rid = start(store, local)
    approval = Approval(
        call_id="call", tool="write_file", arguments={}, digest="hash", policy_revision="1"
    )
    store.mutate(local.id, lambda s, e: s.run(rid).approvals.append(approval))
    controls.send(local.id, "Inspect only", "steer", "steer")
    assert store.get(local.id).run(rid).approvals[0].status == "expired"
    with pytest.raises(Conflict, match="expired"):
        controls.decide(local.id, approval.id, True, "late")
    assert controls.send(local.id, "Inspect only", "steer", "steer")["run_id"] == rid
    assert len(store.get(local.id).run(rid).steers) == 1


def test_stop_before_steer_never_silently_queues(store, local):
    controls, rid = start(store, local)
    controls.stop(local.id, "stop")
    with pytest.raises(Conflict):
        controls.send(local.id, "New plan", "steer", "steer")
    assert len(store.get(local.id).runs) == 1


def test_unknown_requires_explicit_decision(store, local):
    controls, rid = start(store, local)

    def unknown(s, e):
        r = s.run(rid)
        r.status = s.status = "outcome_unknown"
        r.receipts["call"] = Receipt(
            call_id="call", tool="run_command", digest="hash", status="outcome_unknown"
        )

    store.mutate(local.id, unknown)
    with pytest.raises(Conflict):
        controls.recover(local.id, "retry", False, "no")
    controls.recover(local.id, "continue", True, "yes")
    receipt = store.get(local.id).run(rid).receipts["call"]
    assert receipt.status == "reconciled" and "unknown" in receipt.result


def test_snapshot_cursor_includes_prior_events(store, local):
    controls, rid = start(store, local)
    snap = store.snapshot(local.id)
    controls.send(local.id, "After snapshot", "queue", "after")
    replay = store.replay(local.id, snap["cursor"])
    assert len(replay) == 1 and replay[0]["content"] == "After snapshot"


def test_extension_trust_is_reused_only_for_the_same_repository_identity(store, local):
    from pydantic_lab.models import Session

    store.mutate(local.id, lambda s, e: s.trust.update({"skills": "a" * 64}))
    same = store.create(Session(title="Same", mode="local", repository=local.repository))
    other = store.create(
        Session(title="Other", mode="local", repository=local.repository + "-other")
    )
    assert same.trust == {"skills": "a" * 64}
    assert not other.trust
