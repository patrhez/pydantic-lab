"""Atomic control transitions, independent of HTTP and the framework loop."""

from __future__ import annotations

from pydantic_lab.models import Input, Run
from pydantic_lab.storage.control import Conflict, ControlStore


class Controls:
    def __init__(self, store: ControlStore):
        self.store = store

    def send(self, sid: str, content: str, mode: str, request_id: str):
        if not content.strip() or len(content) > 100_000:
            raise Conflict("Message must contain 1 to 100000 characters")
        if mode not in {"queue", "steer"}:
            raise Conflict("Choose queue or steer")

        def apply(session, emit):
            if (session.mode == "server" and not session.initialized) or session.status in {
                "provisioning",
                "deleting",
                "deleted",
                "cleanup_failed",
                "outcome_unknown",
            }:
                raise Conflict("Session is unavailable for messages")
            if any(
                a["status"] in {"queued", "running"}
                and a["kind"] in {"network", "rebuild", "delete", "trust"}
                for a in session.actions
            ):
                raise Conflict("Wait for the sandbox or trust change to finish")
            active = session.active()
            if mode == "steer":
                if not active or active.stop_requested:
                    raise Conflict("No active run; send explicitly as Queue")
                item = Input(content=content)
                active.steers.append(item)
                for approval in active.approvals:
                    if approval.status in {"pending", "allowed"}:
                        approval.status = "expired"
                        approval.reason = "Steer changed the plan"
                emit("steer.recorded", run_id=active.id, message_id=item.id, content=content)
                return {"run_id": active.id, "message_id": item.id}
            run = Run(prompt=content)
            session.runs.append(run)
            emit("queue.accepted", run_id=run.id, content=content, paused=session.paused)
            return {"run_id": run.id}

        return self.store.mutate(sid, apply, request_id)

    def stop(self, sid: str, request_id: str):
        def apply(session, emit):
            session.paused = True
            active = session.active()
            if active:
                active.stop_requested = True
                for approval in active.approvals:
                    if approval.status in {"pending", "allowed"}:
                        approval.status = "expired"
                        approval.reason = "Run stopped"
                emit("stop.requested", run_id=active.id)
            else:
                session.status = "stopped"
            return {"accepted": True}

        return self.store.mutate(sid, apply, request_id)

    def continue_queue(self, sid: str, request_id: str):
        def apply(session, emit):
            if session.active():
                raise Conflict("Resolve the active run before continuing the queue")
            session.paused = False
            session.status = "ready"
            emit("queue.continued")
            return {"accepted": True}

        return self.store.mutate(sid, apply, request_id)

    def decide(self, sid: str, approval_id: str, allow: bool, request_id: str):
        def apply(session, emit):
            candidates = session.setup_approvals + [a for r in session.runs for a in r.approvals]
            approval = next((a for a in candidates if a.id == approval_id), None)
            if (
                not approval
                or approval.status != "pending"
                or approval.policy_revision != session.policy.revision
            ):
                raise Conflict("This approval has expired")
            if not approval.setup:
                active = session.active()
                if not active or active.stop_requested:
                    raise Conflict("This approval has expired")
            approval.status = "allowed" if allow else "rejected"
            emit("approval.decided", approval_id=approval.id, decision=approval.status)
            return {"accepted": True, "status": approval.status}

        return self.store.mutate(sid, apply, request_id)

    def recover(self, sid: str, action: str, confirmed: bool, request_id: str):
        if action not in {"continue", "retry", "abort"} or not confirmed:
            raise Conflict("Inspect the operation and explicitly confirm a recovery decision")

        def apply(session, emit):
            run = session.active()
            if not run and session.status == "outcome_unknown":
                unknown_setup = [
                    r for r in session.setup_receipts.values() if r.status == "outcome_unknown"
                ]
                if not unknown_setup:
                    raise Conflict("No unknown setup operation to inspect")
                for receipt in unknown_setup:
                    if action == "retry":
                        del session.setup_receipts[receipt.call_id]
                    else:
                        receipt.status = "reconciled"
                        receipt.result = "Outcome unknown; manually inspected without retry."
                        if action == "continue":
                            session.init_completed += 1
                session.status = "failed" if action == "abort" else "provisioning"
                session.error = (
                    "Setup aborted; existing effects remain." if action == "abort" else None
                )
                emit("recovery.decided", setup=True, action=action)
                return {"accepted": True}
            if not run or run.status != "outcome_unknown":
                raise Conflict("No unknown operation to inspect")
            unknown = [r for r in run.receipts.values() if r.status == "outcome_unknown"]
            for receipt in unknown:
                if action == "retry":
                    del run.receipts[receipt.call_id]
                else:
                    receipt.status = "reconciled"
                    receipt.result = (
                        "Outcome unknown. The user inspected the workspace and chose not to retry."
                    )
            run.owner = None
            run.stop_requested = False
            if action == "abort":
                run.status = "cancelled"
                session.status = "stopped"
                session.paused = True
            else:
                run.status = "running"
                session.status = "running"
            emit("recovery.decided", run_id=run.id, action=action)
            return {"accepted": True}

        return self.store.mutate(sid, apply, request_id)
