import asyncio

import pytest
from pydantic_ai.models.test import TestModel

from pydantic_lab.application.controls import Controls
from pydantic_lab.application.runner import Runner
from pydantic_lab.sandbox.manager import SandboxManager


async def wait_for(store, sid, predicate, task=None):
    async with asyncio.timeout(40):
        while True:
            session = store.get(sid)
            if predicate(session):
                return session
            if task and task.done():
                await task
                raise AssertionError(f"Run ended unexpectedly: {session.model_dump_json()}")
            await asyncio.sleep(0.05)


@pytest.mark.integration
async def test_native_approval_survives_new_runner_and_writes_real_workspace(
    store, local, settings
):
    controls = Controls(store)
    rid = controls.send(local.id, "Write a file", "queue", "first")["run_id"]
    manager = SandboxManager(store)
    first = Runner(
        settings,
        store,
        manager,
        model=TestModel(call_tools=["write_file"], custom_output_text="Done"),
    )
    task = asyncio.create_task(first.execute(local.id, rid))
    try:
        session = await wait_for(
            store, local.id, lambda s: s.run(rid).status == "awaiting_approval", task
        )
        approval = session.run(rid).approvals[0]
        # End the orchestration task at a durable wait, without sending Stop.
        task.cancel()
        await task

        # A graceful service detach must preserve the durable approval.
        assert store.get(local.id).run(rid).status == "awaiting_approval"
        assert not store.get(local.id).paused
        controls.decide(local.id, approval.id, True, "allow")
        second = Runner(
            settings,
            store,
            manager,
            model=TestModel(call_tools=["write_file"], custom_output_text="Done"),
        )
        await second.execute(local.id, rid)
        result = store.get(local.id).run(rid)
        assert result.status == "completed", result.error
        assert result.receipts[approval.call_id].status == "succeeded"
        assert list(__import__("pathlib").Path(local.repository).iterdir())
    finally:
        if not task.done():
            controls.stop(local.id, "cleanup")
            await task
        await manager.destroy(local.id)


@pytest.mark.integration
async def test_steer_during_approval_keeps_run_and_skips_old_edit(store, local, settings):
    controls = Controls(store)
    rid = controls.send(local.id, "Write a file", "queue", "first")["run_id"]
    manager = SandboxManager(store)
    runner = Runner(
        settings,
        store,
        manager,
        model=TestModel(call_tools=["write_file"], custom_output_text="Replanned"),
    )
    task = asyncio.create_task(runner.execute(local.id, rid))
    try:
        await wait_for(store, local.id, lambda s: s.run(rid).status == "awaiting_approval", task)
        controls.send(local.id, "Do not edit; answer now", "steer", "change")
        await asyncio.wait_for(task, 40)
        run = store.get(local.id).run(rid)
        assert run.status == "completed", run.error
        assert len(store.get(local.id).runs) == 1
        assert run.steers[0].consumed
        assert not run.receipts
    finally:
        if not task.done():
            controls.stop(local.id, "cleanup")
            await task
        await manager.destroy(local.id)
