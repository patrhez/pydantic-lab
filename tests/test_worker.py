import asyncio
from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from pydantic_lab.application.controls import Controls
from pydantic_lab.application.worker import Worker
from pydantic_lab.models import Session


@pytest.mark.integration
async def test_pending_approval_releases_worker_capacity_and_queue_stays_paused(
    store, local, settings, tmp_path
):
    settings.concurrency = 1
    second_path = tmp_path / "second"
    second_path.mkdir()
    second = store.create(
        Session(title="Independent", mode="local", repository=str(second_path), initialized=True)
    )
    controls = Controls(store)
    first = controls.send(local.id, "First", "queue", "first")["run_id"]
    follow = controls.send(local.id, "Later", "queue", "later")["run_id"]
    other = controls.send(second.id, "Other", "queue", "other")["run_id"]
    worker = Worker(
        settings, store, model=TestModel(call_tools=["write_file"], custom_output_text="Done")
    )

    async def wait(predicate):
        async with asyncio.timeout(40):
            while not predicate():
                await worker.tick()
                await asyncio.sleep(0.05)

    try:
        await wait(
            lambda: (
                store.get(local.id).run(first).status == "awaiting_approval"
                and store.get(second.id).run(other).status == "awaiting_approval"
            )
        )
        assert store.get(local.id).run(follow).status == "queued"
        assert store.get(local.id).sandbox.id != store.get(second.id).sandbox.id
        controls.stop(local.id, "stop")
        await wait(lambda: store.get(local.id).status == "stopped")
        assert store.get(local.id).paused and store.get(local.id).run(follow).status == "queued"
        controls.continue_queue(local.id, "continue")
        await wait(lambda: store.get(local.id).run(follow).status == "awaiting_approval")
        assert store.get(local.id).run(first).status == "cancelled"
        approval = store.get(local.id).run(follow).approvals[0]
        controls.decide(local.id, approval.id, True, "allow")
        await wait(lambda: store.get(local.id).run(follow).status == "completed")
        assert (Path(local.repository) / "a").exists()
        assert not (second_path / "a").exists()
    finally:
        for task in worker.tasks.values():
            task.cancel()
        await asyncio.gather(*worker.tasks.values(), return_exceptions=True)
        await worker.sandbox.destroy(local.id)
        await worker.sandbox.destroy(second.id)
