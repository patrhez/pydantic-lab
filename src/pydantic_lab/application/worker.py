"""Independent agent-service process. The API never imports the execution loop."""

from __future__ import annotations

import asyncio
import fcntl
import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from pydantic_lab.application.runner import Runner
from pydantic_lab.config import Settings
from pydantic_lab.models import Approval, Receipt
from pydantic_lab.runtime.extensions import discover
from pydantic_lab.runtime.policy import digest
from pydantic_lab.sandbox.manager import SandboxManager
from pydantic_lab.storage.control import Conflict, ControlStore


class Worker:
    def __init__(self, settings, store=None, *, model=None):
        self.settings = settings
        self.store = store or ControlStore(settings.database_url, settings.redis_url)
        self.sandbox = SandboxManager(self.store)
        self.runner = Runner(
            settings, self.store, self.sandbox, model=model, detach_on_approval=True
        )
        self.tasks: dict[str, asyncio.Task] = {}
        self.closed = False

    async def provision(self, sid):
        session = self.store.get(sid)
        if any(r.status == "started" for r in session.setup_receipts.values()):
            await self.sandbox.stop(sid)

            def unknown(s, emit):
                for r in s.setup_receipts.values():
                    if r.status == "started":
                        r.status = "outcome_unknown"
                s.status = "outcome_unknown"
                emit("recovery.required", setup=True)

            self.store.mutate(sid, unknown)
            return
        try:
            if not session.clone_completed:
                self.store.emit(sid, "setup.cloning")
                await self.sandbox.clone(sid)
                self.store.mutate(sid, lambda s, e: setattr(s, "clone_completed", True))
            session = self.store.get(sid)
            backend = await self.sandbox.ensure(sid, initialize_network=True)
            while session.init_completed < len(session.init_commands):
                index = session.init_completed
                command = session.init_commands[index]
                call_id = f"setup_{index}"
                arguments = {"command": command, "timeout_seconds": 120}
                signature = digest("run_command", arguments)
                approval = next((a for a in session.setup_approvals if a.call_id == call_id), None)
                if not approval:
                    approval = Approval(
                        call_id=call_id,
                        tool="run_command",
                        arguments=arguments,
                        digest=signature,
                        policy_revision=session.policy.revision,
                        setup=True,
                    )
                    self.store.mutate(
                        sid,
                        lambda s, e: (
                            s.setup_approvals.append(approval),
                            e("approval.requested", approval=approval.model_dump(mode="json")),
                        ),
                    )
                    return
                if approval.status == "pending":
                    return
                if approval.status != "allowed":
                    raise Conflict("Setup command was rejected; it was not executed")
                # Setup uses the same native Shell guardrail, including explicit denials.
                from pydantic_ai import Agent
                from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart

                # The native shell parser is exercised by an exact deterministic tool call.
                from pydantic_ai.models.function import FunctionModel
                from pydantic_ai_harness import Shell

                def setup_model(messages, info):
                    if any(
                        getattr(p, "tool_call_id", None) == call_id
                        and getattr(p, "part_kind", None) == "tool-return"
                        for m in messages
                        for p in m.parts
                    ):
                        return ModelResponse(parts=[TextPart("Setup finished")])
                    return ModelResponse(
                        parts=[ToolCallPart("run_command", arguments, tool_call_id=call_id)]
                    )

                receipt = Receipt(
                    call_id=call_id, tool="run_command", digest=signature, status="started"
                )
                self.store.mutate(
                    sid,
                    lambda s, e: (
                        s.setup_receipts.update({call_id: receipt}),
                        e("execution.started", call_id=call_id, setup=True),
                    ),
                )
                shell = Shell(
                    tools=["run_command"],
                    allowed_commands=session.policy.allowed_commands,
                    denied_commands=[]
                    if session.policy.allowed_commands
                    else session.policy.denied_commands,
                    denied_operators=session.policy.denied_operators,
                    default_timeout=120,
                )
                agent = Agent(FunctionModel(setup_model), capabilities=[shell])
                result = await agent.run(
                    "Run the approved setup command.",
                    workspace=backend,
                    usage_limits=__import__(
                        "pydantic_ai.usage", fromlist=["UsageLimits"]
                    ).UsageLimits(request_limit=2),
                )
                returns = [
                    p
                    for m in result.all_messages()
                    for p in m.parts
                    if getattr(p, "part_kind", None) == "tool-return"
                ]
                output = str(returns[-1].content) if returns else "Setup did not execute"
                if "[exit code:" in output or "timed out" in output or not returns:
                    raise RuntimeError(output[-1000:])

                def finished(s, emit):
                    s.setup_receipts[call_id].status = "succeeded"
                    s.setup_receipts[call_id].result = output
                    s.init_completed += 1
                    emit(
                        "execution.completed",
                        call_id=call_id,
                        status="succeeded",
                        setup=True,
                        summary=output[-1000:],
                    )

                self.store.mutate(sid, finished)
                session = self.store.get(sid)
            await self.sandbox.ensure(sid, network_override=False)

            def ready(s, emit):
                s.initialized = True
                s.status = "ready"
                emit("setup.completed", commit=s.commit)

            self.store.mutate(sid, ready)
        except Exception as error:
            message = str(error)[:1500]

            def failed(s, emit):
                for receipt in s.setup_receipts.values():
                    if receipt.status == "started":
                        receipt.status = "failed"
                        receipt.result = message
                s.status = "failed"
                s.error = message
                emit("setup.failed", error=message)

            self.store.mutate(sid, failed)

    async def action(self, sid, item):
        kind = item["kind"]
        try:
            if kind == "trust":
                found = await discover(await self.sandbox.ensure(sid))
                category = item["payload"]["category"]
                if (
                    category not in found
                    or found[category]["identity"] != item["payload"]["identity"]
                ):
                    raise Conflict("Content changed; inspect it again")
                self.store.mutate(
                    sid,
                    lambda s, e: (
                        s.trust.update({category: found[category]["identity"]}),
                        e("trust.granted", category=category),
                    ),
                )
            elif kind in {"start", "network", "rebuild", "stop_sandbox"}:
                if kind == "rebuild":
                    await self.sandbox.destroy(sid, volume=False)
                if kind == "stop_sandbox":
                    await self.sandbox.stop(sid)
                else:
                    desired = item["payload"].get("enabled") if kind == "network" else None
                    await self.sandbox.ensure(sid, network_override=desired)
                    if kind == "network":
                        self.store.mutate(sid, lambda s, e: setattr(s.sandbox, "network", desired))
            elif kind == "delete":
                await self.sandbox.destroy(sid)
                self.store.mutate(sid, lambda s, e: setattr(s, "status", "deleted"))
            else:
                raise Conflict("Unknown workspace action")

            def done(s, emit):
                a = next(a for a in s.actions if a["id"] == item["id"])
                a["status"] = "completed"
                # Only control outcomes are durable; workspace inspection uses read RPC.
                s.inspection.pop("diff", None)
                s.inspection.pop("extensions", None)
                emit("action.completed", action_id=a["id"], action=kind)

            self.store.mutate(sid, done)
        except Exception as error:
            message = str(error)[:1500]

            def failed(s, emit):
                a = next(a for a in s.actions if a["id"] == item["id"])
                a["status"] = "failed"
                a["error"] = message
                if kind == "delete":
                    s.status = "cleanup_failed"
                emit("action.failed", action=kind, error=message)

            self.store.mutate(sid, failed)

    async def tick(self):
        for sid, task in list(self.tasks.items()):
            if task.done():
                try:
                    task.result()
                except Exception as error:
                    self.store.emit(sid, "worker.error", error=type(error).__name__)
                del self.tasks[sid]
        for session in self.store.list():
            if session.id in self.tasks or session.status == "deleted":
                continue
            if len(self.tasks) >= self.settings.concurrency:
                break
            pending_action = next(
                (a for a in session.actions if a["status"] in {"queued", "running"}), None
            )
            if pending_action:
                self.tasks[session.id] = asyncio.create_task(
                    self.action(session.id, pending_action)
                )
                continue
            if session.status == "provisioning":
                self.tasks[session.id] = asyncio.create_task(self.provision(session.id))
                continue
            active = session.active()
            if (
                active
                and active.status == "awaiting_approval"
                and not active.stop_requested
                and not any(not item.consumed for item in active.steers)
                and any(a.status == "pending" for a in active.approvals)
            ):
                if (
                    session.sandbox.state == "running"
                    and time.time() - session.sandbox.last_used > self.settings.idle_seconds
                ):
                    self.tasks[session.id] = asyncio.create_task(self.sandbox.stop(session.id))
                continue
            if active and active.status != "outcome_unknown":
                self.tasks[session.id] = asyncio.create_task(
                    self.runner.execute(session.id, active.id)
                )
                continue
            if not session.paused and session.initialized:
                queued = next((r for r in session.runs if r.status == "queued"), None)
                if queued:

                    def claim(s, emit):
                        if s.paused or s.active() or s.run(queued.id).status != "queued":
                            return False
                        s.run(queued.id).status = "running"
                        s.status = "running"
                        emit("queue.consumed", run_id=queued.id)
                        return True

                    if self.store.mutate(session.id, claim):
                        self.tasks[session.id] = asyncio.create_task(
                            self.runner.execute(session.id, queued.id)
                        )
                    continue
            if (
                session.sandbox.state == "running"
                and not active
                and time.time() - session.sandbox.last_used > self.settings.idle_seconds
            ):
                self.tasks[session.id] = asyncio.create_task(self.sandbox.stop(session.id))

    async def serve(self):
        lock_path = self.settings.state_dir / "worker.lock"
        with lock_path.open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                while not self.closed:
                    await self.tick()
                    await asyncio.sleep(0.2)
            finally:
                for task in self.tasks.values():
                    task.cancel()
                await asyncio.gather(*self.tasks.values(), return_exceptions=True)


def create_agent_app(worker):
    from pydantic_lab.application.inspection import inspect_workspace

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(worker.serve())
        yield
        worker.closed = True
        await task

    app = FastAPI(title="Internal agent service", lifespan=lifespan)

    @app.exception_handler(Conflict)
    async def conflict(request, error):
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.get("/internal/health")
    async def health():
        return {"status": "ok", "role": "agent"}

    @app.get("/internal/sessions/{sid}/inspect/{kind}")
    async def inspect(sid: str, kind: str, approval_id: str | None = None):
        if kind not in {"diff", "extensions", "approval"}:
            raise Conflict("Unknown inspection")
        return await inspect_workspace(worker, sid, kind, approval_id)

    return app


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(create_agent_app(Worker(Settings.load())), host="0.0.0.0", port=8001)
