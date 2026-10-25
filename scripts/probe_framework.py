"""Run a real framework approval cycle against a Docker workspace."""

import asyncio
from pathlib import Path

from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import DeferredToolRequests, DeferredToolResults
from pydantic_ai_harness.step_persistence import SqliteStepStore

from pydantic_lab.config import Settings
from pydantic_lab.models import Run, Session
from pydantic_lab.runtime.agent import build_agent
from pydantic_lab.sandbox.manager import SandboxManager
from pydantic_lab.storage.control import ControlStore


async def main():
    root = Path(".local-data/probe").resolve()
    root.mkdir(parents=True, exist_ok=True)
    store = ControlStore(f"sqlite:///{root / 'control.db'}")
    session = Session(
        title="Native approval probe",
        mode="local",
        repository=str(root / "workspace"),
        initialized=True,
    )
    Path(session.repository).mkdir(exist_ok=True)
    session.sandbox.image = "node:22-alpine"
    run = Run(prompt="Write a small file.", status="running")
    session.runs.append(run)
    store.create(session)
    sandbox = SandboxManager(store)
    try:
        backend = await sandbox.ensure(session.id)
        steps = SqliteStepStore(database=str(root / "framework.db"))
        model = TestModel(call_tools=["write_file"], custom_output_text="Done.")
        agent = build_agent(Settings(demo=True), store, session, run, steps, model=model)
        first = await agent.run(run.prompt, workspace=backend, conversation_id=session.id)
        assert isinstance(first.output, DeferredToolRequests), type(first.output)
        approval = store.get(session.id).run(run.id).approvals[0]
        store.mutate(
            session.id, lambda s, e: setattr(s.run(run.id).approvals[0], "status", "allowed")
        )
        second = await agent.run(
            message_history=first.all_messages(),
            deferred_tool_results=DeferredToolResults(approvals={approval.call_id: True}),
            workspace=backend,
            conversation_id=session.id,
        )
        assert second.output == "Done.", second.output
        assert store.get(session.id).run(run.id).receipts[approval.call_id].status == "succeeded"
        native_runs = await steps.list_runs(conversation_id=session.id)
        assert len(native_runs) == 2
        snapshot = await steps.latest_snapshot(run_id=native_runs[-1].run_id)
        assert snapshot and snapshot.state == "complete"
        print(
            "PASS: native tool deferral, approval continuation, Docker file edit, receipt, and settled checkpoint"
        )
    finally:
        await sandbox.destroy(session.id)


if __name__ == "__main__":
    asyncio.run(main())
