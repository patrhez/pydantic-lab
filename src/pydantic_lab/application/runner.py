"""Run orchestration: native continuation plus durable application controls."""

from __future__ import annotations

import asyncio
import time
import uuid

from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelResponse,
    ToolCallPart,
)
from pydantic_ai.tools import DeferredToolRequests, DeferredToolResults
from pydantic_ai.usage import UsageLimits
from pydantic_ai_harness.step_persistence import SqliteStepStore

from pydantic_lab.runtime.agent import StreamRecorder, build_agent
from pydantic_lab.runtime.extensions import load_extensions
from pydantic_lab.runtime.policy import dump_messages
from pydantic_lab.storage.steps import DatabaseStepStore, ObservedStepStore


class Runner:
    def __init__(self, settings, store, sandbox, *, model=None, detach_on_approval=False):
        self.settings, self.store, self.sandbox, self.model = settings, store, sandbox, model
        self.owner = uuid.uuid4().hex
        self.detach_on_approval = detach_on_approval

    def steps(self, session, run_id):
        if session.mode == "local":
            native = SqliteStepStore(database=str(self.settings.state_dir / "framework.db"))
            return ObservedStepStore(native, self.store, session.id, run_id)
        return ObservedStepStore(
            DatabaseStepStore(self.store, session.id), self.store, session.id, run_id
        )

    async def restore(self, sid, rid):
        session = self.store.get(sid)
        run = session.run(rid)
        if run.owner == self.owner:
            return
        if any(r.status == "started" for r in run.receipts.values()):
            await self.sandbox.stop(sid)

            def unknown(s, emit):
                r = s.run(rid)
                for receipt in r.receipts.values():
                    if receipt.status == "started":
                        receipt.status = "outcome_unknown"
                r.status = s.status = "outcome_unknown"
                s.paused = True
                emit("recovery.required", run_id=rid)

            self.store.mutate(sid, unknown)
            return
        if run.native_ids:
            self.store.emit(sid, "checkpoint.loaded", run_id=rid, reason="resume")

    async def execute(self, sid: str, rid: str):
        await self.restore(sid, rid)
        current = self.store.get(sid)
        if current.run(rid).status == "outcome_unknown":
            return
        self.store.mutate(
            sid,
            lambda s, e: (
                setattr(s.run(rid), "owner", self.owner),
                setattr(s.run(rid), "status", "running"),
                setattr(s, "status", "running"),
            ),
        )
        step_store = self.steps(current, rid)
        native_task = None
        recorder = StreamRecorder(self.store, sid, rid)
        try:
            while True:
                session = self.store.get(sid)
                run = session.run(rid)
                if run.stop_requested:
                    raise asyncio.CancelledError()
                history = ModelMessagesTypeAdapter.validate_python(
                    run.pending_history or session.history
                )
                if run.native_ids:
                    latest = await step_store.latest_snapshot(
                        run_id=run.native_ids[-1], include_interrupted=True
                    )
                    if latest and latest.timestamp.timestamp() > getattr(run, "frontier_at", 0):
                        history = latest.messages
                deferred = None
                if (
                    history
                    and any(isinstance(p, ToolCallPart) for p in history[-1].parts)
                    and isinstance(history[-1], ModelResponse)
                ):
                    calls = [p for p in history[-1].parts if isinstance(p, ToolCallPart)]
                    by_id = {a.call_id: a for a in run.approvals}
                    missing = [
                        p
                        for p in calls
                        if p.tool_call_id not in by_id and p.tool_call_id not in run.receipts
                    ]
                    if missing:
                        # A model response was captured before tool dispatch. Native continuation
                        # needs an explicit result slot to execute unapproved calls through policy.
                        deferred = DeferredToolResults(
                            approvals={p.tool_call_id: True for p in calls}
                        )
                    elif any(
                        by_id.get(p.tool_call_id) and by_id[p.tool_call_id].status == "pending"
                        for p in calls
                    ):
                        self.store.mutate(
                            sid,
                            lambda s, e: (
                                setattr(s.run(rid), "status", "awaiting_approval"),
                                setattr(s, "status", "awaiting_approval"),
                            ),
                        )
                        if (
                            session.sandbox.state == "running"
                            and time.time() - session.sandbox.last_used > self.settings.idle_seconds
                        ):
                            await self.sandbox.stop(sid)
                        if self.detach_on_approval:
                            return
                        await asyncio.sleep(0.1)
                        continue
                    else:
                        # Expired calls are refused inside the permission adapter. This prevents
                        # native false-approval short-circuiting from skipping our audit boundary.
                        deferred = DeferredToolResults(
                            approvals={p.tool_call_id: True for p in calls}
                        )
                backend = await self.sandbox.ensure(sid)
                extensions, _ = await load_extensions(
                    self.store, session, backend, self.settings.state_dir
                )
                agent = build_agent(
                    self.settings,
                    self.store,
                    session,
                    run,
                    step_store,
                    model=self.model,
                    extensions=extensions,
                )
                native_id = uuid.uuid4().hex

                def attempt(s, emit):
                    r = s.run(rid)
                    r.native_ids.append(native_id)
                    r.status = "running"
                    s.status = "running"
                    emit("run.attempt", run_id=rid, native_run_id=native_id)

                self.store.mutate(sid, attempt)
                native_task = asyncio.create_task(
                    agent.run(
                        run.prompt if not run.native_ids else None,
                        message_history=history,
                        deferred_tool_results=deferred,
                        conversation_id=sid,
                        run_id=native_id,
                        workspace=backend,
                        usage_limits=UsageLimits(request_limit=self.settings.request_limit),
                        event_stream_handler=recorder,
                    )
                )
                while not native_task.done():
                    await asyncio.sleep(0.05)
                    if self.store.get(sid).run(rid).stop_requested:
                        native_task.cancel()
                        break
                result = await native_task
                recorder.flush()
                if self.store.get(sid).run(rid).stop_requested:
                    raise asyncio.CancelledError()
                history = result.all_messages()

                def save(s, emit):
                    r = s.run(rid)
                    r.pending_history = dump_messages(history)
                    r.frontier_at = time.time()
                    if isinstance(result.output, DeferredToolRequests):
                        r.status = s.status = "awaiting_approval"
                        emit("run.waiting", run_id=rid)

                self.store.mutate(sid, save)
                if isinstance(result.output, DeferredToolRequests):
                    continue
                latest = self.store.get(sid).run(rid)
                if any(not item.consumed for item in latest.steers):
                    continue

                def complete(s, emit):
                    r = s.run(rid)
                    if r.stop_requested:
                        raise asyncio.CancelledError()
                    if any(not item.consumed for item in r.steers):
                        return False
                    r.status = "completed"
                    r.answer = str(result.output)
                    s.history = dump_messages(history)
                    s.status = "ready"
                    s.sandbox.last_used = time.time()
                    emit("run.completed", run_id=rid, answer=r.answer)
                    return True

                if self.store.mutate(sid, complete):
                    return
        except asyncio.CancelledError:
            if native_task and not native_task.done():
                native_task.cancel()
                await asyncio.gather(native_task, return_exceptions=True)
            await recorder.close()
            await self.sandbox.stop(sid)
            if not self.store.get(sid).run(rid).stop_requested:
                # Service shutdown detaches execution. Only a durable Stop cancels a run.
                # A started receipt will be reconciled as unknown by the next owner.
                return

            def stopped(s, emit):
                r = s.run(rid)
                unknown = False
                for receipt in r.receipts.values():
                    if receipt.status == "started":
                        receipt.status = "outcome_unknown"
                        unknown = True
                r.status = "outcome_unknown" if unknown else "cancelled"
                s.status = "outcome_unknown" if unknown else "stopped"
                s.paused = True
                emit("run.stopped", run_id=rid, unknown=unknown)

            self.store.mutate(sid, stopped)
        except Exception as error:
            error_message = f"{type(error).__name__}: {str(error)[:1000]}"
            await recorder.close()

            def failed(s, emit):
                r = s.run(rid)
                unknown = any(receipt.status == "started" for receipt in r.receipts.values())
                for receipt in r.receipts.values():
                    if receipt.status == "started":
                        receipt.status = "outcome_unknown"
                r.status = "outcome_unknown" if unknown else "failed"
                r.error = error_message
                s.status = r.status
                if unknown:
                    s.paused = True
                emit("run.failed", run_id=rid, error=r.error)

            self.store.mutate(sid, failed)
        finally:
            await recorder.close()
